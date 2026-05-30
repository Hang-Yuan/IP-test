from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
import sqlite3
import struct
import sys
import time
import tempfile
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from ctypes import wintypes
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from Crypto.Cipher import AES

try:
    import zstandard
except ImportError:  # pragma: no cover - optional until requirements are installed
    zstandard = None


STAGE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = STAGE_DIR / "data" / "runtime" / "wechat_db_monitor"
DEFAULT_PUSH_URL = "http://127.0.0.1:8791/wechat/inbound"
STATE_SCHEMA_VERSION = 2
DEFAULT_PUSH_TIMEOUT_SECONDS = 900
KEY_CACHE_SEED = {
    "38dc030fbebc984641d0dabaf18f36a0": "345b4f31635dcc8855d8758630281dc83c1b2feffa7f48f8465a8ab047e27346",
    "8f075d7f8cfcd4e9da7fe5e4269d1ace": "3ac975dd323cb9ee7d10c827aac126686d1b6beac67cd023d9b0f41b7868b9a7",
    "ebbf9978d9aaee9530b58a24b74e6962": "d334a1bf8c0224bd2ea789f592e87d3cc0120081e43efba330ae3412fb988f83",
}
KEY_PATTERN = re.compile(rb"x'([0-9a-fA-F]{96})'")
IGNORED_LOCAL_TYPES = {10000}
APP_MESSAGE_LOCAL_TYPES = {49, 4294967345, 21474836529, 25769803825}


@dataclass
class WeixinProcess:
    pid: int
    name: str


@dataclass
class DbKey:
    pid: int
    salt_hex: str
    key_hex: str


@dataclass
class InboxMessage:
    source: str
    db_file: str
    table: str
    local_id: int
    sort_seq: int
    create_time: int
    username: str
    display_name: str
    text: str
    status: int
    local_type: int
    reply_target: str

    @property
    def identity(self) -> str:
        return f"{self.db_file}:{self.table}:{self.local_id}:{self.sort_seq}"


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(wintypes.ULONG)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wintypes.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
    ]


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

CreateToolhelp32Snapshot = kernel32.CreateToolhelp32Snapshot
CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
CreateToolhelp32Snapshot.restype = wintypes.HANDLE

Process32FirstW = kernel32.Process32FirstW
Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
Process32FirstW.restype = wintypes.BOOL

Process32NextW = kernel32.Process32NextW
Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
Process32NextW.restype = wintypes.BOOL

OpenProcess = kernel32.OpenProcess
OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
OpenProcess.restype = wintypes.HANDLE

ReadProcessMemory = kernel32.ReadProcessMemory
ReadProcessMemory.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
ReadProcessMemory.restype = wintypes.BOOL

VirtualQueryEx = kernel32.VirtualQueryEx
VirtualQueryEx.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.POINTER(MEMORY_BASIC_INFORMATION),
    ctypes.c_size_t,
]
VirtualQueryEx.restype = ctypes.c_size_t

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL


TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
PAGE_NOACCESS = 0x01
MAX_USER_ADDRESS = 0x00007FFFFFFEFFFF
READ_CHUNK = 1024 * 1024


def enumerate_processes(name: str = "Weixin.exe") -> list[WeixinProcess]:
    snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        return []
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        processes: list[WeixinProcess] = []
        ok = Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            exe_name = entry.szExeFile
            if exe_name.lower() == name.lower():
                processes.append(WeixinProcess(pid=int(entry.th32ProcessID), name=exe_name))
            ok = Process32NextW(snapshot, ctypes.byref(entry))
        return processes
    finally:
        CloseHandle(snapshot)


def is_readable_page(protect: int) -> bool:
    if protect & PAGE_GUARD:
        return False
    if protect & PAGE_NOACCESS:
        return False
    return True


def read_memory(handle: int, address: int, size: int) -> bytes:
    if size <= 0:
        return b""
    buffer = ctypes.create_string_buffer(size)
    read = ctypes.c_size_t()
    ok = ReadProcessMemory(handle, ctypes.c_void_p(address), buffer, size, ctypes.byref(read))
    if not ok or read.value <= 0:
        return b""
    return buffer.raw[: read.value]


