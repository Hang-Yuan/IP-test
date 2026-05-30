from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import asdict, dataclass
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .agent import AgentRequest, LocalAgent
from .adapters.gewechat_bridge import normalize_callback_payload as normalize_gewechat_payload
from .adapters.gewechat_bridge import send_text as send_gewechat_text
from .adapters.pc_hook_bridge import normalize_callback_payload, send_text as send_pchook_text
from .adapters.wechat_keyboard import send_text as send_wechat_keyboard_text
from .adapters.wx4py_bridge import send_text as send_wx4py_text
from .store import JsonlStore
from .wechat_xml import check_signature, parse_text_message, text_reply


BASE_DIR = Path(__file__).resolve().parent
STAGE_DIR = BASE_DIR.parent
STATIC_DIR = BASE_DIR / "static"
STORE = JsonlStore(STAGE_DIR / "data" / "messages.jsonl")
AGENT = LocalAgent()
TARGET_SEPARATORS = ("\r", "\n", ";", "；", ",", "，", "、", "|")
BROADCAST_TARGETS = {"*", "all", "@all", "所有", "所有人", "全部", "全体", "群发"}
DEFAULT_BLOCKED_AUTO_SEND_TARGETS = "微信ClawBot,文件传输助手"
SEND_COMMAND_PATTERNS = [
    re.compile(r"^(?:帮我)?给(?P<target>.+?)(?:发(?:一条)?(?:微信|消息)|发微信消息)[：:](?P<text>.+)$", re.S),
    re.compile(r"^(?:帮我)?用微信给(?P<target>.+?)发(?:一条)?消息[：:](?P<text>.+)$", re.S),
    re.compile(r"^(?:微信)?发送给(?P<target>.+?)[：:](?P<text>.+)$", re.S),
]


@dataclass(frozen=True)
class GuardedSendResult:
    ok: bool
    target: str
    text: str
    error: str
    driver: str = "guard"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def split_target_values(value: object) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        raw_items = [str(item) for item in value]
    else:
        raw_items = re.split(r"[,，;；|\n\r]+", str(value))
    return {item.strip().lower() for item in raw_items if item and item.strip()}


def auto_send_allowlist() -> set[str]:
    allowed: set[str] = set()
    for name in (
        "WECHAT_AUTO_SEND_ALLOW_TARGETS",
        "WECHAT_AUTO_SEND_ALLOW_USERS",
        "WECHAT_AUTO_SEND_ALLOW_DISPLAY_NAMES",
    ):
        allowed |= split_target_values(os.getenv(name, ""))
    return allowed


def auto_send_blocklist() -> set[str]:
    blocked = split_target_values(DEFAULT_BLOCKED_AUTO_SEND_TARGETS)
    blocked |= split_target_values(os.getenv("WECHAT_AUTO_SEND_BLOCK_TARGETS", ""))
    return blocked


def target_validation_error(target: str) -> str:
    clean_target = str(target or "").strip()
    if not clean_target:
        return "target is required"
    if clean_target.lower() in BROADCAST_TARGETS:
        return "broadcast target is not allowed"
    if any(separator in clean_target for separator in TARGET_SEPARATORS):
        return "target must be exactly one chat"
    return ""


def target_aliases(payload: dict[str, Any], sender: str, reply_target: str, room_id: str) -> set[str]:
    aliases = {sender, reply_target, room_id, str(payload.get("sender", ""))}
    raw = payload.get("raw")
    if isinstance(raw, dict):
        aliases |= {
            str(raw.get("username", "")),
            str(raw.get("display_name", "")),
            str(raw.get("reply_target", "")),
        }
    return {alias.strip().lower() for alias in aliases if alias and alias.strip()}


def inbound_event_key(payload: dict[str, Any], source: str, sender: str) -> str:
    explicit = payload.get("event_id") or payload.get("message_id") or payload.get("msg_id")
    if explicit:
        return f"{source}:{explicit}"
    raw = payload.get("raw")
    if isinstance(raw, dict):
        raw_source = str(raw.get("source") or source).strip()
        parts = [
            raw_source,
            str(raw.get("db_file", "")).strip(),
            str(raw.get("table", "")).strip(),
            str(raw.get("local_id", "")).strip(),
            str(raw.get("sort_seq", "")).strip(),
        ]
        if all(parts):
            return ":".join(parts)
    return ""


