from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

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
    audit: AuditSummary | None = None
    state_issues: list[str] = Field(default_factory=list)


class AuditSummary(CamelModel):
    """Bounded mutation history without request bodies or target details."""

    total_events: int = 0
    corrupt_entries: int = 0
    recent_actions: list[str] = Field(default_factory=list)


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


TargetType = Literal["web", "local", "repository", "network"]
RiskMode = Literal["safe", "full"]
ScanProfile = Literal["quick", "standard", "deep"]
TerminationPolicy = Literal["consoleLimits", "strixRules"]
ScanStatus = Literal[
    "validating",
    "queued",
    "preparing",
    "running",
    "reporting",
    "completed",
    "stopping",
    "stopped",
    "terminating",
    "terminated",
    "failed",
]


class ScopeConfig(CamelModel):
    """Explicit scope attached to exactly one primary target."""

    allowed_hosts: list[str] = Field(default_factory=list, max_length=50)
    allowed_ports: list[int] = Field(default_factory=list, max_length=100)
    allowed_paths: list[str] = Field(default_factory=list, max_length=100)
    exclusions: list[str] = Field(default_factory=list, max_length=100)


class ScanOptions(CamelModel):
    """Bounded runtime settings supported by the control service."""

    risk_mode: RiskMode = "safe"
    scan_profile: ScanProfile = "standard"
    termination_policy: TerminationPolicy = "consoleLimits"
    request_rate_per_minute: int = Field(default=30, ge=1, le=120)
    max_duration_minutes: int = Field(default=60, ge=5, le=1440)
    max_budget_usd: float = Field(default=10, ge=0.01, le=1000)
    instructions: str = Field(default="", max_length=4000)


class CreateScanRequest(CamelModel):
    """Validated scan launch request without secret material."""

    target_type: TargetType
    target: str = Field(min_length=1, max_length=2048)
    scope: ScopeConfig = Field(default_factory=ScopeConfig)
    options: ScanOptions = Field(default_factory=ScanOptions)
    authorization_confirmed: bool = False
    full_mode_confirmed: bool = False


class ScanSummary(CamelModel):
    """Browser-safe projection of one persistent queue item."""

    id: str
    status: ScanStatus
    target_type: TargetType
    target: str
    scope: ScopeConfig
    options: ScanOptions
    queue_position: int | None = None
    engine_run_name: str
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    ended_at: datetime | None = None
    process_id: int | None = None
    error_code: str | None = None


class ScanListResponse(CamelModel):
    """Persistent queue snapshot."""

    schema_version: int = 1
    scans: list[ScanSummary]


class TerminateScanRequest(CamelModel):
    """Separate confirmation for emergency process termination."""

    confirmed: bool = False


class ApplicationUpdate(CamelModel):
    """Stable GitHub release metadata safe to display in the browser."""

    current_version: str
    latest_version: str | None = None
    available: bool = False
    installable: bool = False
    release_url: str | None = None
    published_at: datetime | None = None


class UpdateAuthorization(CamelModel):
    """Result of the final active-scan guard before a desktop update."""

    allowed: bool = True


class SandboxUpdate(CamelModel):
    """Compatible Sandbox release plus local image state."""

    current_version: str | None = None
    latest_version: str
    image: str
    digest: str
    size_bytes: int
    compatible: bool
    available: bool


class SandboxPullRequest(CamelModel):
    """Explicit confirmation required before downloading an image."""

    confirmed: bool = False


SandboxPullState = Literal["idle", "downloading", "verifying", "completed", "failed"]


class SandboxPullStatus(CamelModel):
    """Observable Docker pull state; old images are never removed."""

    state: SandboxPullState = "idle"
    version: str | None = None
    image: str | None = None
    downloaded_bytes: int = 0
    total_bytes: int = 0
    error_code: str | None = None


EventActorKind = Literal["scan", "agent", "tool", "runtime", "operator", "system"]


class EventActor(CamelModel):
    kind: EventActorKind
    id: str | None = None


class ScanEvent(CamelModel):
    """Versioned browser-safe event persisted before delivery."""

    schema_version: int = 1
    event_id: str
    scan_id: str
    occurred_at: datetime
    type: str
    actor: EventActor | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    source_key: str | None = Field(default=None, exclude=True)


class ScanEventsResponse(CamelModel):
    schema_version: int = 1
    events: list[ScanEvent]


class SteeringRequest(CamelModel):
    message: str = Field(min_length=1, max_length=2000)


class SteeringResponse(CamelModel):
    accepted: bool
    event_id: str


FindingSeverity = Literal["critical", "high", "medium", "low"]
FindingWorkflowState = Literal["pending", "confirmed", "acceptedRisk", "fixed", "falsePositive"]