def scan_process_keys(pid: int, target_salts: set[str] | None = None) -> list[DbKey]:
    handle = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not handle:
        return []
    found: dict[str, DbKey] = {}
    try:
        address = 0
        mbi = MEMORY_BASIC_INFORMATION()
        while address < MAX_USER_ADDRESS:
            result = VirtualQueryEx(handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi))
            if not result:
                address += 0x10000
                continue
            base = int(mbi.BaseAddress or address)
            size = int(mbi.RegionSize or 0)
            next_address = base + max(size, 0x1000)
            if mbi.State == MEM_COMMIT and size > 0 and is_readable_page(int(mbi.Protect)):
                offset = 0
                overlap = b""
                while offset < size:
                    chunk_size = min(READ_CHUNK, size - offset)
                    chunk = read_memory(handle, base + offset, chunk_size)
                    haystack = overlap + chunk
                    for matched in KEY_PATTERN.finditer(haystack):
                        value = matched.group(1).decode("ascii").lower()
                        key_hex = value[:64]
                        salt_hex = value[64:]
                        if target_salts and salt_hex not in target_salts:
                            continue
                        found[salt_hex] = DbKey(pid=pid, salt_hex=salt_hex, key_hex=key_hex)
                    if target_salts and target_salts.issubset(found.keys()):
                        return list(found.values())
                    overlap = haystack[-128:]
                    offset += chunk_size
            address = next_address
        return list(found.values())
    finally:
        CloseHandle(handle)


def discover_db_root(account_wxid: str | None = None, explicit_root: str | None = None) -> Path:
    if explicit_root:
        root = Path(explicit_root)
        if root.exists():
            return root
        raise FileNotFoundError(f"WECHAT_DB_ROOT does not exist: {root}")

    env_root = os.getenv("WECHAT_DB_ROOT", "").strip()
    if env_root:
        return discover_db_root(explicit_root=env_root)

    account = account_wxid or os.getenv("WECHAT_ACCOUNT_WXID", "")
    bases = [
        Path.home() / "Documents" / "xwechat_files",
        Path.home() / "Documents" / "WeChat Files",
    ]
    candidates: list[Path] = []
    for base in bases:
        if not base.exists():
            continue
        candidates.extend(base.glob(f"{account}_*/db_storage"))
        candidates.extend(base.glob(f"{account}/db_storage"))
    existing = [path for path in candidates if path.exists()]
    if not existing:
        raise FileNotFoundError(f"could not find db_storage for account {account}")
    return sorted(existing, key=lambda p: len(str(p)))[0]


def target_dbs(db_root: Path) -> list[Path]:
    paths = [
        db_root / "contact" / "contact.db",
        db_root / "session" / "session.db",
    ]
    message_dir = db_root / "message"
    if message_dir.exists():
        paths.extend(sorted(path for path in message_dir.glob("message_*.db") if re.fullmatch(r"message_\d+\.db", path.name)))
    return [path for path in paths if path.exists()]


def db_salt_hex(path: Path) -> str:
    with path.open("rb") as handle:
        return handle.read(16).hex()


def locate_db_keys(db_paths: Iterable[Path], pid: int | None = None) -> dict[str, DbKey]:
    salts = {db_salt_hex(path) for path in db_paths}
    processes = [WeixinProcess(pid=pid, name="Weixin.exe")] if pid else enumerate_processes()
    keys: dict[str, DbKey] = {}
    for process in processes:
        for key in scan_process_keys(process.pid, target_salts=salts - keys.keys()):
            keys[key.salt_hex] = key
        if salts.issubset(keys.keys()):
            break
    missing = salts - keys.keys()
    if missing:
        raise RuntimeError(f"could not find keys for salts: {', '.join(sorted(missing))}")
    return keys


def decrypt_wcdb_file(
    source_path: Path,
    key_hex: str,
    output_path: Path,
    page_size: int = 4096,
    reserve_size: int = 80,
) -> Path:
    key = bytes.fromhex(key_hex)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with source_path.open("rb") as source, output_path.open("wb") as output:
        page_no = 0
        while True:
            page = source.read(page_size)
            if not page:
                break
            if len(page) != page_size:
                break
            page_no += 1
            reserve = page[-reserve_size:]
            iv = reserve[:16]
            if page_no == 1:
                output.write(decrypt_wcdb_page(page, key, reserve_size=reserve_size, first_page=True))
            else:
                output.write(decrypt_wcdb_page(page, key, reserve_size=reserve_size, first_page=False))
    return output_path


