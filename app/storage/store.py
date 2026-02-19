from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SessionRecord:
    id: str
    title: str
    cwd: Optional[str]
    parent_session_id: Optional[str]
    created_ts_ms: int


@dataclass
class RunRecord:
    id: str
    session_id: str
    status: str  # idle|starting|running|paused|completed|failed|cancelled
    created_ts_ms: int
    updated_ts_ms: int
    model: Optional[str]
    auto_approve: bool
    max_steps: int
    allowed_tools: Optional[str]  # JSON string


class Store:
    """Very small SQLite-backed store (single-file)."""

    def __init__(self, path: str = "./data.db"):
        self.path = str(Path(path))
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._init()

    def _init(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    cwd TEXT,
                    parent_session_id TEXT,
                    created_ts_ms INTEGER NOT NULL
                );
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_ts_ms INTEGER NOT NULL,
                    updated_ts_ms INTEGER NOT NULL,
                    model TEXT,
                    auto_approve INTEGER NOT NULL,
                    max_steps INTEGER NOT NULL,
                    allowed_tools TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_ts_ms INTEGER NOT NULL,
                    run_id TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    ts_ms INTEGER NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_session_ts ON events(session_id, ts_ms);"
            )

    @staticmethod
    def _now_ms() -> int:
        return int(time.time() * 1000)

    @staticmethod
    def _uuid() -> str:
        return str(uuid.uuid4())

    # ---------------- Sessions ----------------

    def create_session(self, title: str, cwd: Optional[str], parent_session_id: Optional[str]) -> SessionRecord:
        sid = self._uuid()
        rec = SessionRecord(
            id=sid,
            title=title,
            cwd=cwd,
            parent_session_id=parent_session_id,
            created_ts_ms=self._now_ms(),
        )
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO sessions(id,title,cwd,parent_session_id,created_ts_ms) VALUES(?,?,?,?,?)",
                (rec.id, rec.title, rec.cwd, rec.parent_session_id, rec.created_ts_ms),
            )
        return rec

    def get_session(self, session_id: str) -> Optional[SessionRecord]:
        with self._lock:
            row = self._conn.execute(
                "SELECT id,title,cwd,parent_session_id,created_ts_ms FROM sessions WHERE id=?",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        return SessionRecord(*row)

    def list_sessions(self, parent_session_id: Optional[str] = None, limit: int = 100) -> List[SessionRecord]:
        with self._lock:
            if parent_session_id is None:
                rows = self._conn.execute(
                    "SELECT id,title,cwd,parent_session_id,created_ts_ms FROM sessions ORDER BY created_ts_ms DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT id,title,cwd,parent_session_id,created_ts_ms FROM sessions WHERE parent_session_id=? ORDER BY created_ts_ms DESC LIMIT ?",
                    (parent_session_id, limit),
                ).fetchall()
        return [SessionRecord(*r) for r in rows]

    def delete_session(self, session_id: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM events WHERE session_id=?", (session_id,))
            self._conn.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
            self._conn.execute("DELETE FROM runs WHERE session_id=?", (session_id,))
            self._conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))

    # ---------------- Runs ----------------

    def create_run(
        self,
        session_id: str,
        model: Optional[str],
        auto_approve: bool,
        max_steps: int,
        allowed_tools_json: Optional[str],
    ) -> RunRecord:
        rid = self._uuid()
        now = self._now_ms()
        rec = RunRecord(
            id=rid,
            session_id=session_id,
            status="starting",
            created_ts_ms=now,
            updated_ts_ms=now,
            model=model,
            auto_approve=auto_approve,
            max_steps=max_steps,
            allowed_tools=allowed_tools_json,
        )
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO runs(id,session_id,status,created_ts_ms,updated_ts_ms,model,auto_approve,max_steps,allowed_tools)
                VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    rec.id,
                    rec.session_id,
                    rec.status,
                    rec.created_ts_ms,
                    rec.updated_ts_ms,
                    rec.model,
                    1 if rec.auto_approve else 0,
                    rec.max_steps,
                    rec.allowed_tools,
                ),
            )
        return rec

    def update_run_status(self, run_id: str, status: str) -> None:
        now = self._now_ms()
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE runs SET status=?, updated_ts_ms=? WHERE id=?",
                (status, now, run_id),
            )

    def get_latest_run(self, session_id: str) -> Optional[RunRecord]:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT id,session_id,status,created_ts_ms,updated_ts_ms,model,auto_approve,max_steps,allowed_tools
                FROM runs WHERE session_id=? ORDER BY created_ts_ms DESC LIMIT 1
                """,
                (session_id,),
            ).fetchone()
        if not row:
            return None
        rid, sid, status, created, updated, model, auto_approve, max_steps, allowed = row
        return RunRecord(
            id=rid,
            session_id=sid,
            status=status,
            created_ts_ms=created,
            updated_ts_ms=updated,
            model=model,
            auto_approve=bool(auto_approve),
            max_steps=int(max_steps),
            allowed_tools=allowed,
        )

    # ---------------- Messages ----------------

    def add_message(self, session_id: str, role: str, content: str, run_id: Optional[str] = None) -> str:
        mid = self._uuid()
        now = self._now_ms()
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO messages(id,session_id,role,content,created_ts_ms,run_id) VALUES(?,?,?,?,?,?)",
                (mid, session_id, role, content, now, run_id),
            )
        return mid

    def list_messages(self, session_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id,role,content,created_ts_ms,run_id
                FROM messages WHERE session_id=?
                ORDER BY created_ts_ms ASC LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [
            {"id": r[0], "role": r[1], "content": r[2], "created_ts_ms": r[3], "run_id": r[4]}
            for r in rows
        ]

    # ---------------- Events ----------------

    def add_event(self, session_id: str, event_id: str, type_: str, payload_json: str, ts_ms: int) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO events(id,session_id,type,payload_json,ts_ms) VALUES(?,?,?,?,?)",
                (event_id, session_id, type_, payload_json, ts_ms),
            )

    def list_events_since(self, session_id: str, since_ts_ms: int, limit: int = 500) -> List[Tuple[str, str, str, int]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id,type,payload_json,ts_ms
                FROM events WHERE session_id=? AND ts_ms>=?
                ORDER BY ts_ms ASC LIMIT ?
                """,
                (session_id, since_ts_ms, limit),
            ).fetchall()
        return [(r[0], r[1], r[2], r[3]) for r in rows]
