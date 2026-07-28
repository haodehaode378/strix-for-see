from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path

from strix_console_service.contracts import AuditSummary

_MAX_EVENTS = 1000


class AuditLog:
    """Append-only local mutation log that never records bodies, targets, or credentials."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def append(self, action: str, outcome: str) -> None:
        entry = {
            "occurredAt": datetime.now(UTC).isoformat(),
            "action": action,
            "outcome": outcome,
        }
        with self._lock:
            entries, _ = self._read()
            entries.append(entry)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(
                "\n".join(
                    json.dumps(item, separators=(",", ":"))
                    for item in entries[-_MAX_EVENTS:]
                )
                + "\n",
                encoding="utf-8",
            )
            temporary.replace(self.path)

    def summary(self) -> AuditSummary:
        with self._lock:
            entries, corrupt = self._read()
        return AuditSummary(
            total_events=len(entries),
            corrupt_entries=corrupt,
            recent_actions=[str(item["action"]) for item in entries[-20:]],
        )

    def _read(self) -> tuple[list[dict[str, str]], int]:
        if not self.path.is_file():
            return [], 0
        entries: list[dict[str, str]] = []
        corrupt = 0
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            return [], 1
        for line in lines:
            try:
                item = json.loads(line)
                if not isinstance(item, dict) or not isinstance(item.get("action"), str):
                    raise ValueError
                entries.append(item)
            except (json.JSONDecodeError, ValueError):
                corrupt += 1
        return entries, corrupt
