import asyncio
import json
import sqlite3
from datetime import datetime, timezone

import pytest

from backend.persistence import db


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "sessions.db"
    monkeypatch.setattr(db, "_DB_PATH", db_file)
    return db_file


def _create(session_id, app_name="youtube"):
    asyncio.run(
        db.create_session(
            session_id=session_id,
            app_name=app_name,
            task="t",
            mode="deploy",
            provider="gemini",
            reasoning_mode=None,
            device_serial=None,
        )
    )


def test_create_and_get_session_returns_matching_fields(tmp_db):
    _create("sess-1", "youtube")
    session = asyncio.run(db.get_session("sess-1"))
    assert session is not None
    assert session["session_id"] == "sess-1"
    assert session["app_name"] == "youtube"
    assert session["task"] == "t"
    assert session["mode"] == "deploy"
    assert session["provider"] == "gemini"
    assert session["status"] == "running"
    assert session["round_num"] == 0
    assert session["task_complete"] == 0
    assert session["reasoning_mode"] is None
    assert session["device_serial"] is None
    assert session["created_at"]
    assert session["updated_at"]


def test_get_session_missing_returns_none(tmp_db):
    assert asyncio.run(db.get_session("nope")) is None


def test_update_session_ignores_non_whitelisted_fields(tmp_db):
    _create("sess-1")
    asyncio.run(
        db.update_session(
            "sess-1",
            status="done",
            round_num=7,
            estimated_cost_usd=1.5,
            bogus_field="nope",
        )
    )
    session = asyncio.run(db.get_session("sess-1"))
    assert session["status"] == "done"
    assert session["round_num"] == 7
    assert session["estimated_cost_usd"] == 1.5
    assert "bogus_field" not in session


def test_update_session_with_only_bogus_kwargs_is_noop(tmp_db):
    _create("sess-1")
    asyncio.run(db.update_session("sess-1", totally_bogus=123))
    session = asyncio.run(db.get_session("sess-1"))
    assert session["status"] == "running"
    assert "totally_bogus" not in session


def test_append_event_round_trips_action_json_with_datetime(tmp_db):
    _create("sess-1")
    ts = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    action = {"action": "tap", "element_id": 3, "cost": 1.25, "at": ts}
    asyncio.run(db.append_event("sess-1", 1, action, "sig-abc"))

    events = asyncio.run(db.get_session_events("sess-1"))
    assert len(events) == 1
    event = events[0]
    assert event["session_id"] == "sess-1"
    assert event["round_num"] == 1
    assert event["element_sig"] == "sig-abc"
    parsed = json.loads(event["action_json"])
    assert parsed["action"] == "tap"
    assert parsed["element_id"] == 3
    assert parsed["cost"] == 1.25
    assert parsed["at"] == "2026-01-02 03:04:05+00:00"


def test_session_events_round_trip_in_insertion_order(tmp_db):
    _create("sess-1")
    asyncio.run(db.append_event("sess-1", 1, {"action": "tap"}, "s1"))
    asyncio.run(db.append_event("sess-1", 2, {"action": "text"}, "s2"))
    events = asyncio.run(db.get_session_events("sess-1"))
    assert [e["round_num"] for e in events] == [1, 2]
    assert [e["element_sig"] for e in events] == ["s1", "s2"]


def test_list_sessions_orders_by_created_at_desc_and_pages(tmp_db):
    _create("s1", "youtube")
    _create("s2", "gmail")
    _create("s3", "maps")

    conn = sqlite3.connect(db._DB_PATH)
    try:
        for i, sid in enumerate(["s1", "s2", "s3"]):
            conn.execute(
                "UPDATE sessions SET created_at = ? WHERE session_id = ?",
                (f"2026-01-0{i + 1}T00:00:00+00:00", sid),
            )
        conn.commit()
    finally:
        conn.close()

    all_sessions = asyncio.run(db.list_sessions())
    assert [s["session_id"] for s in all_sessions] == ["s3", "s2", "s1"]
    page = asyncio.run(db.list_sessions(limit=1, offset=1))
    assert [s["session_id"] for s in page] == ["s2"]


def test_mark_stale_sessions_interrupted_only_touches_running(tmp_db):
    _create("r1")
    _create("r2")
    _create("done-1")
    _create("error-1")
    asyncio.run(db.update_session("done-1", status="done"))
    asyncio.run(db.update_session("error-1", status="error"))

    changed = asyncio.run(db.mark_stale_sessions_interrupted())
    assert changed == 2
    assert asyncio.run(db.get_session("r1"))["status"] == "interrupted"
    assert asyncio.run(db.get_session("r2"))["status"] == "interrupted"
    assert asyncio.run(db.get_session("done-1"))["status"] == "done"
    assert asyncio.run(db.get_session("error-1"))["status"] == "error"
