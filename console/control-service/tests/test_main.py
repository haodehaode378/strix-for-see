from __future__ import annotations

import pytest

from strix_console_service import main


def test_windows_parent_watch_waits_without_sending_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waited_for: list[int] = []

    monkeypatch.setattr(main.os, "name", "nt")
    monkeypatch.setattr(
        main,
        "_wait_for_windows_parent_exit",
        lambda parent_pid: waited_for.append(parent_pid),
    )
    monkeypatch.setattr(
        main.os,
        "_exit",
        lambda code: (_ for _ in ()).throw(SystemExit(code)),
    )

    with pytest.raises(SystemExit, match="0"):
        main._exit_when_parent_stops(42)

    assert waited_for == [42]
