from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from strix_console_service.contracts import (
    ArtifactInfo,
    LocalRunSource,
    LocalRunsResponse,
    LocalRunSummary,
    RunState,
    SeverityCounts,
)
from strix_console_service.system_checks import redact_text

_ARTIFACTS: dict[str, str] = {
    "run.json": "application/json",
    "vulnerabilities.json": "application/json",
    "vulnerabilities.csv": "text/csv",
    "penetration_test_report.md": "text/markdown",
    "penetration_test_report.pdf": "application/pdf",
    "findings.sarif": "application/sarif+json",
}
_ACTIVE_STATUSES = {"validating", "queued", "preparing", "running", "reporting", "stopping"}
_INTERRUPTED_STATUSES = {"failed", "interrupted", "stopped", "terminated"}
_KNOWN_SEVERITIES = {"critical", "high", "medium", "low"}


@dataclass(frozen=True)
class RunRoot:
    """One resolved directory the indexer is allowed to inspect."""

    path: Path
    writable: bool

    @property
    def id(self) -> str:
        normalized = str(self.path).casefold().encode("utf-8")
        return hashlib.sha256(normalized).hexdigest()[:16]


@dataclass(frozen=True)
class ResolvedArtifact:
    """Internal artifact resolution result."""

    path: Path
    media_type: str


class LocalRunIndexer:
    """Build a disposable index from configured local run roots."""

    def __init__(self, roots: list[RunRoot]) -> None:
        deduplicated: dict[str, RunRoot] = {}
        for root in roots:
            resolved = RunRoot(path=root.path.expanduser().resolve(), writable=root.writable)
            existing = deduplicated.get(resolved.id)
            if existing is None or resolved.writable:
                deduplicated[resolved.id] = resolved
        self.roots = list(deduplicated.values())

    @classmethod
    def from_environment(cls, environment: dict[str, str] | None = None) -> LocalRunIndexer:
        env = environment if environment is not None else dict(os.environ)
        local_app_data = env.get("LOCALAPPDATA")
        if local_app_data:
            default_root = Path(local_app_data) / "StrixConsole" / "runs"
        else:
            default_root = Path.home() / "AppData" / "Local" / "StrixConsole" / "runs"

        roots = [RunRoot(path=default_root, writable=True)]
        configured = env.get("STRIX_CONSOLE_RUN_ROOTS", "")
        for value in configured.split(os.pathsep):
            if value.strip():
                roots.append(RunRoot(path=Path(value.strip()), writable=False))
        return cls(roots)

    @property
    def default_root(self) -> Path:
        return self.roots[0].path

    def list_runs(self) -> LocalRunsResponse:
        runs: list[LocalRunSummary] = []
        for root in self.roots:
            runs.extend(self._runs_in_root(root))
        runs.sort(key=lambda run: run.updated_at, reverse=True)
        return LocalRunsResponse(
            scanned_at=datetime.now(UTC),
            sources=[
                LocalRunSource(
                    id=root.id,
                    path=_display_value(str(root.path)),
                    writable=root.writable,
                    exists=root.path.is_dir(),
                )
                for root in self.roots
            ],
            runs=runs,
        )

    def get_run(self, run_id: str) -> LocalRunSummary | None:
        for run in self.list_runs().runs:
            if run.id == run_id:
                return run
        return None

    def resolve_artifact(self, run_id: str, artifact_name: str) -> ResolvedArtifact | None:
        media_type = _ARTIFACTS.get(artifact_name)
        if media_type is None:
            return None
        run_path = self._resolve_run_path(run_id)
        if run_path is None:
            return None
        candidate = (run_path / artifact_name).resolve()
        if candidate.parent != run_path or not candidate.is_file():
            return None
        return ResolvedArtifact(path=candidate, media_type=media_type)

    def _resolve_run_path(self, run_id: str) -> Path | None:
        for root in self.roots:
            for candidate in self._candidate_directories(root):
                if self._run_id(root, candidate.name) == run_id:
                    return candidate
        return None

    def _runs_in_root(self, root: RunRoot) -> list[LocalRunSummary]:
        return [self._summarize(root, candidate) for candidate in self._candidate_directories(root)]

    def _candidate_directories(self, root: RunRoot) -> list[Path]:
        if not root.path.is_dir():
            return []
        try:
            children = list(root.path.iterdir())
        except OSError:
            return []

        candidates: list[Path] = []
        for child in children:
            try:
                resolved = child.resolve()
                if child.is_dir() and resolved.parent == root.path:
                    candidates.append(resolved)
            except OSError:
                continue
        return candidates

    def _summarize(self, root: RunRoot, run_path: Path) -> LocalRunSummary:
        run_record_path = run_path / "run.json"
        updated_at = _updated_at(run_record_path if run_record_path.exists() else run_path)
        artifacts = _artifact_list(run_path)
        record, record_issue = _read_record(run_record_path)
        severity_counts, vulnerability_issue = _read_severity_counts(
            run_path / "vulnerabilities.json"
        )

        if record_issue == "invalidRunRecord":
            state: RunState = "malformed"
        elif record is None:
            state = "partial"
        else:
            state = _derive_state(record)

        diagnostic = record_issue or vulnerability_issue
        target = _primary_target(record) if record is not None else None
        return LocalRunSummary(
            id=self._run_id(root, run_path.name),
            source_id=root.id,
            name=_string_value(record, "run_name") or run_path.name,
            path=_display_value(str(run_path)),
            target=_display_value(target) if target is not None else None,
            scan_mode=_string_value(record, "scan_mode"),
            state=state,
            engine_status=_string_value(record, "status"),
            start_time=_string_value(record, "start_time"),
            end_time=_string_value(record, "end_time"),
            updated_at=updated_at,
            severity_counts=severity_counts,
            artifacts=artifacts,
            diagnostic=diagnostic,
        )

    @staticmethod
    def _run_id(root: RunRoot, name: str) -> str:
        raw = f"{root.id}\0{name}".encode()
        return hashlib.sha256(raw).hexdigest()[:24]


