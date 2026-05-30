from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any


@dataclass(frozen=True)
class MessageRecord:
    message_id: str
    direction: str
    channel: str
    user_id: str
    text: str
    timestamp: str
    meta: dict[str, Any]


class JsonlStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = Lock()

    def append(
        self,
        direction: str,
        channel: str,
        user_id: str,
        text: str,
        meta: dict[str, Any] | None = None,
    ) -> MessageRecord:
        record = MessageRecord(
            message_id=uuid.uuid4().hex[:12],
            direction=direction,
            channel=channel,
            user_id=user_id,
            text=text,
            timestamp=datetime.now().astimezone().replace(microsecond=0).isoformat(),
            meta=meta or {},
        )
        line = json.dumps(asdict(record), ensure_ascii=False)
        with self.lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        return record

    def records(self, limit: int | None = None) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8", errors="replace").splitlines()
        if limit is not None:
            lines = lines[-limit:]
        records: list[dict[str, Any]] = []
        for line in lines:
            if not line.strip():
                continue
            try:
                records.append(json.loads(line.replace("\x00", "")))
            except json.JSONDecodeError:
                continue
        return records

    def tail(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.records(limit=limit)

    def has_meta_value(
        self,
        key: str,
        value: object,
        *,
        direction: str | None = None,
        channel_prefix: str | None = None,
        limit: int = 5000,
    ) -> bool:
        expected = str(value)
        for record in self.records(limit=limit):
            if direction and record.get("direction") != direction:
                continue
            if channel_prefix and not str(record.get("channel", "")).startswith(channel_prefix):
                continue
            meta = record.get("meta")
            if not isinstance(meta, dict):
                continue
            if str(meta.get(key, "")) == expected:
                return True
        return False