def decrypt_wcdb_page(page: bytes, key: bytes, reserve_size: int = 80, first_page: bool = False) -> bytes:
    reserve = page[-reserve_size:]
    iv = reserve[:16]
    if first_page:
        encrypted = page[16:-reserve_size]
        decrypted = AES.new(key, AES.MODE_CBC, iv).decrypt(encrypted)
        return b"SQLite format 3\x00" + decrypted + reserve
    encrypted = page[:-reserve_size]
    decrypted = AES.new(key, AES.MODE_CBC, iv).decrypt(encrypted)
    return decrypted + reserve


def apply_wcdb_wal(
    wal_path: Path,
    decrypted_db_path: Path,
    key_hex: str,
    page_size: int = 4096,
    reserve_size: int = 80,
) -> None:
    if not wal_path.exists() or wal_path.stat().st_size < 32:
        return
    key = bytes.fromhex(key_hex)
    frame_size = 24 + page_size
    wal = wal_path.read_bytes()
    usable = len(wal) - 32
    if usable < frame_size:
        return
    frame_count = usable // frame_size
    frames: list[tuple[int, int, bytes]] = []
    final_commit_size = 0
    final_commit_index = -1
    offset = 32
    for index in range(frame_count):
        header = wal[offset : offset + 24]
        page = wal[offset + 24 : offset + frame_size]
        page_no, commit_size = struct.unpack(">II", header[:8])
        if page_no > 0:
            frames.append((page_no, commit_size, page))
        if commit_size > 0:
            final_commit_size = commit_size
            final_commit_index = index
        offset += frame_size
    if final_commit_index < 0:
        return
    with decrypted_db_path.open("r+b") as output:
        for index, (page_no, _commit_size, page) in enumerate(frames):
            if index > final_commit_index:
                break
            decrypted_page = decrypt_wcdb_page(page, key, reserve_size=reserve_size, first_page=(page_no == 1))
            output.seek((page_no - 1) * page_size)
            output.write(decrypted_page)
        if final_commit_size > 0:
            output.truncate(final_commit_size * page_size)


def snapshot_and_decrypt(
    db_paths: Iterable[Path],
    keys: dict[str, DbKey],
    runtime_dir: Path,
    apply_wal: bool = False,
) -> dict[Path, Path]:
    snapshot_dir = runtime_dir / "snapshots"
    decrypted_dir = runtime_dir / "decrypted"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    decrypted_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[Path, Path] = {}
    for path in db_paths:
        salt = db_salt_hex(path)
        key = keys[salt]
        snapshot = snapshot_dir / f"{path.parent.name}__{path.name}"
        decrypted = decrypted_dir / f"{path.parent.name}__{path.name}"
        shutil.copy2(path, snapshot)
        decrypt_wcdb_file(snapshot, key.key_hex, decrypted)
        wal_path = path.with_name(path.name + "-wal")
        if apply_wal and wal_path.exists():
            wal_snapshot = snapshot_dir / f"{path.parent.name}__{path.name}-wal"
            shutil.copy2(wal_path, wal_snapshot)
            apply_wcdb_wal(wal_snapshot, decrypted, key.key_hex)
        outputs[path] = decrypted
    return outputs


def table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute("select name from sqlite_master where type='table'").fetchall()
        if isinstance(row[0], str)
    }


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        if value.startswith(b"\x28\xb5\x2f\xfd") and zstandard is not None:
            try:
                return as_text(zstandard.ZstdDecompressor().decompress(value))
            except Exception:
                pass
        for encoding in ("utf-8", "utf-16-le", "gb18030"):
            try:
                return value.decode(encoding).rstrip("\x00")
            except UnicodeDecodeError:
                continue
        return ""
    return str(value)


def xml_find_text(content: str, selector: str) -> str:
    if not content.lstrip().startswith("<"):
        return ""
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return ""
    value = root.findtext(selector)
    return value.strip() if value else ""


