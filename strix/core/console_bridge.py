"""Local run-directory bridge for Console steering messages."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from pathlib import Path

    from strix.core.agents import AgentCoordinator


logger = logging.getLogger(__name__)


async def watch_console_steering(
    state_dir: Path,
    coordinator: AgentCoordinator,
    root_id: str,
) -> None:
    """Deliver new validated Console inbox entries to the live root session."""

    inbox = state_dir / "console-steering.jsonl"
    acknowledgements = state_dir / "console-steering-ack.jsonl"
    delivered = _acknowledged_ids(acknowledgements)
    while True:
        for entry in _read_entries(inbox):
            message_id = entry.get("id")
            message = entry.get("message")
            if (
                not isinstance(message_id, str)
                or not isinstance(message, str)
                or not message.strip()
                or len(message) > 2000
                or message_id in delivered
            ):
                continue
            if await coordinator.send(
                root_id,
                {
                    "from": "user",
                    "type": "instruction",
                    "priority": "high",
                    "content": message.strip(),
                },
            ):
                delivered.add(message_id)
                _append_ack(acknowledgements, message_id)
                logger.info("Delivered Console steering message %s to root agent", message_id)
        await asyncio.sleep(0.25)


def _read_entries(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    entries: list[dict[str, Any]] = []
    for line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            entries.append(value)
    return entries


def _acknowledged_ids(path: Path) -> set[str]:
    return {
        message_id
        for entry in _read_entries(path)
        if isinstance((message_id := entry.get("id")), str)
    }


def _append_ack(path: Path, message_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps({"id": message_id}) + "\n")