class FindingLocation(CamelModel):
    """Bounded source or endpoint location attached to a finding."""

    file: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    label: str | None = None
    snippet: str | None = None


class FindingOccurrence(CamelModel):
    """One appearance of a stable finding in a local Strix run."""

    run_id: str
    run_name: str
    target: str | None = None
    source_finding_id: str | None = None
    observed_at: str | None = None


class FindingHistoryEntry(CamelModel):
    """Append-only local review event."""

    id: str
    occurred_at: datetime
    kind: Literal["stateChanged", "noteAdded"]
    from_state: FindingWorkflowState | None = None
    to_state: FindingWorkflowState | None = None
    note: str | None = None


class FindingExplanationDetails(CamelModel):
    """Evidence-backed facts used by the UI and every export renderer."""

    interface_or_feature: str | None = None
    affected_inputs: list[str] = Field(default_factory=list, max_length=100)
    prerequisites: str | None = None
    trigger_behavior: str | None = None
    real_impact: str | None = None


class Finding(CamelModel):
    """Safe aggregate of one issue across local runs."""

    id: str
    fingerprint_version: int = 1
    title: str
    severity: FindingSeverity
    workflow_state: FindingWorkflowState = "pending"
    target: str | None = None
    description: str | None = None
    impact: str | None = None
    technical_analysis: str | None = None
    evidence: str | None = None
    poc_description: str | None = None
    poc_script_code: str | None = None
    remediation_steps: str | None = None
    endpoint: str | None = None
    method: str | None = None
    affected_inputs: list[str] = Field(default_factory=list, max_length=100)
    cve: str | None = None
    cwe: str | None = None
    cvss: float | None = None
    locations: list[FindingLocation] = Field(default_factory=list)
    occurrences: list[FindingOccurrence] = Field(default_factory=list)
    history: list[FindingHistoryEntry] = Field(default_factory=list)
    explanation: FindingExplanationDetails = Field(default_factory=FindingExplanationDetails)


class FindingsResponse(CamelModel):
    schema_version: int = 1
    generated_at: datetime
    findings: list[Finding]
    severity_counts: SeverityCounts


class UpdateFindingRequest(CamelModel):
    workflow_state: FindingWorkflowState | None = None
    note: str | None = Field(default=None, min_length=1, max_length=4000)


class FindingTranslation(CamelModel):
    """Chinese translations of descriptive fields; exploit evidence is intentionally excluded."""

    title: str | None = None
    description: str | None = None
    impact: str | None = None
    technical_analysis: str | None = None
    remediation_steps: str | None = None
    interface_or_feature: str | None = None
    prerequisites: str | None = None
    trigger_behavior: str | None = None
    real_impact: str | None = None


ReportFormat = Literal["html", "pdf", "markdown", "json"]
ReportLocale = Literal["zh-CN", "en-US"]


class ReportRedaction(CamelModel):
    omit_evidence: bool = True
    omit_poc: bool = True
    omit_paths: bool = True


class ExportFindingsRequest(CamelModel):
    format: ReportFormat
    locale: ReportLocale = "zh-CN"
    run_id: str = Field(min_length=1, max_length=64)
    finding_ids: list[str] = Field(default_factory=list, max_length=500)
    redaction: ReportRedaction = Field(default_factory=ReportRedaction)


class ExportFindingsResponse(CamelModel):
    filename: str
    display_path: str
    run_id: str
    run_name: str | None = None


ProviderKind = Literal["openai", "anthropic", "gemini", "openaiCompatible", "ollama"]


class ProviderConfigRequest(CamelModel):
    """Provider settings; api_key is write-only and never returned."""

    provider: ProviderKind
    model: str = Field(min_length=1, max_length=200)
    api_base: str | None = Field(default=None, max_length=2048)
    api_key: str | None = Field(default=None, min_length=1, max_length=1200)


class ProviderModelsRequest(CamelModel):
    """Write-only connection details used to discover available model identifiers."""

    provider: ProviderKind
    api_base: str | None = Field(default=None, max_length=2048)
    api_key: str | None = Field(default=None, min_length=1, max_length=1200)


class ProviderModelsResponse(CamelModel):
    """Bounded model identifiers returned by a provider without response metadata."""

    models: list[str] = Field(default_factory=list, max_length=200)


class ProviderStatus(CamelModel):
    """Safe provider status returned to the browser."""

    configured: bool
    provider: ProviderKind | None = None
    model: str | None = None
    api_base: str | None = None
    has_api_key: bool = False
    connection_verified: bool = False


class ProviderTestResult(CamelModel):
    """Bounded connectivity result without response bodies."""

    ok: bool
    issue: str | None = None
