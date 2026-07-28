from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from strix_console_service import __version__


def _to_camel_case(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


class CamelModel(BaseModel):
    """Base contract that serializes Python fields as camelCase."""

    model_config = ConfigDict(alias_generator=_to_camel_case, populate_by_name=True)


class HealthResponse(CamelModel):
    """Authenticated service-health contract."""

    status: Literal["ok"] = "ok"
    service_version: str = __version__
    schema_version: int = 1
    platform: Literal["windows"] = "windows"


class SessionResponse(CamelModel):
    """One-time browser bootstrap response."""

    access_token: str


CheckStatus = Literal["ready", "warning", "missing", "error"]
Requirement = Literal["required", "optional"]


class SystemCheck(CamelModel):
    """One machine-readiness result without secret-bearing raw output."""

    id: str
    status: CheckStatus
    requirement: Requirement
    value: str | None = None
    issue: str | None = None


class SystemSummary(CamelModel):
    """Aggregate readiness counts."""

    ready: bool
    required_total: int
    required_ready: int
    required_failures: int
    optional_warnings: int


class SystemReport(CamelModel):
    """Current non-mutating readiness report."""

    schema_version: int = 1
    generated_at: datetime
    summary: SystemSummary
    checks: list[SystemCheck]


class DiagnosticReport(CamelModel):
    """Redacted support payload safe to copy from the UI."""

    schema_version: int = 1
    service_version: str = __version__
    system: SystemReport


RunState = Literal["active", "completed", "interrupted", "partial", "malformed"]


class SeverityCounts(CamelModel):
    """Stable severity buckets for a run summary."""

    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0


class ArtifactInfo(CamelModel):
    """Allowlisted artifact available for authenticated download."""

    name: str
    media_type: str
    size_bytes: int


class LocalRunSource(CamelModel):
    """Configured root scanned by the read-only indexer."""

    id: str
    path: str
    writable: bool
    exists: bool


class LocalRunSummary(CamelModel):
    """Safe list/detail projection of one disk-backed run."""

    id: str
    source_id: str
    name: str
    path: str
    target: str | None = None
    scan_mode: str | None = None
    state: RunState
    engine_status: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    updated_at: datetime
    severity_counts: SeverityCounts
    artifacts: list[ArtifactInfo]
    diagnostic: str | None = None


class LocalRunsResponse(CamelModel):
    """Fresh index result and the roots that produced it."""

    schema_version: int = 1
    scanned_at: datetime
    sources: list[LocalRunSource]
    runs: list[LocalRunSummary]