def message_text_for_local_type(local_type: int, content: str) -> str:
    content = content.strip()
    if local_type == 1:
        return content
    if local_type == 3:
        return "[图片消息] 对方发来了一张图片。"
    if local_type == 47:
        return "[表情消息] 对方发来了一个表情。"
    if local_type in APP_MESSAGE_LOCAL_TYPES:
        title = xml_find_text(content, ".//title")
        app_type = xml_find_text(content, ".//type")
        if app_type == "6":
            return f"[文件消息] 对方发来了文件：{title}" if title else "[文件消息] 对方发来了一个文件。"
        return f"[卡片消息] 对方发来了：{title}" if title else "[卡片消息] 对方发来了一条应用消息。"
    if content:
        return content
    return f"[非文本消息] 对方发来了一条 local_type={local_type} 的消息。"


def load_contacts(contact_db: Path | None) -> dict[str, str]:
    if not contact_db or not contact_db.exists():
        return {}
    connection = sqlite3.connect(contact_db)
    try:
        names = table_names(connection)
        contacts: dict[str, str] = {}
        for table in ("contact", "stranger"):
            if table not in names:
                continue
            for username, remark, nick_name, alias in connection.execute(
                f"select username, remark, nick_name, alias from {quote_identifier(table)}"
            ).fetchall():
                user = as_text(username)
                display = as_text(remark) or as_text(nick_name) or as_text(alias) or user
                if user:
                    contacts[user] = display
        return contacts
    finally:
        connection.close()


def normalize_filter_values(values: Iterable[str] | None) -> set[str]:
    if not values:
        return set()
    normalized: set[str] = set()
    for value in values:
        for item in str(value).split(","):
            item = item.strip()
            if item:
                normalized.add(item)
    return normalized


def contact_allowed(
    username: str,
    display_name: str,
    allowed_users: set[str] | None = None,
    allowed_display_names: set[str] | None = None,
) -> bool:
    users = allowed_users or set()
    names = allowed_display_names or set()
    if not users and not names:
        return True
    return username in users or display_name in names


def load_usernames(message_db: Path) -> list[str]:
    connection = sqlite3.connect(message_db)
    try:
        if "Name2Id" not in table_names(connection):
            return []
        return [as_text(row[0]) for row in connection.execute('select user_name from "Name2Id"').fetchall() if as_text(row[0])]
    finally:
        connection.close()


def message_table_for(username: str) -> str:
    return "Msg_" + hashlib.md5(username.encode("utf-8")).hexdigest()


def read_message_db(
    message_db: Path,
    contacts: dict[str, str],
    allowed_users: set[str] | None = None,
    allowed_display_names: set[str] | None = None,
) -> list[InboxMessage]:
    connection = sqlite3.connect(message_db)
    connection.row_factory = sqlite3.Row
    try:
        names = table_names(connection)
        messages: list[InboxMessage] = []
        for username in load_usernames(message_db):
            table = message_table_for(username)
            display_name = contacts.get(username, username)
            if not contact_allowed(username, display_name, allowed_users, allowed_display_names):
                continue
            if table not in names:
                continue
            query = f"""
                select local_id, local_type, sort_seq, create_time, status, message_content
                from {quote_identifier(table)}
                where real_sender_id != 2
                  and message_content is not null
                order by sort_seq asc, local_id asc
            """
            for row in connection.execute(query).fetchall():
                local_type = int(row["local_type"])
                if local_type in IGNORED_LOCAL_TYPES:
                    continue
                text = message_text_for_local_type(local_type, as_text(row["message_content"]))
                if not text:
                    continue
                messages.append(
                    InboxMessage(
                        source="wechat_db",
                        db_file=message_db.name,
                        table=table,
                        local_id=int(row["local_id"]),
                        sort_seq=int(row["sort_seq"]),
                        create_time=int(row["create_time"]),
                        username=username,
                        display_name=display_name,
                        text=text,
                        status=int(row["status"]),
                        local_type=local_type,
                        reply_target=display_name,
                    )
                )
        return messages
    finally:
        connection.close()


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"seen": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {"seen": {}}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def sort_seq_from_identity(identity: str) -> int:
    try:
        return int(identity.rsplit(":", 1)[1])
    except Exception:
        return 0


def state_high_water_sort_seq(state: dict[str, Any], seen: dict[str, bool]) -> int:
    try:
        stored = int(state.get("high_water_sort_seq", 0))
    except Exception:
        stored = 0
    parsed = max((sort_seq_from_identity(identity) for identity in seen), default=0)
    return max(stored, parsed)