def auto_send_block_reason(
    payload: dict[str, Any],
    sender: str,
    reply_target: str,
    room_id: str,
    inbound_key: str = "",
) -> str:
    expected_target = room_id or sender
    target_error = target_validation_error(reply_target)
    if target_error:
        return target_error
    if expected_target and reply_target.strip() != expected_target.strip():
        return "reply_target must match the current inbound chat"
    if target_aliases(payload, sender, reply_target, room_id) & auto_send_blocklist():
        return "target is blocked from auto send"
    if inbound_key and STORE.has_meta_value(
        "inbound_event_key",
        inbound_key,
        direction="out",
        channel_prefix="wechat_",
    ):
        return "inbound event already has a send attempt"
    allowed = auto_send_allowlist()
    if allowed and not (target_aliases(payload, sender, reply_target, room_id) & allowed):
        return "target is outside WECHAT_AUTO_SEND_ALLOW_TARGETS"
    return ""


def parse_wechat_send_command(text: str) -> dict[str, str] | None:
    cleaned = str(text or "").strip()
    for pattern in SEND_COMMAND_PATTERNS:
        matched = pattern.match(cleaned)
        if not matched:
            continue
        target = matched.group("target").strip(" \t\r\n\"'“”‘’")
        message = matched.group("text").strip()
        if target and message:
            return {"target": target, "text": message}
    return None


