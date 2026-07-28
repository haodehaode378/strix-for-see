from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol
from urllib.parse import urlsplit, urlunsplit

from strix_console_service.contracts import (
    CamelModel,
    CreateScanRequest,
    ScanListResponse,
    ScanStatus,
    ScanSummary,
)
from strix_console_service.provider import ProviderRuntime, ProviderService
from strix_console_service.scan_validation import validate_scan_request
from strix_console_service.system_checks import redact_text

_ACTIVE_STATUSES: set[ScanStatus] = {
    "preparing",
    "running",
    "reporting",
    "stopping",
    "terminating",
}
_TERMINAL_STATUSES: set[ScanStatus] = {
    "completed",
    "stopped",
    "terminated",
    "failed",
}


class ScanManagerError(ValueError):
    """Stable queue or lifecycle error safe to return as an error code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _ScanRecord(CamelModel):
    id: str
    idempotency_key: str
    status: ScanStatus
    request: CreateScanRequest
    constraint_instruction: str
    engine_run_name: str
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    ended_at: datetime | None = None
    process_id: int | None = None
    error_code: str | None = None
    stop_requested: bool = False
    terminate_requested: bool = False


class ProcessAdapter(Protocol):
    """Execution boundary for one resolved Strix child process."""

    def run(
        self,
        record: _ScanRecord,
        provider: ProviderRuntime,
        *,
        on_started: Callable[[int], None],
        on_timeout: Callable[[], None],
    ) -> int: ...

    def stop(self, scan_id: str) -> bool: ...

    def terminate(self, scan_id: str) -> bool: ...


class StrixProcessAdapter:
    """Start Strix without a shell and control only tracked child handles."""

    def __init__(
        self,
        *,
        run_root: Path,
        strix_path: str | None,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self.run_root = run_root.resolve()
        self.strix_path = strix_path
        self.base_environment = dict(environment if environment is not None else os.environ)
        self._processes: dict[str, subprocess.Popen[bytes]] = {}
        self._lock = threading.Lock()

    def run(
        self,
        record: _ScanRecord,
        provider: ProviderRuntime,
        *,
        on_started: Callable[[int], None],
        on_timeout: Callable[[], None],
    ) -> int:
        command, child_environment = self._build_command(record, provider)
        self.run_root.mkdir(parents=True, exist_ok=True)
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        process = subprocess.Popen(  # noqa: S603
            command,
            cwd=self.run_root.parent,
            env=child_environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            close_fds=True,
            creationflags=creation_flags,
        )
        with self._lock:
            self._processes[record.id] = process
        on_started(process.pid)

        deadline = time.monotonic() + record.request.options.max_duration_minutes * 60
        timeout_sent = False
        try:
            while True:
                return_code = process.poll()
                if return_code is not None:
                    return return_code
                if not timeout_sent and time.monotonic() >= deadline:
                    timeout_sent = True
                    on_timeout()
                    self.stop(record.id)
                time.sleep(0.25)
        finally:
            with self._lock:
                self._processes.pop(record.id, None)

    def stop(self, scan_id: str) -> bool:
        process = self._tracked_process(scan_id)
        if process is None or process.poll() is not None:
            return False
        try:
            if os.name == "nt":
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                process.send_signal(signal.SIGINT)
        except OSError:
            return False
        return True

    def terminate(self, scan_id: str) -> bool:
        process = self._tracked_process(scan_id)
        if process is None or process.poll() is not None:
            return False
        try:
            process.kill()
        except OSError:
            return False
        return True

    def _tracked_process(self, scan_id: str) -> subprocess.Popen[bytes] | None:
        with self._lock:
            return self._processes.get(scan_id)

    def _build_command(
        self,
        record: _ScanRecord,
        provider: ProviderRuntime,
    ) -> tuple[list[str], dict[str, str]]:
        command, python_path = self._resolved_launcher()
        request = record.request
        instruction = record.constraint_instruction
        if request.options.instructions:
            instruction = f"{instruction}\n\n[OPERATOR FOCUS]\n{request.options.instructions}"
        command.extend(
            [
                "--target",
                request.target,
                "--non-interactive",
                "--scan-mode",
                request.options.scan_profile,
                "--max-budget-usd",
                str(request.options.max_budget_usd),
                "--run-name",
                record.engine_run_name,
                "--instruction",
                instruction,
            ]
        )

        environment = dict(self.base_environment)
        environment.update(
            {
                "STRIX_LLM": provider.model,
                "STRIX_RUNS_DIR": str(self.run_root),
                "STRIX_TELEMETRY": "false",
            }
        )
        if provider.api_key:
            environment["LLM_API_KEY"] = provider.api_key
        if provider.api_base:
            environment["LLM_API_BASE"] = provider.api_base
        if python_path:
            existing = environment.get("PYTHONPATH")
            environment["PYTHONPATH"] = (
                f"{python_path}{os.pathsep}{existing}" if existing else python_path
            )
        return command, environment

    def _resolved_launcher(self) -> tuple[list[str], str | None]:
        candidate = self.strix_path or shutil.which("strix")
        if not candidate:
            raise ScanManagerError("strixNotFound")
        path = Path(candidate).expanduser().resolve()
        if path.is_file():
            return [str(path)], None
        if path.is_dir():
            executable = path / "strix.exe"
            if executable.is_file():
                return [str(executable)], None
            if (path / "strix" / "interface" / "main.py").is_file():
                return [sys.executable, "-m", "strix.interface.main"], str(path)
        raise ScanManagerError("strixNotFound")


class ScanManager:
    """Persistent single-worker queue with idempotent creation and safe lifecycle controls."""

    def __init__(
        self,
        *,
        state_path: Path,
        provider_service: ProviderService,
        process_adapter: ProcessAdapter,
        readiness: Callable[[], bool],
    ) -> None:
        self.state_path = state_path
        self.provider_service = provider_service
        self.process_adapter = process_adapter
        self.readiness = readiness
        self._records = self._load()
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._closed = threading.Event()
        self._thread: threading.Thread | None = None
        self._reconciled = False

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        if not self._reconciled:
            self._reconcile_restart()
            self._reconciled = True
        self._closed.clear()
        self._thread = threading.Thread(
            target=self._dispatch_loop,
            name="strix-console-scan-queue",
            daemon=True,
        )
        self._thread.start()
        self._wake.set()

    def close(self) -> None:
        self._closed.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=1)

    def create(self, request: CreateScanRequest, idempotency_key: str) -> ScanSummary:
        if not idempotency_key or len(idempotency_key) > 200:
            raise ScanManagerError("idempotencyKeyRequired")
        with self._lock:
            existing = next(
                (
                    record
                    for record in self._records
                    if record.idempotency_key == idempotency_key
                ),
                None,
            )
            if existing is not None:
                return self._summary(existing)
        validated = validate_scan_request(request)
        if not self.readiness():
            raise ScanManagerError("environmentNotReady")
        provider_status = self.provider_service.status()
        if not provider_status.configured:
            raise ScanManagerError("providerNotConfigured")
        if not provider_status.connection_verified:
            raise ScanManagerError("providerConnectivityNotVerified")

        with self._lock:
            existing = next(
                (
                    record
                    for record in self._records
                    if record.idempotency_key == idempotency_key
                ),
                None,
            )
            if existing is not None:
                return self._summary(existing)
            now = datetime.now(UTC)
            scan_id = uuid.uuid4().hex
            record = _ScanRecord(
                id=scan_id,
                idempotency_key=idempotency_key,
                status="queued",
                request=validated.request,
                constraint_instruction=validated.constraint_instruction,
                engine_run_name=f"console-{scan_id}",
                created_at=now,
                updated_at=now,
            )
            self._records.append(record)
            self._persist()
            summary = self._summary(record)
        self._wake.set()
        return summary

    def list_scans(self) -> ScanListResponse:
        with self._lock:
            return ScanListResponse(scans=[self._summary(record) for record in self._records])

    def get(self, scan_id: str) -> ScanSummary | None:
        with self._lock:
            record = self._find(scan_id)
            return self._summary(record) if record is not None else None

    def stop(self, scan_id: str) -> ScanSummary:
        with self._lock:
            record = self._require(scan_id)
            if record.status == "queued":
                self._update(record, status="stopped", ended_at=datetime.now(UTC))
                self._persist()
                return self._summary(record)
            if record.status not in {"preparing", "running", "reporting"}:
                raise ScanManagerError("scanCannotStop")
            record.stop_requested = True
            self._update(record, status="stopping")
            self._persist()
        self.process_adapter.stop(scan_id)
        return self._summary(record)

    def terminate(self, scan_id: str, *, confirmed: bool) -> ScanSummary:
        if not confirmed:
            raise ScanManagerError("terminationConfirmationRequired")
        with self._lock:
            record = self._require(scan_id)
            if record.status not in {"preparing", "running", "reporting", "stopping"}:
                raise ScanManagerError("scanCannotTerminate")
            previous_status = record.status
            record.terminate_requested = True
            self._update(record, status="terminating")
            self._persist()
        if not self.process_adapter.terminate(scan_id) and previous_status != "preparing":
            with self._lock:
                self._update(record, status="failed", error_code="processControlLost")
                record.ended_at = datetime.now(UTC)
                self._persist()
        return self._summary(record)

    def _dispatch_loop(self) -> None:
        while not self._closed.is_set():
            self._wake.wait(timeout=0.5)
            self._wake.clear()
            record = self._claim_next()
            if record is None:
                continue
            self._execute(record)

    def _claim_next(self) -> _ScanRecord | None:
        with self._lock:
            orphaned = next(
                (
                    record
                    for record in self._records
                    if record.error_code == "serviceRestartedProcessStillRunning"
                    and record.process_id is not None
                ),
                None,
            )
            if orphaned is not None:
                orphaned_process_id = orphaned.process_id
                if orphaned_process_id is not None and _pid_is_running(orphaned_process_id):
                    return None
                orphaned.process_id = None
                orphaned.error_code = "serviceRestarted"
                orphaned.updated_at = datetime.now(UTC)
                self._persist()
            if any(record.status in _ACTIVE_STATUSES for record in self._records):
                return None
            record = next((item for item in self._records if item.status == "queued"), None)
            if record is None:
                return None
            self._update(record, status="preparing")
            self._persist()
            return record

    def _execute(self, record: _ScanRecord) -> None:
        if not self.readiness():
            self._finish(record, "failed", "environmentNotReady")
            return
        if not self.provider_service.status().connection_verified:
            self._finish(record, "failed", "providerConnectivityNotVerified")
            return
        provider = self.provider_service.runtime()
        if provider is None:
            self._finish(record, "failed", "providerNotConfigured")
            return

        def on_started(process_id: int) -> None:
            with self._lock:
                record.process_id = process_id
                record.started_at = datetime.now(UTC)
                if record.terminate_requested:
                    self._update(record, status="terminating")
                elif record.stop_requested:
                    self._update(record, status="stopping")
                else:
                    self._update(record, status="running")
                self._persist()
            if record.terminate_requested:
                self.process_adapter.terminate(record.id)
            elif record.stop_requested:
                self.process_adapter.stop(record.id)

        def on_timeout() -> None:
            with self._lock:
                record.stop_requested = True
                self._update(record, status="stopping", error_code="durationLimitReached")
                self._persist()

        try:
            return_code = self.process_adapter.run(
                record,
                provider,
                on_started=on_started,
                on_timeout=on_timeout,
            )
        except (OSError, ScanManagerError):
            self._finish(record, "failed", "processStartFailed")
            return

        if record.terminate_requested:
            self._finish(record, "terminated", None)
        elif record.stop_requested:
            self._finish(record, "stopped", record.error_code)
        elif return_code == 0:
            self._finish(record, "completed", None)
        else:
            error_code = (
                "processExitedBySignal"
                if return_code < 0
                else f"processExit{return_code}"
            )
            self._finish(record, "failed", error_code)

    def _finish(
        self,
        record: _ScanRecord,
        status: Literal["completed", "stopped", "terminated", "failed"],
        error_code: str | None,
    ) -> None:
        with self._lock:
            record.process_id = None
            record.ended_at = datetime.now(UTC)
            self._update(record, status=status, error_code=error_code)
            self._persist()
        self._wake.set()

    def _summary(self, record: _ScanRecord) -> ScanSummary:
        queued = [item for item in self._records if item.status == "queued"]
        queue_position = queued.index(record) + 1 if record in queued else None
        safe_request = record.request.model_copy(
            update={
                "target": _display_scan_target(record.request.target),
                "scope": record.request.scope.model_copy(
                    update={
                        "exclusions": [
                            redact_text(value, home=Path.home())
                            for value in record.request.scope.exclusions
                        ]
                    }
                ),
                "options": record.request.options.model_copy(update={"instructions": ""}),
            }
        )
        return ScanSummary(
            id=record.id,
            status=record.status,
            target_type=safe_request.target_type,
            target=safe_request.target,
            scope=safe_request.scope,
            options=safe_request.options,
            queue_position=queue_position,
            engine_run_name=record.engine_run_name,
            created_at=record.created_at,
            updated_at=record.updated_at,
            started_at=record.started_at,
            ended_at=record.ended_at,
            process_id=record.process_id,
            error_code=record.error_code,
        )

    def _load(self) -> list[_ScanRecord]:
        if not self.state_path.is_file():
            return []
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                return []
            return [_ScanRecord.model_validate(item) for item in data]
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            return []

    def _persist(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                [record.model_dump(mode="json", by_alias=True) for record in self._records],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(self.state_path)

    def _reconcile_restart(self) -> None:
        changed = False
        for record in self._records:
            if record.status in _ACTIVE_STATUSES:
                record.status = "failed"
                record.error_code = (
                    "serviceRestartedProcessStillRunning"
                    if record.process_id and _pid_is_running(record.process_id)
                    else "serviceRestarted"
                )
                record.ended_at = datetime.now(UTC)
                if record.error_code != "serviceRestartedProcessStillRunning":
                    record.process_id = None
                record.updated_at = datetime.now(UTC)
                changed = True
        if changed:
            self._persist()

    def _find(self, scan_id: str) -> _ScanRecord | None:
        return next((record for record in self._records if record.id == scan_id), None)

    def _require(self, scan_id: str) -> _ScanRecord:
        record = self._find(scan_id)
        if record is None:
            raise ScanManagerError("scanNotFound")
        return record

    @staticmethod
    def _update(
        record: _ScanRecord,
        *,
        status: ScanStatus,
        error_code: str | None = None,
        ended_at: datetime | None = None,
    ) -> None:
        if record.status in _TERMINAL_STATUSES and record.status != status:
            raise ScanManagerError("terminalStateImmutable")
        record.status = status
        record.updated_at = datetime.now(UTC)
        record.error_code = error_code
        if ended_at is not None:
            record.ended_at = ended_at


def _pid_is_running(process_id: int) -> bool:
    try:
        os.kill(process_id, 0)
    except OSError:
        return False
    return True


def _display_scan_target(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        value = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    return redact_text(value, home=Path.home())
