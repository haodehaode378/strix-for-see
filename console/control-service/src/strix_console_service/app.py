from __future__ import annotations

import hmac
import os
import secrets
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from threading import Lock
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse

from strix_console_service import __version__
from strix_console_service.audit import AuditLog
from strix_console_service.contracts import (
    ApplicationUpdate,
    CreateScanRequest,
    DiagnosticReport,
    ExportFindingsRequest,
    ExportFindingsResponse,
    Finding,
    FindingsResponse,
    FindingTranslation,
    HealthResponse,
    LocalRunsResponse,
    LocalRunSummary,
    ProviderConfigRequest,
    ProviderModelsRequest,
    ProviderModelsResponse,
    ProviderStatus,
    ProviderTestResult,
    SandboxPullRequest,
    SandboxPullStatus,
    SandboxUpdate,
    ScanListResponse,
    ScanSummary,
    SessionResponse,
    SteeringRequest,
    SteeringResponse,
    SystemReport,
    TerminateScanRequest,
    UpdateAuthorization,
    UpdateFindingRequest,
)
from strix_console_service.events import (
    EventStore,
    RunEventObserver,
    heartbeat_frame,
    sse_frames,
)
from strix_console_service.findings import FindingStore, FindingStoreError
from strix_console_service.local_runs import LocalRunIndexer, RunRoot
from strix_console_service.provider import (
    ProviderConfigurationError,
    ProviderService,
    default_credential_store,
)
from strix_console_service.scan_manager import (
    ScanManager,
    ScanManagerError,
    StrixProcessAdapter,
)
from strix_console_service.scan_validation import ScanValidationError
from strix_console_service.system_checks import SystemInspector
from strix_console_service.updates import UpdateError, UpdateService


class _AppServices:
    """Process-local service dependencies."""

    def __init__(
        self,
        *,
        run_indexer: LocalRunIndexer,
        system_inspector: SystemInspector,
        provider_service: ProviderService,
        scan_manager: ScanManager,
        event_store: EventStore,
        finding_store: FindingStore,
        update_service: UpdateService,
        audit_log: AuditLog,
    ) -> None:
        self.run_indexer = run_indexer
        self.system_inspector = system_inspector
        self.provider_service = provider_service
        self.scan_manager = scan_manager
        self.event_store = event_store
        self.finding_store = finding_store
        self.update_service = update_service
        self.audit_log = audit_log


def _build_services(
    *,
    run_roots: list[RunRoot] | None = None,
    system_inspector: SystemInspector | None = None,
    provider_service: ProviderService | None = None,
    scan_manager: ScanManager | None = None,
    update_service: UpdateService | None = None,
) -> _AppServices:
    run_indexer = (
        LocalRunIndexer(run_roots)
        if run_roots is not None
        else LocalRunIndexer.from_environment()
    )
    state_root = run_indexer.default_root.parent / "state"
    event_store = EventStore(state_root / "events")
    event_observer = RunEventObserver(run_indexer.default_root, event_store)
    provider = provider_service or ProviderService(
        config_path=state_root / "provider.json",
        credential_store=default_credential_store(),
    )

    def provider_ready() -> bool:
        provider_status = provider.status()
        return provider_status.configured and provider_status.connection_verified

    inspector = system_inspector or SystemInspector(
        run_root=run_indexer.default_root,
        provider_configured=provider_ready,
    )
    manager = scan_manager or ScanManager(
        state_path=state_root / "scan-queue.json",
        provider_service=provider,
        process_adapter=StrixProcessAdapter(
            run_root=run_indexer.default_root,
            strix_path=os.environ.get("STRIX_CONSOLE_STRIX_PATH"),
            python_path=os.environ.get("STRIX_CONSOLE_PYTHON_PATH"),
        ),
        readiness=lambda: inspector.inspect().summary.ready,
        event_store=event_store,
        event_observer=event_observer,
        run_root=run_indexer.default_root,
    )
    updater = update_service or UpdateService(scan_active=manager.has_active_scan)
    return _AppServices(
        run_indexer=run_indexer,
        system_inspector=inspector,
        provider_service=provider,
        scan_manager=manager,
        event_store=manager.event_store,
        finding_store=FindingStore(
            run_indexer,
            state_root / "findings.json",
            run_indexer.default_root.parent / "exports",
        ),
        update_service=updater,
        audit_log=AuditLog(state_root / "audit.jsonl"),
    )


