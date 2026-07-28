from __future__ import annotations

import asyncio
import contextlib
import json
from typing import TYPE_CHECKING

from strix.core.console_bridge import watch_console_steering


if TYPE_CHECKING:
    from pathlib import Path


class FakeCoordinator:
    def __init__(self) -> None:
        self.messages: list[tuple[str, dict[str, str]]] = []

    async def send(self, agent_id: str, message: dict[str, str]) -> bool:
        self.messages.append((agent_id, message))
        return True


def test_console_bridge_delivers_each_message_once(tmp_path: Path) -> None:
    async def exercise() -> None:
        inbox = tmp_path / "console-steering.jsonl"
        inbox.write_text(
            json.dumps({"id": "message-1", "message": "Focus on authentication"}) + "\n",
            encoding="utf-8",
        )
        coordinator = FakeCoordinator()
        task = asyncio.create_task(
            watch_console_steering(tmp_path, coordinator, "root"),
        )
        await asyncio.sleep(0.35)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

        assert len(coordinator.messages) == 1
        assert coordinator.messages[0][0] == "root"
        assert "message-1" in (tmp_path / "console-steering-ack.jsonl").read_text(
            encoding="utf-8"
        )

    asyncio.run(exercise())
