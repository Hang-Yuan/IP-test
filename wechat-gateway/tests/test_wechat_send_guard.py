import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gateway import server
from gateway.store import JsonlStore


class WeChatSendGuardTests(unittest.TestCase):
    def tearDown(self) -> None:
        for name in (
            "WECHAT_AUTO_SEND_ALLOW_TARGETS",
            "WECHAT_AUTO_SEND_ALLOW_USERS",
            "WECHAT_AUTO_SEND_ALLOW_DISPLAY_NAMES",
            "WECHAT_AUTO_SEND_BLOCK_TARGETS",
        ):
            os.environ.pop(name, None)

    def test_rejects_broadcast_and_multi_target_names(self) -> None:
        self.assertEqual(server.target_validation_error("所有人"), "broadcast target is not allowed")
        self.assertEqual(server.target_validation_error("alice,bob"), "target must be exactly one chat")

    def test_auto_send_allows_current_inbound_chat_without_static_allowlist(self) -> None:
        payload = {"raw": {"username": "wxid_test_friend", "display_name": "alice"}}

        self.assertEqual(server.auto_send_block_reason(payload, "alice", "alice", ""), "")

    def test_optional_allowlist_can_still_restrict_targets(self) -> None:
        payload = {"raw": {"username": "wxid_test_friend", "display_name": "alice"}}
        os.environ["WECHAT_AUTO_SEND_ALLOW_TARGETS"] = "bob"
        self.assertEqual(
            server.auto_send_block_reason(payload, "alice", "alice", ""),
            "target is outside WECHAT_AUTO_SEND_ALLOW_TARGETS",
        )
        os.environ["WECHAT_AUTO_SEND_ALLOW_TARGETS"] = "alice"
        self.assertEqual(server.auto_send_block_reason(payload, "alice", "alice", ""), "")

    def test_auto_send_target_must_match_current_inbound_chat(self) -> None:
        os.environ["WECHAT_AUTO_SEND_ALLOW_TARGETS"] = "alice,bob"
        payload = {"raw": {"username": "wxid_test_friend", "display_name": "alice"}}

        self.assertEqual(
            server.auto_send_block_reason(payload, "alice", "bob", ""),
            "reply_target must match the current inbound chat",
        )

    def test_auto_send_blocks_bridge_self_loops(self) -> None:
        os.environ["WECHAT_AUTO_SEND_ALLOW_TARGETS"] = "微信ClawBot"
        payload = {"raw": {"username": "mmo9cq80yfHylgYFzC9HQnK6JQZWsw@weclaw", "display_name": "微信ClawBot"}}

        self.assertEqual(
            server.auto_send_block_reason(payload, "微信ClawBot", "微信ClawBot", ""),
            "target is blocked from auto send",
        )

    def test_auto_send_blocks_duplicate_inbound_event_send_attempts(self) -> None:
        os.environ["WECHAT_AUTO_SEND_ALLOW_TARGETS"] = "alice"
        payload = {"raw": {"username": "wxid_test_friend", "display_name": "alice"}}
        inbound_key = "wechat_db:message__message_0.db:Msg_x:7:1780163834000"

        with tempfile.TemporaryDirectory() as temp_dir:
            store = JsonlStore(Path(temp_dir) / "messages.jsonl")
            store.append(
                direction="out",
                channel="wechat_keyboard",
                user_id="alice",
                text="already sent",
                meta={"inbound_event_key": inbound_key},
            )
            with patch.object(server, "STORE", store):
                self.assertEqual(
                    server.auto_send_block_reason(payload, "alice", "alice", "", inbound_key),
                    "inbound event already has a send attempt",
                )


if __name__ == "__main__":
    unittest.main()
