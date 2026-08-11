from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from strix_console_service.contracts import CreateScanRequest, ScanSummary
from strix_console_service.provider import ProviderRuntime, ProviderService
from strix_console_service.scan_manager import (
    ProcessAdapter,
    ScanManager,
    StrixProcessAdapter,
    _ScanRecord,
)


class MemoryCredentialStore:
    def __init__(self) -> None:
        self.values = {"StrixConsole/llm/openai": "secret"}

    def get(self, name: str) -> str | None:
        return self.values.get(name)

    def set(self, name: str, value: str) -> None:
        self.values[name] = value


class BlockingProcessAdapter(ProcessAdapter):
    def __init__(self) -> None:
        self.started: list[str] = []
        self.releases: dict[str, threading.Event] = {}
        self.stop_calls: list[str] = []
        self.terminate_calls: list[str] = []

    def run(
        self,
        record: _ScanRecord,
        _provider: ProviderRuntime,
        *,
        on_started: Callable[[int], None],
        on_timeout: Callable[[], None],
    ) -> int:
        del on_timeout
        release = threading.Event()
        self.releases[record.id] = release
        self.started.append(record.id)
        on_started(1000 + len(self.started))
        release.wait(timeout=3)
        return 0

    def stop(self, scan_id: str) -> bool:
        self.stop_calls.append(scan_id)
        release = self.releases.get(scan_id)
        if release is None:
            return False
        release.set()
        return True

    def terminate(self, scan_id: str) -> bool:
        self.terminate_calls.append(scan_id)
        release = self.releases.get(scan_id)
        if release is None:
            return False
        release.set()
        return True


class FailingProcessAdapter(BlockingProcessAdapter):
    def run(
        self,
        record: _ScanRecord,
        provider: ProviderRuntime,
        *,
        on_started: Callable[[int], None],
        on_timeout: Callable[[], None],
    ) -> int:
        del record, provider, on_started, on_timeout
        raise OSError("launch failed")


def _provider(tmp_path: Path) -> ProviderService:
    config_path = tmp_path / "provider.json"
    config_path.write_text(
        '{"provider":"openai","model":"openai/gpt-5","api_base":null,'
        '"connection_verified":true}',
        encoding="utf-8",
    )
    return ProviderService(
        config_path=config_path,
        credential_store=MemoryCredentialStore(),
    )


def _request() -> CreateScanRequest:
    return CreateScanRequest.model_validate(
        {
            "targetType": "web",
            "target": "https://example.com",
            "authorizationConfirmed": True,
        }
    )


def _wait_for(
    manager: ScanManager,
    scan_id: str,
    status: str,
) -> ScanSummary:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        scan = manager.get(scan_id)
        if scan is not None and scan.status == status:
            return scan
        time.sleep(0.01)
    raise AssertionError(f"scan {scan_id} did not reach {status}")


def test_queue_is_idempotent_and_runs_only_one_scan_at_a_time(tmp_path: Path) -> None:
    adapter = BlockingProcessAdapter()
    manager = ScanManager(
        state_path=tmp_path / "queue.json",
        provider_service=_provider(tmp_path),
        process_adapter=adapter,
        readiness=lambda: True,
    )
    manager.start()
    try:
        first = manager.create(_request(), "same-request")
        duplicate = manager.create(_request(), "same-request")
        second = manager.create(_request(), "second-request")

        _wait_for(manager, first.id, "running")
        assert duplicate.id == first.id
        assert manager.get(second.id).status == "queued"  # type: ignore[union-attr]
        assert adapter.started == [first.id]

        adapter.releases[first.id].set()
        _wait_for(manager, second.id, "running")
        adapter.releases[second.id].set()
        _wait_for(manager, second.id, "completed")
    finally:
        manager.close()


def test_safe_stop_and_emergency_termination_are_separate(tmp_path: Path) -> None:
    adapter = BlockingProcessAdapter()
    manager = ScanManager(
        state_path=tmp_path / "queue.json",
        provider_service=_provider(tmp_path),
        process_adapter=adapter,
        readiness=lambda: True,
    )
    manager.start()
    try:
        safe = manager.create(_request(), "safe-stop")
        _wait_for(manager, safe.id, "running")
        manager.stop(safe.id)
        _wait_for(manager, safe.id, "stopped")
        assert adapter.stop_calls == [safe.id]

        emergency = manager.create(_request(), "emergency")
        _wait_for(manager, emergency.id, "running")
        manager.terminate(emergency.id, confirmed=True)
        _wait_for(manager, emergency.id, "terminated")
        assert adapter.terminate_calls == [emergency.id]
    finally:
        manager.close()


def test_failed_startup_never_becomes_running(tmp_path: Path) -> None:
    manager = ScanManager(
        state_path=tmp_path / "queue.json",
        provider_service=_provider(tmp_path),
        process_adapter=FailingProcessAdapter(),
        readiness=lambda: True,
    )
    manager.start()
    try:
        scan = manager.create(_request(), "failed-start")
        failed = _wait_for(manager, scan.id, "failed")
        assert failed.started_at is None
        assert failed.error_code == "processStartFailed"
    finally:
        manager.close()