def load_key_cache(path: Path) -> dict[str, DbKey]:
    cache: dict[str, DbKey] = {
        salt: DbKey(pid=0, salt_hex=salt, key_hex=key)
        for salt, key in KEY_CACHE_SEED.items()
    }
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            for salt, item in raw.items():
                key_hex = str(item.get("key_hex", ""))
                if len(salt) == 32 and len(key_hex) == 64:
                    cache[salt] = DbKey(pid=int(item.get("pid", 0)), salt_hex=salt, key_hex=key_hex)
        except Exception:
            pass
    return cache


def save_key_cache(path: Path, cache: dict[str, DbKey]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        salt: {"pid": key.pid, "key_hex": key.key_hex}
        for salt, key in cache.items()
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class WeChatDbMonitor:
    def __init__(
        self,
        db_root: Path,
        runtime_dir: Path,
        pid: int | None = None,
        keep_files: bool = False,
        apply_wal: bool = False,
        allowed_users: Iterable[str] | None = None,
        allowed_display_names: Iterable[str] | None = None,
    ):
        self.db_root = db_root
        self.runtime_dir = runtime_dir
        self.pid = pid
        self.keep_files = keep_files
        self.apply_wal = apply_wal
        self.allowed_users = normalize_filter_values(allowed_users)
        self.allowed_display_names = normalize_filter_values(allowed_display_names)
        self.state_path = runtime_dir / "state.json"
        self.key_cache_path = runtime_dir / "key_cache.json"
        self._key_cache: dict[str, DbKey] = load_key_cache(self.key_cache_path)

    def locate_keys(self, db_paths: list[Path]) -> dict[str, DbKey]:
        salts = {db_salt_hex(path) for path in db_paths}
        missing = salts - self._key_cache.keys()
        if missing:
            try:
                self._key_cache.update(locate_db_keys(db_paths, pid=self.pid))
                save_key_cache(self.key_cache_path, self._key_cache)
            except RuntimeError:
                if not salts.issubset(self._key_cache.keys()):
                    raise
        return {salt: self._key_cache[salt] for salt in salts}

    def read_all(self) -> list[InboxMessage]:
        db_paths = target_dbs(self.db_root)
        if not db_paths:
            raise FileNotFoundError(f"no target dbs found under {self.db_root}")
        keys = self.locate_keys(db_paths)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        work_dir = self.runtime_dir / "last_scan"
        if self.keep_files:
            if work_dir.exists():
                shutil.rmtree(work_dir)
            work_dir.mkdir(parents=True, exist_ok=True)
        else:
            work_dir = Path(tempfile.mkdtemp(prefix="scan_", dir=str(self.runtime_dir)))
        try:
            decrypted = snapshot_and_decrypt(db_paths, keys, work_dir, apply_wal=self.apply_wal)
            contact_db = decrypted.get(self.db_root / "contact" / "contact.db")
            contacts = load_contacts(contact_db)
            messages: list[InboxMessage] = []
            for source, output in decrypted.items():
                if source.parent.name != "message":
                    continue
                messages.extend(
                    read_message_db(
                        output,
                        contacts,
                        allowed_users=self.allowed_users,
                        allowed_display_names=self.allowed_display_names,
                    )
                )
            messages.sort(key=lambda item: (item.sort_seq, item.local_id))
            return messages
        finally:
            if not self.keep_files:
                shutil.rmtree(work_dir, ignore_errors=True)

    def read_all_identities(self) -> set[str]:
        return {message.identity for message in self.read_all()}

    def read_new(self, include_existing: bool = False, limit: int | None = None) -> tuple[list[InboxMessage], bool]:
        state = load_state(self.state_path)
        seen: dict[str, bool] = dict(state.get("seen", {}))
        all_messages = self.read_all()
        high_water_sort_seq = state_high_water_sort_seq(state, seen)
        seeded = False
        if not seen and not include_existing:
            for message in all_messages:
                seen[message.identity] = True
            state["seen"] = seen
            state["high_water_sort_seq"] = max((message.sort_seq for message in all_messages), default=0)
            state["schema_version"] = STATE_SCHEMA_VERSION
            save_state(self.state_path, state)
            return [], True

        if include_existing:
            new_messages = [message for message in all_messages if not seen.get(message.identity)]
        else:
            # Schema changes can expose old message types that were previously invisible.
            # Only messages above the prior high-water mark are allowed to auto-reply.
            new_messages = [
                message
                for message in all_messages
                if not seen.get(message.identity) and message.sort_seq > high_water_sort_seq
            ]
        if limit is not None:
            new_messages = new_messages[-limit:]
        for message in all_messages:
            seen[message.identity] = True
        state["seen"] = seen
        state["high_water_sort_seq"] = max(
            [high_water_sort_seq, *[message.sort_seq for message in all_messages]],
            default=high_water_sort_seq,
        )
        state["schema_version"] = STATE_SCHEMA_VERSION
        state["updated_at"] = int(time.time())
        save_state(self.state_path, state)
        return new_messages, seeded


def post_inbound(message: InboxMessage, push_url: str, auto_send: bool = False) -> dict[str, Any]:
    payload = {
        "source": message.source,
        "event_id": message.identity,
        "from_user": message.display_name or message.username,
        "sender": message.username,
        "reply_target": message.display_name or message.username,
        "reply_target_username": message.username,
        "reply_target_display": message.display_name,
        "text": message.text,
        "auto_send": auto_send,
        "raw": asdict(message),
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        push_url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        try:
            timeout_seconds = int(os.getenv("WECHAT_DB_MONITOR_PUSH_TIMEOUT", str(DEFAULT_PUSH_TIMEOUT_SECONDS)))
        except ValueError:
            timeout_seconds = DEFAULT_PUSH_TIMEOUT_SECONDS
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        return {"ok": False, "error": str(exc)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read inbound text messages from local WeChat 4.x databases.")
    parser.add_argument("mode", choices=["once", "watch"], nargs="?", default="once")
    parser.add_argument("--account", default=os.getenv("WECHAT_ACCOUNT_WXID", ""))
    parser.add_argument("--db-root", default=os.getenv("WECHAT_DB_ROOT", ""))
    parser.add_argument("--runtime-dir", default=str(DEFAULT_RUNTIME_DIR))
    parser.add_argument("--pid", type=int, default=None)
    parser.add_argument("--include-existing", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--interval", type=float, default=3.0)
    parser.add_argument("--seconds", type=float, default=0.0)
    parser.add_argument("--push-url", default=DEFAULT_PUSH_URL)
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--auto-send", action="store_true")
    parser.add_argument("--keep-files", action="store_true")
    parser.add_argument("--apply-wal", action="store_true")
    parser.add_argument("--allow-user", action="append", default=[])
    parser.add_argument("--allow-display", action="append", default=[])
    return parser


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    db_root = discover_db_root(account_wxid=args.account, explicit_root=args.db_root or None)
    monitor = WeChatDbMonitor(
        db_root=db_root,
        runtime_dir=Path(args.runtime_dir),
        pid=args.pid,
        keep_files=args.keep_files,
        apply_wal=args.apply_wal,
        allowed_users=args.allow_user or os.getenv("WECHAT_MONITOR_ALLOW_USERS", "").split(","),
        allowed_display_names=args.allow_display or os.getenv("WECHAT_MONITOR_ALLOW_DISPLAY_NAMES", "").split(","),
    )

    if args.mode == "once":
        messages, seeded = monitor.read_new(include_existing=args.include_existing, limit=args.limit)
        pushed = []
        if args.push:
            pushed = [post_inbound(message, args.push_url, auto_send=args.auto_send) for message in messages]
        print(
            json.dumps(
                {
                    "ok": True,
                    "db_root": str(db_root),
                    "seeded": seeded,
                    "count": len(messages),
                    "messages": [asdict(message) for message in messages],
                    "pushed": pushed,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    start = time.time()
    first = True
    while True:
        try:
            messages, seeded = monitor.read_new(include_existing=args.include_existing and first, limit=args.limit)
            first = False
            for message in messages:
                result: dict[str, Any] | None = None
                if args.push:
                    result = post_inbound(message, args.push_url, auto_send=args.auto_send)
                print(json.dumps({"message": asdict(message), "push": result, "seeded": seeded}, ensure_ascii=False), flush=True)
        except Exception as exc:
            print(json.dumps({"ok": False, "error": str(exc), "source": "wechat_db_monitor"}, ensure_ascii=False), flush=True)
        if args.seconds > 0 and time.time() - start >= args.seconds:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
