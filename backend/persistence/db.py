import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_DB_PATH = Path(__file__).resolve().parent.parent / "sessions.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    app_name TEXT NOT NULL,
    task TEXT NOT NULL,
    mode TEXT NOT NULL,
    provider TEXT NOT NULL,
    reasoning_mode TEXT,
    device_serial TEXT,
    status TEXT NOT NULL,
    round_num INTEGER NOT NULL DEFAULT 0,
    task_complete INTEGER NOT NULL DEFAULT 0,
    failure_reason TEXT,
    tokens_used INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd REAL NOT NULL DEFAULT 0.0,
    llm_call_count INTEGER NOT NULL DEFAULT 0,
    escalation_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS session_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    round_num INTEGER NOT NULL,
    action_json TEXT NOT NULL,
    element_sig TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_session_events_session ON session_events(session_id);
"""

# columns update_session() is allowed to write (whitelist — never build SQL from raw kwargs)
_UPDATABLE_COLUMNS = {
    "status",
    "round_num",
    "task_complete",
    "failure_reason",
    "tokens_used",
    "estimated_cost_usd",
    "llm_call_count",
    "escalation_count",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def _create_session(
    session_id: str,
    app_name: str,
    task: str,
    mode: str,
    provider: str,
    reasoning_mode: Optional[str],
    device_serial: Optional[str],
) -> None:
    now = _now()
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO sessions (
                session_id, app_name, task, mode, provider, reasoning_mode,
                device_serial, status, round_num, task_complete, failure_reason,
                tokens_used, estimated_cost_usd, llm_call_count, escalation_count,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'running', 0, 0, NULL, 0, 0.0, 0, 0, ?, ?)
            """,
            (
                session_id,
                app_name,
                task,
                mode,
                provider,
                reasoning_mode,
                device_serial,
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _update_session(session_id: str, fields: dict) -> None:
    sets = {k: v for k, v in fields.items() if k in _UPDATABLE_COLUMNS}
    if not sets:
        return
    sets["updated_at"] = _now()
    conn = _connect()
    try:
        assignments = ", ".join(f"{k} = ?" for k in sets)
        conn.execute(
            f"UPDATE sessions SET {assignments} WHERE session_id = ?",
            (*sets.values(), session_id),
        )
        conn.commit()
    finally:
        conn.close()


def _append_event(
    session_id: str,
    round_num: int,
    action_dict: dict,
    element_sig: Optional[str],
) -> None:
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO session_events (session_id, round_num, action_json, element_sig, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session_id,
                round_num,
                json.dumps(action_dict, default=str),
                element_sig,
                _now(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _get_session(session_id: str) -> Optional[dict]:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        return dict(row) if row is not None else None
    finally:
        conn.close()


def _get_session_events(session_id: str) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM session_events WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _list_sessions(limit: int, offset: int) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _mark_stale_sessions_interrupted() -> int:
    conn = _connect()
    try:
        cur = conn.execute(
            "UPDATE sessions SET status = 'interrupted', updated_at = ? WHERE status = 'running'",
            (_now(),),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


async def create_session(
    session_id: str,
    app_name: str,
    task: str,
    mode: str,
    provider: str,
    reasoning_mode: Optional[str],
    device_serial: Optional[str],
) -> None:
    await asyncio.to_thread(
        _create_session, session_id, app_name, task, mode, provider, reasoning_mode, device_serial
    )


async def update_session(session_id: str, **fields) -> None:
    await asyncio.to_thread(_update_session, session_id, fields)


async def append_event(
    session_id: str, round_num: int, action_dict: dict, element_sig: Optional[str]
) -> None:
    await asyncio.to_thread(_append_event, session_id, round_num, action_dict, element_sig)


async def get_session(session_id: str) -> Optional[dict]:
    return await asyncio.to_thread(_get_session, session_id)


async def get_session_events(session_id: str) -> list[dict]:
    return await asyncio.to_thread(_get_session_events, session_id)


async def list_sessions(limit: int = 50, offset: int = 0) -> list[dict]:
    return await asyncio.to_thread(_list_sessions, limit, offset)


async def mark_stale_sessions_interrupted() -> int:
    return await asyncio.to_thread(_mark_stale_sessions_interrupted)
