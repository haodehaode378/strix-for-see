from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass, field
from threading import Lock
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict

from strix_console_service import __version__


def _to_camel_case(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


class HealthResponse(BaseModel):
    """Authenticated service-health contract."""

    model_config = ConfigDict(
        alias_generator=lambda value: _to_camel_case(value),
        populate_by_name=True,
    )

    status: Literal["ok"] = "ok"
    service_version: str = __version__
    schema_version: int = 1
    platform: Literal["windows"] = "windows"


class SessionResponse(BaseModel):
    """One-time browser bootstrap response."""

    model_config = ConfigDict(
        alias_generator=lambda value: _to_camel_case(value),
        populate_by_name=True,
    )

    access_token: str


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
) -> FastAPI:
    """Create an isolated service instance with per-process in-memory credentials."""

    session = SessionState(
        access_token=access_token or secrets.token_urlsafe(32),
        bootstrap_token=bootstrap_token or secrets.token_urlsafe(32),
    )
    app = FastAPI(
        title="Strix Console Control Service",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.session = session
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
        allow_headers=["X-Strix-Access-Token", "X-Strix-Bootstrap"],
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

    return app


app = create_app()