class GatewayHandler(SimpleHTTPRequestHandler):
    server_version = "IPWeChatGateway/0.1"

    def do_GET(self) -> None:
        route = urlparse(self.path).path
        if route == "/":
            self.serve_static("index.html")
            return
        if route == "/health":
            self.send_json(
                {
                    "status": "ok",
                    "agent_mode": AGENT.mode,
                    "store": str(STORE.path),
                }
            )
            return
        if route == "/admin/messages":
            query = parse_qs(urlparse(self.path).query)
            limit = int(query.get("limit", ["50"])[0])
            self.send_json({"messages": STORE.tail(limit=limit)})
            return
        if route == "/wechat/official":
            self.handle_wechat_verify()
            return
        if route.startswith("/static/"):
            self.serve_static(route.removeprefix("/static/"))
            return
        self.send_error(HTTPStatus.NOT_FOUND, "not found")

    def do_POST(self) -> None:
        route = urlparse(self.path).path
        if route == "/webhook/manual":
            self.handle_json_message("manual")
            return
        if route == "/webhook/pchook":
            self.handle_pc_hook_callback()
            return
        if route == "/webhook/gewechat":
            self.handle_gewechat_callback()
            return
        if route == "/wechat/official":
            self.handle_wechat_official_post()
            return
        if route == "/wechat/inbound":
            self.handle_wechat_inbound()
            return
        if route == "/wechat/send":
            self.handle_wechat_send()
            return
        if route == "/wechat/wx4py/send":
            self.handle_wechat_send(driver_override="wx4py")
            return
        if route == "/v1/chat/completions":
            self.handle_openai_chat_completion()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "not found")

    def handle_json_message(self, channel: str) -> None:
        payload = self.read_json()
        text = str(payload.get("text", "")).strip()
        user_id = str(payload.get("from_user", payload.get("user_id", "manual-user"))).strip()
        if not text:
            self.send_error(HTTPStatus.BAD_REQUEST, "text is required")
            return
        result = self.process_message(channel=channel, user_id=user_id, text=text, meta=payload)
        self.send_json(result)

    def handle_wechat_verify(self) -> None:
        query = parse_qs(urlparse(self.path).query)
        token = os.getenv("WECHAT_OFFICIAL_TOKEN", "")
        signature = query.get("signature", [""])[0]
        timestamp = query.get("timestamp", [""])[0]
        nonce = query.get("nonce", [""])[0]
        echostr = query.get("echostr", [""])[0]
        if not check_signature(token, timestamp, nonce, signature):
            self.send_error(HTTPStatus.FORBIDDEN, "bad signature")
            return
        self.send_text(echostr)

    def handle_wechat_official_post(self) -> None:
        raw = self.read_body().decode("utf-8")
        try:
            message = parse_text_message(raw)
        except Exception as exc:
            self.send_error(HTTPStatus.BAD_REQUEST, f"bad xml: {exc}")
            return
        if not message.content:
            self.send_text("success")
            return
        result = self.process_message(
            channel="wechat_official",
            user_id=message.from_user,
            text=message.content,
            meta={"to_user": message.to_user},
        )
        reply_xml = text_reply(
            to_user=message.from_user,
            from_user=message.to_user,
            content=str(result["reply"]["text"])[:1800],
        )
        self.send_xml(reply_xml)

    def handle_wechat_send(self, driver_override: str | None = None) -> None:
        payload = self.read_json()
        target = str(payload.get("target") or payload.get("to") or "").strip()
        text = str(payload.get("text") or payload.get("message") or "").strip()
        target_type = str(payload.get("target_type", "contact")).strip() or "contact"
        driver = (driver_override or str(payload.get("driver", os.getenv("WECHAT_SEND_DRIVER", "keyboard")))).strip().lower()
        target_error = target_validation_error(target)
        if target_error:
            self.send_error(HTTPStatus.BAD_REQUEST, target_error)
            return
        if not text:
            self.send_error(HTTPStatus.BAD_REQUEST, "text is required")
            return

        result = self.send_wechat_text(target=target, text=text, target_type=target_type, driver=driver)
        outbound = STORE.append(
            direction="out",
            channel=f"wechat_{driver}",
            user_id=target,
            text=text,
            meta={
                "ok": result.ok,
                "target": target,
                "send_result": result.to_dict(),
            },
        )
        status = HTTPStatus.OK if result.ok else HTTPStatus.INTERNAL_SERVER_ERROR
        self.send_json({"ok": result.ok, "result": result.to_dict(), "outbound": asdict(outbound)}, status=status)

    def send_wechat_text(self, target: str, text: str, target_type: str = "contact", driver: str = "keyboard") -> Any:
        target_error = target_validation_error(target)
        if target_error:
            return GuardedSendResult(False, target, text, target_error)
        if driver == "wx4py":
            return send_wx4py_text(target=target, text=text, target_type=target_type)
        if driver == "auto":
            wx4py_result = send_wx4py_text(target=target, text=text, target_type=target_type)
            if wx4py_result.ok:
                return wx4py_result
        return send_wechat_keyboard_text(target=target, text=text)

    def handle_pc_hook_callback(self) -> None:
        payload = self.read_json()
        message = normalize_callback_payload(payload)
        if message.ignored:
            self.send_json({"ok": True, "ignored": True, "reason": message.reason, "source": message.source})
            return

        auto_send = bool(payload.get("auto_send", False)) or os.getenv("PCHOOK_AUTO_SEND", "").lower() in {
            "1",
            "true",
            "yes",
        }
        result = self.process_message(
            channel=f"inbound:{message.source}",
            user_id=message.reply_target or message.sender,
            text=message.text,
            meta={**payload, "normalized": asdict(message), "auto_send": auto_send},
        )

        send_result = None
        if auto_send:
            reply_text = str(result["reply"]["text"]).strip()
            send_result = send_pchook_text(
                to_wxid=message.reply_target,
                content=reply_text,
                api_url=os.getenv("PCHOOK_API_URL", "http://127.0.0.1:8981/api"),
            )
            STORE.append(
                direction="out",
                channel="pchook",
                user_id=message.reply_target,
                text=reply_text,
                meta={"source": message.source, "send_result": send_result, "in_reply_to": result["inbound"]["message_id"]},
            )

        self.send_json({"ok": True, **result, "auto_send": auto_send, "send": send_result})

    def handle_gewechat_callback(self) -> None:
        payload = self.read_json()
        message = normalize_gewechat_payload(payload)
        if message.ignored:
            self.send_json({"ok": True, "ignored": True, "reason": message.reason, "source": message.source})
            return

        auto_send = bool(payload.get("auto_send", False)) or os.getenv("GEWECHAT_AUTO_SEND", "").lower() in {
            "1",
            "true",
            "yes",
        }
        result = self.process_message(
            channel=f"inbound:{message.source}",
            user_id=message.reply_target or message.sender,
            text=message.text,
            meta={**payload, "normalized": message.to_dict(), "auto_send": auto_send},
        )

        send_result = None
        if auto_send:
            reply_text = str(result["reply"]["text"]).strip()
            send_result = send_gewechat_text(
                app_id=message.app_id or os.getenv("GEWECHAT_APP_ID", ""),
                to_wxid=message.reply_target,
                content=reply_text,
                api_url=os.getenv("GEWECHAT_API_URL", "http://127.0.0.1:2531/v2/api"),
                token=os.getenv("GEWECHAT_TOKEN", ""),
            )
            STORE.append(
                direction="out",
                channel="gewechat",
                user_id=message.reply_target,
                text=reply_text,
                meta={"source": message.source, "send_result": send_result, "in_reply_to": result["inbound"]["message_id"]},
            )

        self.send_json({"ok": True, **result, "auto_send": auto_send, "send": send_result})

    def handle_wechat_inbound(self) -> None:
        payload = self.read_json()
        text = str(payload.get("text") or payload.get("content") or "").strip()
        sender = str(payload.get("from_user") or payload.get("sender") or "").strip()
        room_id = str(payload.get("room_id") or payload.get("roomid") or "").strip()
        source = str(payload.get("source", "wechat_event")).strip() or "wechat_event"
        reply_target = str(payload.get("reply_target") or (room_id or sender)).strip()
        auto_send_requested = truthy(payload.get("auto_send", False)) or truthy(os.getenv("WECHAT_AUTO_SEND", ""))

        if not sender:
            self.send_error(HTTPStatus.BAD_REQUEST, "from_user/sender is required")
            return
        if not text:
            self.send_error(HTTPStatus.BAD_REQUEST, "text/content is required")
            return

        inbound_key = inbound_event_key(payload, source, sender)
        send_block_reason = (
            auto_send_block_reason(payload, sender, reply_target, room_id, inbound_key)
            if auto_send_requested
            else ""
        )
        auto_send = auto_send_requested and not send_block_reason

        result = self.process_message(
            channel=f"inbound:{source}",
            user_id=reply_target or sender,
            text=text,
            meta={
                **payload,
                "sender": sender,
                "room_id": room_id,
                "reply_target": reply_target,
                "inbound_event_key": inbound_key,
                "auto_send_requested": auto_send_requested,
                "auto_send": auto_send,
                "send_block_reason": send_block_reason,
            },
        )

        send_result = None
        send_outbound = None
        if auto_send:
            if not reply_target:
                self.send_error(HTTPStatus.BAD_REQUEST, "reply_target is required when auto_send is true")
                return
            reply_text = str(result["reply"]["text"]).strip()
            send_result = self.send_wechat_text(
                target=reply_target,
                text=reply_text,
                driver=os.getenv("WECHAT_SEND_DRIVER", "keyboard").strip().lower() or "keyboard",
            )
            send_outbound = STORE.append(
                direction="out",
                channel=f"wechat_{os.getenv('WECHAT_SEND_DRIVER', 'keyboard').strip().lower() or 'keyboard'}",
                user_id=reply_target,
                text=reply_text,
                meta={
                    "ok": send_result.ok,
                    "source": source,
                    "in_reply_to": result["inbound"]["message_id"],
                    "inbound_event_key": inbound_key,
                    "target_lock": {
                        "sender": sender,
                        "reply_target": reply_target,
                        "room_id": room_id,
                    },
                    "send_result": send_result.to_dict(),
                },
            )

        response = {
            **result,
            "auto_send_requested": auto_send_requested,
            "auto_send": auto_send,
            "send_block_reason": send_block_reason,
            "send": None
            if send_result is None
            else {
                "ok": send_result.ok,
                "result": send_result.to_dict(),
                "outbound": asdict(send_outbound),
            },
        }
        status = HTTPStatus.OK if send_result is None or send_result.ok else HTTPStatus.INTERNAL_SERVER_ERROR
        self.send_json(response, status=status)

    def handle_openai_chat_completion(self) -> None:
        payload = self.read_json()
        messages = payload.get("messages", [])
        user_id = str(payload.get("user", "weclaw-user")).strip() or "weclaw-user"
        text = ""
        if isinstance(messages, list):
            for message in reversed(messages):
                if not isinstance(message, dict):
                    continue
                content = message.get("content", "")
                if isinstance(content, list):
                    parts = []
                    for item in content:
                        if isinstance(item, dict):
                            parts.append(str(item.get("text", "")))
                        else:
                            parts.append(str(item))
                    content = "\n".join(part for part in parts if part)
                if str(content).strip():
                    text = str(content).strip()
                    break
        if not text:
            self.send_error(HTTPStatus.BAD_REQUEST, "messages content is required")
            return

        send_command = parse_wechat_send_command(text)
        if send_command:
            inbound = STORE.append(
                direction="in",
                channel="weclaw_http",
                user_id=user_id,
                text=text,
                meta={"source": "weclaw", "raw_model": payload.get("model", ""), "intent": "wechat_send"},
            )
            send_result = self.send_wechat_text(
                target=send_command["target"],
                text=send_command["text"],
                driver=os.getenv("WECHAT_COMMAND_SEND_DRIVER", os.getenv("WECHAT_SEND_DRIVER", "auto")).strip().lower()
                or "wx4py",
            )
            if send_result.ok:
                reply_text = f"已通过本机微信发送给「{send_command['target']}」：{send_command['text']}"
            elif getattr(send_result, "login_required", False):
                reply_text = "本机微信还在登录窗口，需要先把小号登录进主界面，我这边暂时没有发出去。"
            else:
                reply_text = f"这条微信暂时没发出去：{send_result.error}"
            outbound = STORE.append(
                direction="out",
                channel="weclaw_http",
                user_id=user_id,
                text=reply_text,
                meta={
                    "backend": "wechat_send_command",
                    "ok": send_result.ok,
                    "target": send_command["target"],
                    "send_result": send_result.to_dict(),
                    "in_reply_to": inbound.message_id,
                },
            )
            self.send_json(
                {
                    "id": outbound.message_id,
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": payload.get("model", "ip-demo"),
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": reply_text},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                }
            )
            return

        result = self.process_message(
            channel="weclaw_http",
            user_id=user_id,
            text=text,
            meta={"source": "weclaw", "raw_model": payload.get("model", "")},
        )
        reply_text = str(result["reply"]["text"])
        self.send_json(
            {
                "id": result["outbound"]["message_id"],
                "object": "chat.completion",
                "created": int(time.time()),
                "model": payload.get("model", "ip-demo"),
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": reply_text},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }
        )

    def process_message(
        self,
        channel: str,
        user_id: str,
        text: str,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        inbound = STORE.append(
            direction="in",
            channel=channel,
            user_id=user_id,
            text=text,
            meta=meta or {},
        )
        agent_response = AGENT.reply(AgentRequest(user_id=user_id, text=text))
        outbound = STORE.append(
            direction="out",
            channel=channel,
            user_id=user_id,
            text=agent_response.text,
            meta={
                "backend": agent_response.backend,
                "ok": agent_response.ok,
                "error": agent_response.error,
                "in_reply_to": inbound.message_id,
            },
        )
        return {
            "inbound": asdict(inbound),
            "outbound": asdict(outbound),
            "reply": asdict(agent_response),
        }

    def read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0"))
        return self.rfile.read(length) if length > 0 else b""

    def read_json(self) -> dict[str, Any]:
        body = self.read_body()
        if not body:
            return {}
        return json.loads(body.decode("utf-8"))

    def send_json(self, data: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, text: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_xml(self, text: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_static(self, name: str) -> None:
        safe_name = Path(name).name
        path = STATIC_DIR / safe_name
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "not found")
            return
        content_type = "text/html; charset=utf-8"
        if path.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        if path.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[wechat-gateway] {self.address_string()} {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8791)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), GatewayHandler)
    print(f"WeChat presentation gateway listening on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
