from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from strix_console_service.events import EventStore, RunEventObserver


def test_event_store_replays_without_duplicates_and_redacts(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events")
    first = store.append(
        "scan-1",
        "message.created",
        payload={"content": "Authorization: Bearer secret-value", "token": "secret"},
        source_key="source-1",
    )
    duplicate = store.append(
        "scan-1",
        "message.created",
        payload={"content": "different"},
        source_key="source-1",
    )
    second = store.append("scan-1", "scan.running", source_key="source-2")

    assert duplicate.event_id == first.event_id
    assert store.after("scan-1", first.event_id) == [second]
    serialized = (tmp_path / "events" / "scan-1.jsonl").read_text(encoding="utf-8")
    assert "secret-value" not in serialized
    assert json.loads(serialized.splitlines()[0])["payload"]["token"] == "[REDACTED]"
    reloaded = EventStore(tmp_path / "events")
    replayed = reloaded.append(
        "scan-1",
        "message.created",
        payload={"content": "not appended"},
        source_key="source-1",
    )
    assert replayed.event_id == first.event_id
    assert len(reloaded.after("scan-1", None)) == 2


def test_observer_normalizes_agent_history_and_findings(tmp_path: Path) -> None:
    run_root = tmp_path / "runs"
    state = run_root / "console-test" / ".state"
    state.mkdir(parents=True)
    (state / "agents.json").write_text(
        json.dumps(
            {
                "statuses": {"root": "running"},
                "names": {"root": "strix"},
                "parent_of": {"root": None},
                "metadata": {"root": {"task": "Review the target"}},
            }
        ),
        encoding="utf-8",
    )
    connection = sqlite3.connect(state / "agents.db")
    connection.execute(
        "create table agent_messages "
        "(id integer, session_id text, message_data text, created_at text)"
    )
    connection.execute(
        "insert into agent_messages values (?, ?, ?, ?)",
        (
            1,
            "root",
            json.dumps(
                {
                    "type": "function_call",
                    "call_id": "call-1",
                    "name": "web_search",
                    "arguments": '{"query":"example"}',
                }
            ),
            "2026-07-28T00:00:00Z",
        ),
    )
    connection.commit()
    connection.close()
    (run_root / "console-test" / "vulnerabilities.json").write_text(
        '[{"id":"finding-1","title":"Example","severity":"high"}]',
        encoding="utf-8",
    )

    store = EventStore(tmp_path / "events")
    observer = RunEventObserver(run_root, store)
    observer.refresh("scan-1", "console-test")
    observer.refresh("scan-1", "console-test")

    types = [event.type for event in store.after("scan-1", None)]
    assert types == ["agent.updated", "tool.started", "finding.created"]
