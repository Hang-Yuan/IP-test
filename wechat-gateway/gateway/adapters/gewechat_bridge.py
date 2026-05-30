from __future__ import annotations

"""Gewechat/GeWe callback and send boundary helpers."""

import argparse
import json
import os
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any
from urllib.error import URLError


DEFAULT_API_URL = "http://127.0.0.1:2531/v2/api"
DEFAULT_GATEWAY_URL = "http://127.0.0.1:8791/webhook/gewechat"


@dataclass
class NormalizedGewechatMessage:
    text: str
    sender: str
    reply_target: str
    room_id: str
    app_id: str
    source: str
    ignored: bool = False
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def post_json(url: str, payload: dict[str, Any], token: str = "", timeout: int = 12) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["X-GEWE-TOKEN"] = token
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body else {}


def send_text(
    app_id: str,
    to_wxid: str,
    content: str,
    api_url: str = DEFAULT_API_URL,
    token: str = "",
    ats: str = "",
) -> dict[str, Any]:
    url = api_url.rstrip("/") + "/message/postText"
    payload = {
        "appId": app_id,
        "toWxid": to_wxid,
        "content": content,
        "ats": ats,
    }
    return post_json(url, payload, token=token)


def normalize_callback_payload(payload: dict[str, Any]) -> NormalizedGewechatMessage:
    type_name = str(payload.get("TypeName", payload.get("type_name", ""))).strip()
    app_id = str(payload.get("Appid", payload.get("appId", payload.get("app_id", "")))).strip()
    self_wxid = str(payload.get("Wxid", payload.get("wxid", ""))).strip()
    data = payload.get("Data") if isinstance(payload.get("Data"), dict) else payload.get("data", {})
    if not isinstance(data, dict):
        data = {}

    if type_name and type_name != "AddMsg":
        return NormalizedGewechatMessage(
            text="",
            sender="",
            reply_target="",
            room_id="",
            app_id=app_id,
            source=f"gewechat:{type_name}",
            ignored=True,
            reason="not an AddMsg event",
        )

    msg_type = data.get("MsgType", data.get("msgType"))
    from_user = nested_string(data.get("FromUserName")) or str(data.get("fromUserName", "")).strip()
    to_user = nested_string(data.get("ToUserName")) or str(data.get("toUserName", "")).strip()
    content = nested_string(data.get("Content")) or str(data.get("content", "")).strip()
    push_content = str(data.get("PushContent", data.get("pushContent", ""))).strip()

    if from_user and self_wxid and from_user == self_wxid:
        return NormalizedGewechatMessage(
            text=content,
            sender=from_user,
            reply_target=to_user,
            room_id=from_user if from_user.endswith("@chatroom") else "",
            app_id=app_id,
            source="gewechat",
            ignored=True,
            reason="self message",
        )

    room_id = from_user if from_user.endswith("@chatroom") else ""
    sender = from_user
    text = content
    if room_id and ":\n" in content:
        sender, text = content.split(":\n", 1)
        sender = sender.strip()
        text = text.strip()

    if str(msg_type) != "1":
        text = push_content or f"[non-text message msgType={msg_type}]"

    if not text:
        return NormalizedGewechatMessage(
            text="",
            sender=sender,
            reply_target=room_id or from_user,
            room_id=room_id,
            app_id=app_id,
            source="gewechat",
            ignored=True,
            reason="empty message content",
        )

    return NormalizedGewechatMessage(
        text=text,
        sender=sender,
        reply_target=room_id or from_user,
        room_id=room_id,
        app_id=app_id,
        source="gewechat",
    )


def nested_string(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("string", "")).strip()
    return str(value or "").strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Gewechat bridge helper")
    parser.add_argument("command", choices=["send", "simulate-callback"])
    parser.add_argument("--api-url", default=os.getenv("GEWECHAT_API_URL", DEFAULT_API_URL))
    parser.add_argument("--gateway-url", default=os.getenv("GEWECHAT_GATEWAY_URL", DEFAULT_GATEWAY_URL))
    parser.add_argument("--token", default=os.getenv("GEWECHAT_TOKEN", ""))
    parser.add_argument("--app-id", default=os.getenv("GEWECHAT_APP_ID", "wx_demo_app"))
    parser.add_argument("--to")
    parser.add_argument("--text")
    args = parser.parse_args()

    try:
        if args.command == "send":
            if not args.to or not args.text:
                parser.error("--to and --text are required")
            print(
                json.dumps(
                    send_text(args.app_id, args.to, args.text, api_url=args.api_url, token=args.token),
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return
        if args.command == "simulate-callback":
            payload = {
                "TypeName": "AddMsg",
                "Appid": args.app_id,
                "Wxid": "wxid_self",
                "Data": {
                    "MsgId": 1,
                    "NewMsgId": 1,
                    "MsgType": 1,
                    "FromUserName": {"string": args.to or "wxid_friend"},
                    "ToUserName": {"string": "wxid_self"},
                    "Content": {"string": args.text or "Gewechat callback test"},
                    "PushContent": args.text or "Gewechat callback test",
                },
            }
            print(json.dumps(post_json(args.gateway_url, payload), ensure_ascii=False, indent=2))
    except URLError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": str(exc.reason),
                    "hint": "Gewechat service or gateway is not reachable. Start it first, then retry.",
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