@dataclass
class SessionState:
    """In-memory credentials for one service process."""

    access_token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    bootstrap_token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    bootstrap_consumed: bool = False
    lock: Lock = field(default_factory=Lock)

    def exchange_bootstrap(self, candidate: str) -> str | None:
        """Exchange the bootstrap token once without persisting either credential."""

        with self.lock:
            if self.bootstrap_consumed or not hmac.compare_digest(
                candidate, self.bootstrap_token
            ):
                return None
            self.bootstrap_consumed = True
            return self.access_token


def create_app(
    *,
    access_token: str | None = None,
    bootstrap_token: str | None = None,
    run_roots: list[RunRoot] | None = None,
    system_inspector: SystemInspector | None = None,
    provider_service: ProviderService | None = None,
    scan_manager: ScanManager | None = None,
    update_service: UpdateService | None = None,
) -> FastAPI:
    """Create an isolated service instance with per-process in-memory credentials."""

    session = SessionState(
        access_token=access_token or secrets.token_urlsafe(32),
        bootstrap_token=bootstrap_token or secrets.token_urlsafe(32),
    )
    services = _build_services(
        run_roots=run_roots,
        system_inspector=system_inspector,
        provider_service=provider_service,
        scan_manager=scan_manager,
        update_service=update_service,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        services.scan_manager.start()
        try:
            yield
        finally:
            services.scan_manager.close()

    app = FastAPI(
        title="Strix Console Control Service",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.session = session
    app.state.services = services
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://tauri.localhost",
            "tauri://localhost",
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=[
            "Content-Type",
            "Last-Event-ID",
            "X-Idempotency-Key",
            "X-Strix-Access-Token",
            "X-Strix-Bootstrap",
        ],
    )

    def require_access_token(
        x_strix_access_token: Annotated[str | None, Header()] = None,
    ) -> None:
        if x_strix_access_token is None or not hmac.compare_digest(
            x_strix_access_token, session.access_token
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Valid in-memory access token required",
            )

    @app.post("/api/session", response_model=SessionResponse)
    def create_session(
        x_strix_bootstrap: Annotated[str | None, Header()] = None,
    ) -> SessionResponse:
        if x_strix_bootstrap is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bootstrap token required",
            )
        exchanged_token = session.exchange_bootstrap(x_strix_bootstrap)
        if exchanged_token is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bootstrap token is invalid or already used",
            )
        return SessionResponse(access_token=exchanged_token)

    @app.get(
        "/api/health",
        response_model=HealthResponse,
        dependencies=[Depends(require_access_token)],
    )
    def health() -> HealthResponse:
        return HealthResponse()

    @app.get(
        "/api/system",
        response_model=SystemReport,
        dependencies=[Depends(require_access_token)],
    )
    def system_report() -> SystemReport:
        return services.system_inspector.inspect()

    @app.post(
        "/api/system/recheck",
        response_model=SystemReport,
        dependencies=[Depends(require_access_token)],
    )
    def recheck_system() -> SystemReport:
        return services.system_inspector.inspect()

    @app.post(
        "/api/system/prepare",
        response_model=SystemReport,
        dependencies=[Depends(require_access_token)],
    )
    def prepare_system() -> SystemReport:
        result = services.system_inspector.prepare()
        services.audit_log.append("system.prepare", "completed")
        return result

    @app.get(
        "/api/system/diagnostics",
        response_model=DiagnosticReport,
        dependencies=[Depends(require_access_token)],
    )
    def diagnostics() -> DiagnosticReport:
        report = services.system_inspector.diagnostics()
        state_issues = (
            [services.scan_manager.load_issue] if services.scan_manager.load_issue else []
        )
        return report.model_copy(
            update={
                "audit": services.audit_log.summary(),
                "state_issues": state_issues,
            }
        )

    @app.get(
        "/api/updates/application",
        response_model=ApplicationUpdate,
        dependencies=[Depends(require_access_token)],
    )
    def application_update() -> ApplicationUpdate:
        try:
            return services.update_service.check_application()
        except (OSError, ValueError) as error:
            detail = error.code if isinstance(error, UpdateError) else "updateCheckFailed"
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail) from error

    @app.post(
        "/api/updates/application/authorize",
        response_model=UpdateAuthorization,
        dependencies=[Depends(require_access_token)],
    )
    def authorize_application_update() -> UpdateAuthorization:
        try:
            services.update_service.authorize_application_update()
            services.audit_log.append("applicationUpdate.authorized", "allowed")
            return UpdateAuthorization()
        except UpdateError as error:
            services.audit_log.append("applicationUpdate.authorized", "blocked")
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error.code) from error

    @app.get(
        "/api/updates/sandbox",
        response_model=SandboxUpdate,
        dependencies=[Depends(require_access_token)],
    )
    def sandbox_update() -> SandboxUpdate:
        try:
            return services.update_service.check_sandbox()
        except (OSError, ValueError) as error:
            detail = error.code if isinstance(error, UpdateError) else "updateCheckFailed"
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail) from error

    @app.post(
        "/api/updates/sandbox/pull",
        response_model=SandboxPullStatus,
        dependencies=[Depends(require_access_token)],
    )
    def pull_sandbox(request: SandboxPullRequest) -> SandboxPullStatus:
        try:
            result = services.update_service.start_sandbox_pull(confirmed=request.confirmed)
            services.audit_log.append("sandboxUpdate.started", "accepted")
            return result
        except UpdateError as error:
            services.audit_log.append("sandboxUpdate.started", "blocked")
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error.code) from error

    @app.get(
        "/api/updates/sandbox/pull",
        response_model=SandboxPullStatus,
        dependencies=[Depends(require_access_token)],
    )
    def sandbox_pull_status() -> SandboxPullStatus:
        return services.update_service.pull_status()

    @app.get(
        "/api/provider",
        response_model=ProviderStatus,
        dependencies=[Depends(require_access_token)],
    )
    def provider_status() -> ProviderStatus:
        return services.provider_service.status()

    @app.post(
        "/api/provider",
        response_model=ProviderStatus,
        dependencies=[Depends(require_access_token)],
    )
    def configure_provider(request: ProviderConfigRequest) -> ProviderStatus:
        try:
            result = services.provider_service.configure(request)
            services.audit_log.append("provider.configured", "success")
            return result
        except (ProviderConfigurationError, OSError) as error:
            detail = (
                error.code
                if isinstance(error, ProviderConfigurationError)
                else "secretStoreFailed"
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from error

    @app.post(
        "/api/provider/test",
        response_model=ProviderTestResult,
        dependencies=[Depends(require_access_token)],
    )
    def test_provider() -> ProviderTestResult:
        return services.provider_service.test_connectivity()

    @app.post(
        "/api/provider/models",
        response_model=ProviderModelsResponse,
        dependencies=[Depends(require_access_token)],
    )
    def discover_provider_models(request: ProviderModelsRequest) -> ProviderModelsResponse:
        try:
            return services.provider_service.discover_models(request)
        except ProviderConfigurationError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error.code,
            ) from error

    @app.post(
        "/api/scans",
        response_model=ScanSummary,
        dependencies=[Depends(require_access_token)],
    )
    def create_scan(
        request: CreateScanRequest,
        x_idempotency_key: Annotated[str | None, Header()] = None,
    ) -> ScanSummary:
        try:
            result = services.scan_manager.create(request, x_idempotency_key or "")
            services.audit_log.append("scan.created", "accepted")
            return result
        except (ScanValidationError, ScanManagerError) as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error.code,
            ) from error

    @app.get(
        "/api/scans",
        response_model=ScanListResponse,
        dependencies=[Depends(require_access_token)],
    )
    def scans() -> ScanListResponse:
        return services.scan_manager.list_scans()

    @app.get(
        "/api/scans/{scan_id}",
        response_model=ScanSummary,
        dependencies=[Depends(require_access_token)],
    )
    def scan(scan_id: str) -> ScanSummary:
        result = services.scan_manager.get(scan_id)
        if result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scanNotFound")
        return result

    @app.post(
        "/api/scans/{scan_id}/stop",
        response_model=ScanSummary,
        dependencies=[Depends(require_access_token)],
    )
    def stop_scan(scan_id: str) -> ScanSummary:
        try:
            result = services.scan_manager.stop(scan_id)
            services.audit_log.append("scan.stop", "accepted")
            return result
        except ScanManagerError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error.code) from error

    @app.post(
        "/api/scans/{scan_id}/terminate",
        response_model=ScanSummary,
        dependencies=[Depends(require_access_token)],
    )
    def terminate_scan(scan_id: str, request: TerminateScanRequest) -> ScanSummary:
        try:
            result = services.scan_manager.terminate(scan_id, confirmed=request.confirmed)
            services.audit_log.append("scan.terminate", "accepted")
            return result
        except ScanManagerError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error.code) from error

    @app.post(
        "/api/scans/{scan_id}/steering",
        response_model=SteeringResponse,
        dependencies=[Depends(require_access_token)],
    )
    def steer_scan(scan_id: str, request: SteeringRequest) -> SteeringResponse:
        try:
            return services.scan_manager.steer(scan_id, request.message)
        except (ScanValidationError, ScanManagerError, OSError) as error:
            detail = error.code if hasattr(error, "code") else "steeringWriteFailed"
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from error

    @app.get(
        "/api/scans/{scan_id}/events",
        dependencies=[Depends(require_access_token)],
    )
    def scan_events(
        scan_id: str,
        last_event_id: Annotated[str | None, Header()] = None,
        after: str | None = Query(default=None),
    ) -> StreamingResponse:
        if services.scan_manager.get(scan_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scanNotFound")
        cursor = last_event_id or after

        def stream() -> Iterator[str]:
            nonlocal cursor
            idle_ticks = 0
            while True:
                services.scan_manager.refresh_events(scan_id)
                events = services.event_store.wait_after(scan_id, cursor, timeout=0.75)
                if events:
                    yield from sse_frames(events)
                    cursor = events[-1].event_id
                    idle_ticks = 0
                else:
                    idle_ticks += 1
                if idle_ticks >= 20:
                    yield heartbeat_frame()
                    idle_ticks = 0

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get(
        "/api/scans/{scan_id}/findings",
        response_model=FindingsResponse,
        dependencies=[Depends(require_access_token)],
    )
    def scan_findings(scan_id: str) -> FindingsResponse:
        scan_result = services.scan_manager.get(scan_id)
        if scan_result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scanNotFound")
        return services.finding_store.list_findings(run_name=scan_result.engine_run_name)

    @app.get(
        "/api/runs/{run_id}/findings",
        response_model=FindingsResponse,
        dependencies=[Depends(require_access_token)],
    )
    def run_findings(run_id: str) -> FindingsResponse:
        if services.run_indexer.get_run(run_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="runNotFound")
        return services.finding_store.list_findings(run_id=run_id)

    @app.get(
        "/api/runs/{run_id}/findings/{finding_id}",
        response_model=Finding,
        dependencies=[Depends(require_access_token)],
    )
    def run_finding(run_id: str, finding_id: str) -> Finding:
        if services.run_indexer.get_run(run_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="runNotFound")
        result = services.finding_store.get(finding_id, run_id=run_id)
        if result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="findingNotFound")
        return result

    @app.post(
        "/api/runs/{run_id}/findings/{finding_id}/translation",
        response_model=FindingTranslation,
        dependencies=[Depends(require_access_token)],
    )
    def translate_run_finding(run_id: str, finding_id: str) -> FindingTranslation:
        if services.run_indexer.get_run(run_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="runNotFound")
        finding = services.finding_store.get(finding_id, run_id=run_id)
        if finding is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="findingNotFound")
        explanation = finding.explanation
        fields = {
            "title": finding.title,
            "description": finding.description or "",
            "impact": finding.impact or "",
            "technical_analysis": finding.technical_analysis or "",
            "remediation_steps": finding.remediation_steps or "",
            "interface_or_feature": explanation.interface_or_feature or "",
            "prerequisites": explanation.prerequisites or "",
            "trigger_behavior": explanation.trigger_behavior or "",
            "real_impact": explanation.real_impact or "",
        }
        try:
            return services.provider_service.translate_to_chinese(fields)
        except ProviderConfigurationError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error.code,
            ) from error

    @app.patch(
        "/api/runs/{run_id}/findings/{finding_id}",
        response_model=Finding,
        dependencies=[Depends(require_access_token)],
    )
    def update_run_finding(
        run_id: str, finding_id: str, request: UpdateFindingRequest
    ) -> Finding:
        if services.run_indexer.get_run(run_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="runNotFound")
        try:
            return services.finding_store.update(finding_id, request, run_id=run_id)
        except FindingStoreError as error:
            code = (
                status.HTTP_404_NOT_FOUND
                if error.code == "findingNotFound"
                else status.HTTP_409_CONFLICT
            )
            raise HTTPException(status_code=code, detail=error.code) from error

    @app.get(
        "/api/findings",
        response_model=FindingsResponse,
        dependencies=[Depends(require_access_token)],
    )
    def findings() -> FindingsResponse:
        return services.finding_store.list_findings()

    @app.post(
        "/api/findings/export",
        dependencies=[Depends(require_access_token)],
    )
    def export_findings(request: ExportFindingsRequest) -> Response:
        try:
            payload, media_type, filename = services.finding_store.export(request)
        except FindingStoreError as error:
            code = (
                status.HTTP_404_NOT_FOUND
                if error.code == "findingNotFound"
                else status.HTTP_409_CONFLICT
            )
            raise HTTPException(status_code=code, detail=error.code) from error
        return Response(
            payload,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.post(
        "/api/findings/export-file",
        response_model=ExportFindingsResponse,
        dependencies=[Depends(require_access_token)],
    )
    def export_findings_to_file(
        request: ExportFindingsRequest,
    ) -> ExportFindingsResponse:
        try:
            filename, display_path = services.finding_store.export_to_file(request)
        except FindingStoreError as error:
            code = (
                status.HTTP_404_NOT_FOUND
                if error.code == "findingNotFound"
                else status.HTTP_409_CONFLICT
            )
            raise HTTPException(status_code=code, detail=error.code) from error
        return ExportFindingsResponse(
            filename=filename,
            display_path=display_path,
            run_id=request.run_id,
            run_name=(run.name if (run := services.run_indexer.get_run(request.run_id)) else None),
        )

    @app.post(
        "/api/findings/export-folder",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[Depends(require_access_token)],
    )
    def open_findings_export_folder() -> Response:
        try:
            services.finding_store.open_export_folder()
        except OSError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="exportFolderOpenFailed",
            ) from error
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.get(
        "/api/local-runs",
        response_model=LocalRunsResponse,
        dependencies=[Depends(require_access_token)],
    )
    def local_runs() -> LocalRunsResponse:
        return services.run_indexer.list_runs()

    @app.get(
        "/api/local-runs/{run_id}",
        response_model=LocalRunSummary,
        dependencies=[Depends(require_access_token)],
    )
    def local_run(run_id: str) -> LocalRunSummary:
        run = services.run_indexer.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
        return run

    @app.get(
        "/api/local-runs/{run_id}/artifacts/{artifact_name}",
        dependencies=[Depends(require_access_token)],
    )
    def local_run_artifact(run_id: str, artifact_name: str) -> FileResponse:
        artifact = services.run_indexer.resolve_artifact(run_id, artifact_name)
        if artifact is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
        return FileResponse(
            path=artifact.path,
            media_type=artifact.media_type,
            filename=artifact.path.name,
        )

    return app


app = create_app()
