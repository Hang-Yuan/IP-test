from __future__ import annotations

import hashlib
import html
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass


@dataclass(frozen=True)
class WeChatTextMessage:
    to_user: str
    from_user: str
    content: str


def check_signature(token: str, timestamp: str, nonce: str, signature: str) -> bool:
    if not token:
        return True
    joined = "".join(sorted([token, timestamp, nonce]))
    digest = hashlib.sha1(joined.encode("utf-8")).hexdigest()
    return digest == signature


def parse_text_message(payload: str) -> WeChatTextMessage:
    root = ET.fromstring(payload)

    def get(tag: str) -> str:
        node = root.find(tag)
        return node.text if node is not None and node.text else ""

    return WeChatTextMessage(
        to_user=get("ToUserName"),
        from_user=get("FromUserName"),
        content=get("Content").strip(),
    )


def text_reply(to_user: str, from_user: str, content: str) -> str:
    return (
        "<xml>"
        f"<ToUserName><![CDATA[{html.escape(to_user)}]]></ToUserName>"
        f"<FromUserName><![CDATA[{html.escape(from_user)}]]></FromUserName>"
        f"<CreateTime>{int(time.time())}</CreateTime>"
        "<MsgType><![CDATA[text]]></MsgType>"
        f"<Content><![CDATA[{content}]]></Content>"
        "</xml>"
    )