def test_restart_reconciles_stale_running_state_to_failure(tmp_path: Path) -> None:
    state_path = tmp_path / "queue.json"
    request = _request()
    state_path.write_text(
        json.dumps(
            [
                {
                    "id": "stale-scan",
                    "idempotencyKey": "stale-request",
                    "status": "running",
                    "request": request.model_dump(mode="json", by_alias=True),
                    "constraintInstruction": "scope",
                    "engineRunName": "console-stale-scan",
                    "createdAt": "2026-07-28T02:00:00Z",
                    "updatedAt": "2026-07-28T02:01:00Z",
                    "startedAt": "2026-07-28T02:01:00Z",
                    "processId": 2_147_000_000,
                }
            ]
        ),
        encoding="utf-8",
    )
    manager = ScanManager(
        state_path=state_path,
        provider_service=_provider(tmp_path),
        process_adapter=BlockingProcessAdapter(),
        readiness=lambda: True,
    )

    manager.start()
    try:
        scan = manager.get("stale-scan")
        assert scan is not None
        assert scan.status == "failed"
        assert scan.error_code == "serviceRestarted"
        assert scan.process_id is None
    finally:
        manager.close()


def test_steering_is_written_only_for_a_running_in_scope_scan(tmp_path: Path) -> None:
    adapter = BlockingProcessAdapter()
    run_root = tmp_path / "runs"
    manager = ScanManager(
        state_path=tmp_path / "queue.json",
        provider_service=_provider(tmp_path),
        process_adapter=adapter,
        readiness=lambda: True,
        run_root=run_root,
    )
    manager.start()
    try:
        scan = manager.create(_request(), "steering")
        _wait_for(manager, scan.id, "running")
        response = manager.steer(scan.id, "Focus on the existing authentication flow")

        assert response.accepted
        inbox = run_root / scan.engine_run_name / ".state" / "console-steering.jsonl"
        payload = json.loads(inbox.read_text(encoding="utf-8"))
        assert payload["message"] == "Focus on the existing authentication flow"
    finally:
        adapter.releases.get(scan.id, threading.Event()).set()
        manager.close()


def test_corrupt_queue_is_reported_without_crashing(tmp_path: Path) -> None:
    state_path = tmp_path / "queue.json"
    state_path.write_text("{broken", encoding="utf-8")

    manager = ScanManager(
        state_path=state_path,
        provider_service=_provider(tmp_path),
        process_adapter=BlockingProcessAdapter(),
        readiness=lambda: True,
    )

    assert manager.list_scans().scans == []
    assert manager.load_issue == "invalidScanQueue"


@pytest.mark.parametrize(
    ("run_message", "expected"),
    [
        ("provider returned HTTP 429 rate limit", "providerRateLimited"),
        ("model budget exceeded the cost limit", "budgetExhausted"),
        ("Docker daemon became unavailable", "dockerUnavailable"),
    ],
)
def test_runtime_failures_use_safe_actionable_categories(
    tmp_path: Path,
    run_message: str,
    expected: str,
) -> None:
    run_root = tmp_path / "runs"
    manager = ScanManager(
        state_path=tmp_path / "queue.json",
        provider_service=_provider(tmp_path),
        process_adapter=BlockingProcessAdapter(),
        readiness=lambda: True,
        run_root=run_root,
    )
    scan = manager.create(_request(), f"failure-{expected}")
    record = manager._records[0]
    run_path = run_root / scan.engine_run_name
    run_path.mkdir(parents=True)
    (run_path / "run.json").write_text(
        json.dumps({"status": "failed", "message": run_message}),
        encoding="utf-8",
    )

    assert manager._classify_failure(record, 1) == expected


def test_official_binary_command_does_not_use_custom_run_name_flag(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "strix.exe"
    executable.touch()
    adapter = StrixProcessAdapter(
        run_root=tmp_path / "runs",
        strix_path=str(executable),
        environment={},
    )
    record = _ScanRecord.model_validate(
        {
            "id": "scan-id",
            "idempotencyKey": "request-id",
            "status": "queued",
            "request": _request().model_dump(mode="json", by_alias=True),
            "constraintInstruction": "scope",
            "engineRunName": "console-scan-id",
            "createdAt": "2026-08-10T00:00:00Z",
            "updatedAt": "2026-08-10T00:00:00Z",
        }
    )

    command, environment = adapter._build_command(
        record,
        ProviderRuntime(
            provider="openai",
            model="openai/gpt-5",
            api_base=None,
            api_key="secret",
        ),
    )

    assert "--run-name" not in command
    assert command[command.index("--max-budget-usd") + 1] == "10.0"
    assert command[1:3] == ["--target", "https://example.com"]
    assert environment["PYTHONIOENCODING"] == "utf-8"
    assert environment["PYTHONUTF8"] == "1"

    record.request.options.termination_policy = "strixRules"
    strix_command, _environment = adapter._build_command(
        record,
        ProviderRuntime(
            provider="openai",
            model="openai/gpt-5",
            api_base=None,
            api_key="secret",
        ),
    )
    assert "--max-budget-usd" not in strix_command


def test_source_launcher_uses_configured_strix_python(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "strix" / "interface").mkdir(parents=True)
    (source / "strix" / "interface" / "main.py").touch()
    python = tmp_path / "strix-python.exe"
    python.touch()
    adapter = StrixProcessAdapter(
        run_root=tmp_path / "runs",
        strix_path=str(source),
        python_path=str(python),
        environment={},
    )

    command, python_path = adapter._resolved_launcher()

    assert command == [str(python), "-m", "strix.interface.main"]
    assert python_path == str(source)
