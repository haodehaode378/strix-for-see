from __future__ import annotations

import json
import os
import re
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
    EventActor,
    ScanListResponse,
    ScanStatus,
    ScanSummary,
    SteeringResponse,
)
from strix_console_service.events import EventStore, RunEventObserver
from strix_console_service.provider import ProviderRuntime, ProviderService
from strix_console_service.scan_validation import (
    validate_scan_request,
    validate_steering_message,
)
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

    def cleanup(self, scan_id: str, engine_run_name: str) -> bool: ...

    def reconcile(
        self, scan_id: str, engine_run_name: str, process_id: int | None
    ) -> bool: ...


class StrixProcessAdapter:
    """Start Strix without a shell and control only tracked child handles."""

    def __init__(
        self,
        *,
        run_root: Path,
        strix_path: str | None,
        python_path: str | None = None,
        environment: Mapping[str, str] | None = None,
        stop_grace_seconds: float = 15.0,
    ) -> None:
        self.run_root = run_root.resolve()
        self.strix_path = strix_path
        self.python_path = python_path
        self.base_environment = dict(environment if environment is not None else os.environ)
        self.stop_grace_seconds = stop_grace_seconds
        self._processes: dict[str, subprocess.Popen[bytes]] = {}
        self._stop_deadlines: dict[str, float] = {}
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
        log_path = self.run_root.parent / "state" / "process-logs" / f"{record.id}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle = log_path.open("wb")
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        try:
            process = subprocess.Popen(  # noqa: S603
                command,
                cwd=self.run_root.parent,
                env=child_environment,
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                shell=False,
                close_fds=True,
                creationflags=creation_flags,
                start_new_session=os.name != "nt",
            )
        except OSError:
            log_handle.close()
            raise
        with self._lock:
            self._processes[record.id] = process
        on_started(process.pid)

        deadline = (
            time.monotonic() + record.request.options.max_duration_minutes * 60
            if record.request.options.termination_policy == "consoleLimits"
            else None
        )
        timeout_sent = False
        try:
            while True:
                return_code = process.poll()
                if return_code is not None:
                    return return_code
                with self._lock:
                    stop_deadline = self._stop_deadlines.get(record.id)
                if stop_deadline is not None and time.monotonic() >= stop_deadline:
                    self.terminate(record.id)
                if (
                    deadline is not None
                    and not timeout_sent
                    and time.monotonic() >= deadline
                ):
                    timeout_sent = True
                    on_timeout()
                    self.stop(record.id)
                time.sleep(0.25)
        finally:
            log_handle.close()
            with self._lock:
                self._processes.pop(record.id, None)
                self._stop_deadlines.pop(record.id, None)

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
        with self._lock:
            self._stop_deadlines[scan_id] = time.monotonic() + self.stop_grace_seconds
        return True

    def terminate(self, scan_id: str) -> bool:
        process = self._tracked_process(scan_id)
        if process is None or process.poll() is not None:
            return False
        return _kill_process_tree(process.pid, process)

    def cleanup(self, scan_id: str, engine_run_name: str) -> bool:
        del scan_id
        return self._remove_console_containers(engine_run_name)

    def reconcile(
        self, scan_id: str, engine_run_name: str, process_id: int | None
    ) -> bool:
        del scan_id
        process_stopped = process_id is None or not _pid_is_running(process_id)
        if not process_stopped and process_id is not None:
            process_stopped = _kill_process_tree(process_id)
        return process_stopped and self._remove_console_containers(engine_run_name)

    def _remove_console_containers(self, engine_run_name: str) -> bool:
        docker = shutil.which("docker", path=self.base_environment.get("PATH"))
        if docker is None:
            return False
        filters = [
            "--filter",
            f"label=strix-run-id={engine_run_name}",
            "--filter",
            "label=strix-run-type=console",
        ]
        try:
            listed = subprocess.run(  # noqa: S603
                [docker, "ps", "-aq", *filters],
                check=True,
                capture_output=True,
                text=True,
                timeout=15,
                env=self.base_environment,
            )
            container_ids = [value for value in listed.stdout.split() if value]
            if container_ids:
                subprocess.run(  # noqa: S603
                    [docker, "rm", "-f", *container_ids],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=self.base_environment,
                )
            remaining = subprocess.run(  # noqa: S603
                [docker, "ps", "-aq", *filters],
                check=True,
                capture_output=True,
                text=True,
                timeout=15,
                env=self.base_environment,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return not remaining.stdout.strip()

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
                "--run-name",
                record.engine_run_name,
            ]
        )
        if request.options.termination_policy == "consoleLimits":
            command.extend(["--max-budget-usd", str(request.options.max_budget_usd)])
        command.extend(["--instruction", instruction])

        environment = dict(self.base_environment)
        environment.update(
            {
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUTF8": "1",
                "STRIX_LLM": provider.model,
                "STRIX_RUNS_DIR": str(self.run_root),
                "STRIX_RUN_ID": record.engine_run_name,
                "STRIX_RUN_TYPE": "console",
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
                python = Path(self.python_path or sys.executable).expanduser().resolve()
                if not python.is_file():
                    raise ScanManagerError("strixPythonNotFound")
                return [str(python), "-m", "strix.interface.main"], str(path)
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
        event_store: EventStore | None = None,
        event_observer: RunEventObserver | None = None,
        run_root: Path | None = None,
    ) -> None:
        self.state_path = state_path
        self.provider_service = provider_service
        self.process_adapter = process_adapter
        self.readiness = readiness
        self.event_store = event_store or EventStore(state_path.parent / "events")
        self.run_root = run_root.resolve() if run_root is not None else None
        self.event_observer = event_observer
        self.load_issue: str | None = None
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
            self.event_store.append(
                scan_id,
                "scan.queued",
                actor=EventActor(kind="scan", id=scan_id),
                payload={"status": "queued"},
                source_key="lifecycle:queued",
            )
            summary = self._summary(record)
        self._wake.set()
        return summary

    def list_scans(self) -> ScanListResponse:
        with self._lock:
            return ScanListResponse(scans=[self._summary(record) for record in self._records])

    def has_active_scan(self) -> bool:
        """Return whether an update or other exclusive operation must be blocked."""

        with self._lock:
            return any(
                record.status in _ACTIVE_STATUSES or record.status == "queued"
                for record in self._records
            )

    def get(self, scan_id: str) -> ScanSummary | None:
        with self._lock:
            record = self._find(scan_id)
            if record is not None:
                self._refresh_events(record)
            return self._summary(record) if record is not None else None

    def refresh_events(self, scan_id: str) -> None:
        with self._lock:
            self._refresh_events(self._require(scan_id))

    def steer(self, scan_id: str, message: str) -> SteeringResponse:
        with self._lock:
            record = self._require(scan_id)
            if record.status != "running":
                raise ScanManagerError("scanCannotSteer")
            normalized = validate_steering_message(record.request, message)
            if self.run_root is None:
                raise ScanManagerError("steeringUnavailable")
            run_dir = (self.run_root / record.engine_run_name).resolve()
            if run_dir.parent != self.run_root:
                raise ScanManagerError("steeringUnavailable")
            inbox = run_dir / ".state" / "console-steering.jsonl"
            inbox.parent.mkdir(parents=True, exist_ok=True)
            message_id = uuid.uuid4().hex
            with inbox.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(
                    json.dumps(
                        {
                            "id": message_id,
                            "createdAt": datetime.now(UTC).isoformat(),
                            "message": normalized,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
            event = self.event_store.append(
                scan_id,
                "steering.accepted",
                actor=EventActor(kind="operator"),
                payload={"messageId": message_id},
                source_key=f"steering:{message_id}",
            )
            return SteeringResponse(accepted=True, event_id=event.event_id)

    def stop(self, scan_id: str) -> ScanSummary:
        with self._lock:
            record = self._require(scan_id)
            if record.status == "queued":
                self._update(record, status="stopped", ended_at=datetime.now(UTC))
                self._persist()
                self._lifecycle_event(record, "stopped")
                return self._summary(record)
            if record.status not in {"preparing", "running", "reporting"}:
                raise ScanManagerError("scanCannotStop")
            record.stop_requested = True
            self._update(record, status="stopping")
            self._persist()
            self._lifecycle_event(record, "stopping")
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
            self._lifecycle_event(record, "terminating")
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
            self._lifecycle_event(record, "preparing")
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
                self._lifecycle_event(record, record.status)
                self.event_store.append(
                    record.id,
                    "runtime.updated",
                    actor=EventActor(kind="runtime", id=str(process_id)),
                    payload={
                        "state": "running",
                        "processId": process_id,
                        "engineRunName": record.engine_run_name,
                    },
                    source_key=f"runtime:started:{process_id}",
                )
            if record.terminate_requested:
                self.process_adapter.terminate(record.id)
            elif record.stop_requested:
                self.process_adapter.stop(record.id)

        def on_timeout() -> None:
            with self._lock:
                record.stop_requested = True
                self._update(record, status="stopping", error_code="durationLimitReached")
                self._persist()
                self._lifecycle_event(record, "stopping")

        try:
            return_code = self.process_adapter.run(
                record,
                provider,
                on_started=on_started,
                on_timeout=on_timeout,
            )
        except (OSError, ScanManagerError):
            cleanup_ok = self.process_adapter.cleanup(record.id, record.engine_run_name)
            self._finish(
                record,
                "failed",
                "processStartFailed" if cleanup_ok else "sandboxCleanupFailed",
            )
            return

        cleanup_ok = self.process_adapter.cleanup(record.id, record.engine_run_name)
        if not cleanup_ok:
            self._finish(record, "failed", "sandboxCleanupFailed")
            return

        if record.terminate_requested:
            self._finish(record, "terminated", None)
        elif record.stop_requested:
            self._finish(record, "stopped", record.error_code)
        elif return_code == 0:
            self._finish(record, "completed", None)
        else:
            error_code = self._classify_failure(record, return_code)
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
            self._lifecycle_event(record, status, error_code=error_code)
            self.event_store.append(
                record.id,
                "runtime.updated",
                actor=EventActor(kind="runtime"),
                payload={"state": "stopped", "terminalStatus": status},
                source_key=f"runtime:stopped:{status}:{record.updated_at.isoformat()}",
            )
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
                self.load_issue = "invalidScanQueue"
                return []
            return [_ScanRecord.model_validate(item) for item in data]
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            self.load_issue = "invalidScanQueue"
            return []

    def _classify_failure(self, record: _ScanRecord, return_code: int) -> str:
        if self.run_root is not None:
            run_record = self.run_root / record.engine_run_name / "run.json"
            try:
                raw = run_record.read_text(encoding="utf-8")[:32_768].lower()
            except (OSError, UnicodeDecodeError):
                raw = ""
            if re.search(r"\b(429|rate[ _-]?limit|too many requests)\b", raw):
                return "providerRateLimited"
            if re.search(r"\b(budget|cost limit|spend limit)\b", raw):
                return "budgetExhausted"
            docker_failure = (
                r"\b(docker|container|daemon).{0,80}\b"
                r"(lost|unavailable|stopped|failed)\b"
            )
            if re.search(docker_failure, raw):
                return "dockerUnavailable"
        return "processExitedBySignal" if return_code < 0 else f"processExit{return_code}"

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
                cleanup_ok = self.process_adapter.reconcile(
                    record.id, record.engine_run_name, record.process_id
                )
                record.status = "failed"
                record.error_code = (
                    "serviceRestarted" if cleanup_ok else "sandboxCleanupFailed"
                )
                record.ended_at = datetime.now(UTC)
                if cleanup_ok:
                    record.process_id = None
                record.updated_at = datetime.now(UTC)
                changed = True
        if changed:
            self._persist()

    def _refresh_events(self, record: _ScanRecord) -> None:
        if self.event_observer is not None:
            self.event_observer.refresh(record.id, record.engine_run_name)

    def _lifecycle_event(
        self,
        record: _ScanRecord,
        status: str,
        *,
        error_code: str | None = None,
    ) -> None:
        payload: dict[str, str] = {"status": status}
        if error_code:
            payload["errorCode"] = error_code
        self.event_store.append(
            record.id,
            f"scan.{status}",
            actor=EventActor(kind="scan", id=record.id),
            payload=payload,
            source_key=f"lifecycle:{status}:{record.updated_at.isoformat()}",
        )

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


def _kill_process_tree(
    process_id: int, process: subprocess.Popen[bytes] | None = None
) -> bool:
    try:
        if os.name == "nt":
            taskkill = shutil.which("taskkill")
            if taskkill is None:
                return False
            completed = subprocess.run(  # noqa: S603
                [taskkill, "/PID", str(process_id), "/T", "/F"],
                check=False,
                capture_output=True,
                timeout=15,
            )
            return completed.returncode == 0 or not _pid_is_running(process_id)
        getpgid = getattr(os, "getpgid")  # noqa: B009 -- absent from Windows stubs
        killpg = getattr(os, "killpg")  # noqa: B009 -- absent from Windows stubs
        killpg(getpgid(process_id), getattr(signal, "SIGKILL", 9))
    except OSError:
        if process is None:
            return not _pid_is_running(process_id)
        try:
            process.kill()
        except OSError:
            return not _pid_is_running(process_id)
    return True


def _display_scan_target(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        value = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    return redact_text(value, home=Path.home())
