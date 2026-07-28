from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from strix_console_service.contracts import EventActor, ScanEvent
from strix_console_service.system_checks import redact_text

_SECRET_VALUE = re.compile(
    r"(?i)(Bearer\s+)[^\s,;]+|"
    r"((?:api[_-]?key|token|password|secret|cookie)\s*[:=]\s*)[^\s,;]+"
)


def redact_event_value(value: Any) -> Any:
    """Return a bounded, browser-safe copy of untrusted engine output."""

    if isinstance(value, str):
        text = redact_text(value, home=Path.home())
        text = _SECRET_VALUE.sub(
            lambda match: f"{match.group(1) or match.group(2)}[REDACTED]",
            text,
        )
        return text[:4000] + ("…" if len(text) > 4000 else "")
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for key, item in list(value.items())[:100]:
            if str(key).casefold() in {
                "authorization",
                "api_key",
                "apikey",
                "cookie",
                "password",
                "secret",
                "token",
            }:
                safe[str(key)] = "[REDACTED]"
            else:
                safe[str(key)] = redact_event_value(item)
        return safe
    if isinstance(value, list):
        return [redact_event_value(item) for item in value[:100]]
    if isinstance(value, int | float | bool) or value is None:
        return value
    return redact_event_value(str(value))


class EventStore:
    """Append-only per-scan JSONL event store with replay and source deduplication."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._events: dict[str, list[ScanEvent]] = {}
        self._source_keys: dict[str, set[str]] = {}
        self._conditions: dict[str, threading.Condition] = {}
        self._lock = threading.RLock()

    def append(
        self,
        scan_id: str,
        event_type: str,
        *,
        actor: EventActor | None = None,
        payload: dict[str, Any] | None = None,
        source_key: str | None = None,
    ) -> ScanEvent:
        with self._lock:
            events, source_keys = self._load(scan_id)
            if source_key and source_key in source_keys:
                return next(event for event in events if event.source_key == source_key)
            event = ScanEvent(
                event_id=str(len(events) + 1),
                scan_id=scan_id,
                occurred_at=datetime.now(UTC),
                type=event_type,
                actor=actor,
                payload=redact_event_value(payload or {}),
                source_key=source_key,
            )
            self.root.mkdir(parents=True, exist_ok=True)
            with self._path(scan_id).open("a", encoding="utf-8", newline="\n") as handle:
                persisted = event.model_dump(mode="json", by_alias=True)
                persisted["_sourceKey"] = source_key
                handle.write(json.dumps(persisted, ensure_ascii=False) + "\n")
            events.append(event)
            if source_key:
                source_keys.add(source_key)
            self._condition(scan_id).notify_all()
            return event

    def after(self, scan_id: str, last_event_id: str | None, limit: int = 500) -> list[ScanEvent]:
        with self._lock:
            events, _source_keys = self._load(scan_id)
            try:
                cursor = max(int(last_event_id or "0"), 0)
            except ValueError:
                cursor = 0
            return events[cursor : cursor + limit]

    def wait_after(
        self,
        scan_id: str,
        last_event_id: str | None,
        timeout: float = 15,
    ) -> list[ScanEvent]:
        with self._lock:
            available = self.after(scan_id, last_event_id)
            if available:
                return available
            self._condition(scan_id).wait(timeout=timeout)
            return self.after(scan_id, last_event_id)

    def _load(self, scan_id: str) -> tuple[list[ScanEvent], set[str]]:
        if scan_id in self._events:
            return self._events[scan_id], self._source_keys[scan_id]
        events: list[ScanEvent] = []
        path = self._path(scan_id)
        if path.is_file():
            try:
                for line in path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        value = json.loads(line)
                        source_key = value.pop("_sourceKey", None)
                        events.append(
                            ScanEvent.model_validate(
                                {**value, "sourceKey": source_key},
                            )
                        )
            except (OSError, UnicodeDecodeError, ValueError):
                events = []
        self._events[scan_id] = events
        self._source_keys[scan_id] = {
            event.source_key for event in events if event.source_key is not None
        }
        return events, self._source_keys[scan_id]

    def _path(self, scan_id: str) -> Path:
        return self.root / f"{scan_id}.jsonl"

    def _condition(self, scan_id: str) -> threading.Condition:
        return self._conditions.setdefault(scan_id, threading.Condition(self._lock))


class RunEventObserver:
    """Normalize authoritative Strix run files into stable console events."""

    def __init__(self, run_root: Path, store: EventStore) -> None:
        self.run_root = run_root.resolve()
        self.store = store

    def refresh(self, scan_id: str, engine_run_name: str) -> None:
        run_dir = (self.run_root / engine_run_name).resolve()
        if run_dir.parent != self.run_root:
            return
        state_dir = run_dir / ".state"
        agents = self._json(state_dir / "agents.json", {})
        if isinstance(agents, dict):
            self._agents(scan_id, agents)
        self._history(scan_id, state_dir / "agents.db")
        vulnerabilities = self._json(run_dir / "vulnerabilities.json", [])
        if isinstance(vulnerabilities, list):
            for index, finding in enumerate(vulnerabilities):
                if isinstance(finding, dict):
                    finding_id = str(finding.get("id") or finding.get("title") or index)
                    self.store.append(
                        scan_id,
                        "finding.created",
                        payload=finding,
                        source_key=f"finding:{finding_id}",
                    )
        record = self._json(run_dir / "run.json", {})
        if isinstance(record, dict) and isinstance(record.get("llm_usage"), dict):
            usage = record["llm_usage"]
            self.store.append(
                scan_id,
                "usage.updated",
                payload=usage,
                source_key=f"usage:{json.dumps(usage, sort_keys=True, default=str)}",
            )

    def _agents(self, scan_id: str, data: dict[str, Any]) -> None:
        statuses = data.get("statuses")
        names = data.get("names")
        parents = data.get("parent_of")
        metadata = data.get("metadata")
        if not isinstance(statuses, dict):
            return
        for agent_id, status in statuses.items():
            if not isinstance(agent_id, str):
                continue
            payload = {
                "id": agent_id,
                "name": names.get(agent_id, agent_id) if isinstance(names, dict) else agent_id,
                "parentId": parents.get(agent_id) if isinstance(parents, dict) else None,
                "status": str(status),
                "task": (
                    metadata.get(agent_id, {}).get("task", "")
                    if isinstance(metadata, dict)
                    and isinstance(metadata.get(agent_id), dict)
                    else ""
                ),
            }
            self.store.append(
                scan_id,
                "agent.updated",
                actor=EventActor(kind="agent", id=agent_id),
                payload=payload,
                source_key=f"agent:{agent_id}:{json.dumps(payload, sort_keys=True)}",
            )

    def _history(self, scan_id: str, database: Path) -> None:
        if not database.is_file():
            return
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True, timeout=1)
            rows = connection.execute(
                "select id, session_id, message_data, created_at "
                "from agent_messages order by id"
            ).fetchall()
        except sqlite3.Error:
            return
        finally:
            if connection is not None:
                connection.close()
        for row_id, agent_id, raw, created_at in rows:
            try:
                item = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(item, dict):
                continue
            actor = EventActor(kind="agent", id=str(agent_id))
            item_type = item.get("type")
            if item_type == "function_call":
                self.store.append(
                    scan_id,
                    "tool.started",
                    actor=actor,
                    payload={
                        "callId": item.get("call_id") or item.get("id"),
                        "toolName": item.get("name") or "tool",
                        "arguments": self._parse(item.get("arguments")),
                        "occurredAt": created_at,
                    },
                    source_key=f"history:{row_id}",
                )
            elif item_type == "function_call_output":
                self.store.append(
                    scan_id,
                    "tool.completed",
                    actor=actor,
                    payload={
                        "callId": item.get("call_id") or item.get("id"),
                        "result": self._parse(item.get("output")),
                        "occurredAt": created_at,
                    },
                    source_key=f"history:{row_id}",
                )
            elif item.get("role") in {"user", "assistant"}:
                self.store.append(
                    scan_id,
                    "message.created",
                    actor=actor,
                    payload={
                        "role": item.get("role"),
                        "content": self._message_text(item.get("content")),
                        "occurredAt": created_at,
                    },
                    source_key=f"history:{row_id}",
                )

    @staticmethod
    def _json(path: Path, default: Any) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return default

    @staticmethod
    def _parse(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    @staticmethod
    def _message_text(value: Any) -> str:
        if isinstance(value, str):
            return value
        if not isinstance(value, list):
            return ""
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)


def sse_frames(events: list[ScanEvent]) -> Iterator[str]:
    for event in events:
        yield (
            f"id: {event.event_id}\n"
            f"event: {event.type}\n"
            f"data: {event.model_dump_json(by_alias=True)}\n\n"
        )


def heartbeat_frame() -> str:
    return f": keepalive {int(time.time())}\n\n"
