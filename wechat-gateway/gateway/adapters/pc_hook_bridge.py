from __future__ import annotations

"""PC WeChat hook boundary helpers.

This module does not inject or control WeChat by itself. It only normalizes
callback payloads from hook sidecars and calls a local hook HTTP API when one is
already running.
"""

import argparse
import json
import os
import urllib.request
from dataclasses import dataclass, asdict
from typing import Any
from urllib.error import URLError


DEFAULT_API_URL = "http://127.0.0.1:8981/api"
DEFAULT_GATEWAY_URL = "http://127.0.0.1:8791/webhook/pchook"

VXHOOK_TYPE_LIST_PROCESSES = 10001
VXHOOK_TYPE_TAKEOVER_PROCESS = 10002
VXHOOK_TYPE_SEND_TEXT = 34001
VXHOOK_TYPE_RECEIVE_MESSAGE = 20001


@dataclass
class NormalizedHookMessage:
    text: str
    sender: str
    reply_target: str
    room_id: str
    source: str
    ignored: bool = False
    reason: str = ""

    def to_inbound_payload(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "from_user": self.sender,
            "reply_target": self.reply_target,
            "room_id": self.room_id,
            "source": self.source,
        }


def post_json(url: str, payload: dict[str, Any], timeout: int = 8) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body else {}


def call_vxhook(api_url: str, command_type: int, data: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"type": command_type}
    if data is not None:
        payload["data"] = data
    return post_json(api_url, payload)


def list_processes(api_url: str = DEFAULT_API_URL) -> dict[str, Any]:
    return call_vxhook(api_url, VXHOOK_TYPE_LIST_PROCESSES)


def takeover_process(pid: int, api_url: str = DEFAULT_API_URL) -> dict[str, Any]:
    return call_vxhook(api_url, VXHOOK_TYPE_TAKEOVER_PROCESS, {"pid": pid})


def send_text(to_wxid: str, content: str, api_url: str = DEFAULT_API_URL) -> dict[str, Any]:
    return call_vxhook(api_url, VXHOOK_TYPE_SEND_TEXT, {"to_wxid": to_wxid, "content": content})


def normalize_callback_payload(payload: dict[str, Any]) -> NormalizedHookMessage:
    """Normalize common PC hook callback shapes into the gateway inbound shape."""

    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    event_type = payload.get("type")

    if event_type is not None and int_or_none(event_type) not in {VXHOOK_TYPE_RECEIVE_MESSAGE, None}:
        return NormalizedHookMessage(
            text="",
            sender="",
            reply_target="",
            room_id="",
            source=f"pchook:type:{event_type}",
            ignored=True,
            reason="not a receive-message event",
        )

    content = first_text(data, "content", "msg", "message", "text") or first_text(
        payload, "content", "msg", "message", "text"
    )
    sender = first_text(data, "sender", "from_wxid", "fromWxid", "wxid") or first_text(
        payload, "sender", "from_user", "from_wxid", "fromWxid", "wxid"
    )
    source_chat = first_text(data, "from", "room_id", "roomid", "talker") or first_text(
        payload, "from", "room_id", "roomid", "talker"
    )
    to_wxid = first_text(data, "receive", "to_wxid", "toWxid") or first_text(
        payload, "receive", "to_wxid", "toWxid"
    )

    msgtype = data.get("msgtype", payload.get("msgtype", payload.get("type")))
    room_id = source_chat if source_chat.endswith("@chatroom") else ""
    reply_target = room_id or source_chat or sender

    if not content:
        return NormalizedHookMessage(
            text="",
            sender=sender or source_chat or to_wxid,
            reply_target=reply_target,
            room_id=room_id,
            source="pchook",
            ignored=True,
            reason="empty message content",
        )

    text = content.strip()
    if str(msgtype) not in {"", "1", "20001"} and text.startswith("<"):
        text = f"[non-text message msgtype={msgtype}]"

    return NormalizedHookMessage(
        text=text,
        sender=sender or source_chat or to_wxid,
        reply_target=reply_target,
        room_id=room_id,
        source="pchook:vxhook" if event_type == VXHOOK_TYPE_RECEIVE_MESSAGE else "pchook",
    )


def first_text(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="PC WeChat hook bridge helper")
    parser.add_argument("command", choices=["probe", "takeover", "send", "simulate-callback"])
    parser.add_argument("--api-url", default=os.getenv("PCHOOK_API_URL", DEFAULT_API_URL))
    parser.add_argument("--gateway-url", default=os.getenv("PCHOOK_GATEWAY_URL", DEFAULT_GATEWAY_URL))
    parser.add_argument("--pid", type=int)
    parser.add_argument("--to")
    parser.add_argument("--text")
    args = parser.parse_args()

    try:
        if args.command == "probe":
            print(json.dumps(list_processes(args.api_url), ensure_ascii=False, indent=2))
            return
        if args.command == "takeover":
            if args.pid is None:
                parser.error("--pid is required")
            print(json.dumps(takeover_process(args.pid, args.api_url), ensure_ascii=False, indent=2))
            return
        if args.command == "send":
            if not args.to or not args.text:
                parser.error("--to and --text are required")
            print(json.dumps(send_text(args.to, args.text, args.api_url), ensure_ascii=False, indent=2))
            return
        if args.command == "simulate-callback":
            payload = {
                "type": VXHOOK_TYPE_RECEIVE_MESSAGE,
                "pid": 0,
                "port": 8981,
                "data": {
                    "content": args.text or "PC Hook callback test",
                    "from": args.to or "filehelper",
                    "msgid": "simulated",
                    "msgtype": 1,
                    "receive": "self",
                    "sender": args.to or "filehelper",
                },
            }
            print(json.dumps(post_json(args.gateway_url, payload), ensure_ascii=False, indent=2))
    except URLError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "api_url": args.api_url,
                    "error": str(exc.reason),
                    "hint": "PC Hook sidecar is not reachable. Start the hook program first, then run probe again.",
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