def _read_record(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, "missingRunRecord"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, "invalidRunRecord"
    if not isinstance(data, dict):
        return None, "invalidRunRecord"
    return data, None


def _derive_state(record: dict[str, Any]) -> RunState:
    status = _string_value(record, "status")
    end_time = _string_value(record, "end_time")
    if status == "completed" and end_time:
        return "completed"
    if status in _INTERRUPTED_STATUSES:
        return "interrupted"
    if status in _ACTIVE_STATUSES:
        return "active"
    return "partial"


def _read_severity_counts(path: Path) -> tuple[SeverityCounts, str | None]:
    if not path.is_file():
        return SeverityCounts(), None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return SeverityCounts(), "invalidVulnerabilities"
    if not isinstance(data, list):
        return SeverityCounts(), "invalidVulnerabilities"

    counts = {severity: 0 for severity in _KNOWN_SEVERITIES}
    for item in data:
        raw_severity = item.get("severity") if isinstance(item, dict) else None
        severity = str(raw_severity or "").strip().lower()
        if severity not in _KNOWN_SEVERITIES:
            severity = "low"
        counts[severity] += 1
    return SeverityCounts(**counts), None


def _artifact_list(run_path: Path) -> list[ArtifactInfo]:
    artifacts: list[ArtifactInfo] = []
    for name, media_type in _ARTIFACTS.items():
        path = run_path / name
        try:
            if path.is_file():
                artifacts.append(
                    ArtifactInfo(name=name, media_type=media_type, size_bytes=path.stat().st_size)
                )
        except OSError:
            continue
    return artifacts


def _primary_target(record: dict[str, Any]) -> str | None:
    targets = record.get("targets_info")
    if not isinstance(targets, list):
        return None
    for item in targets:
        if isinstance(item, dict):
            original = item.get("original")
            if isinstance(original, str) and original:
                return original
    return None


def _string_value(record: dict[str, Any] | None, key: str) -> str | None:
    if record is None:
        return None
    value = record.get(key)
    return value if isinstance(value, str) and value else None


def _updated_at(path: Path) -> datetime:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    except OSError:
        return datetime.fromtimestamp(0, tz=UTC)


def _display_value(value: str) -> str:
    return redact_text(value, home=Path.home())
