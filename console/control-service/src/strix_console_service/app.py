from __future__ import annotations

import hmac
import os
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from threading import Lock
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from strix_console_service import __version__
from strix_console_service.contracts import (
    CreateScanRequest,
    DiagnosticReport,
    HealthResponse,
    LocalRunsResponse,
    LocalRunSummary,
    ProviderConfigRequest,
    ProviderStatus,
    ProviderTestResult,
    ScanListResponse,
    ScanSummary,
    SessionResponse,
    SystemReport,
    TerminateScanRequest,
)
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


class _AppServices:
    """Process-local service dependencies."""

    def __init__(
        self,
        *,
        run_indexer: LocalRunIndexer,
        system_inspector: SystemInspector,
        provider_service: ProviderService,
        scan_manager: ScanManager,
    ) -> None:
        self.run_indexer = run_indexer
        self.system_inspector = system_inspector
        self.provider_service = provider_service
        self.scan_manager = scan_manager


def _build_services(
    *,
    run_roots: list[RunRoot] | None = None,
    system_inspector: SystemInspector | None = None,
    provider_service: ProviderService | None = None,
    scan_manager: ScanManager | None = None,
) -> _AppServices:
    run_indexer = (
        LocalRunIndexer(run_roots)
        if run_roots is not None
        else LocalRunIndexer.from_environment()
    )
    state_root = run_indexer.default_root.parent / "state"
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
        ),
        readiness=lambda: inspector.inspect().summary.ready,
    )
    return _AppServices(
        run_indexer=run_indexer,
        system_inspector=inspector,
        provider_service=provider,
        scan_manager=manager,
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
        allow_methods=["GET", "POST"],
        allow_headers=[
            "Content-Type",
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

    @app.get(
        "/api/system/diagnostics",
        response_model=DiagnosticReport,
        dependencies=[Depends(require_access_token)],
    )
    def diagnostics() -> DiagnosticReport:
        return services.system_inspector.diagnostics()

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
            return services.provider_service.configure(request)
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
        "/api/scans",
        response_model=ScanSummary,
        dependencies=[Depends(require_access_token)],
    )
    def create_scan(
        request: CreateScanRequest,
        x_idempotency_key: Annotated[str | None, Header()] = None,
    ) -> ScanSummary:
        try:
            return services.scan_manager.create(request, x_idempotency_key or "")
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
            return services.scan_manager.stop(scan_id)
        except ScanManagerError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error.code) from error

    @app.post(
        "/api/scans/{scan_id}/terminate",
        response_model=ScanSummary,
        dependencies=[Depends(require_access_token)],
    )
    def terminate_scan(scan_id: str, request: TerminateScanRequest) -> ScanSummary:
        try:
            return services.scan_manager.terminate(scan_id, confirmed=request.confirmed)
        except ScanManagerError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error.code) from error

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
