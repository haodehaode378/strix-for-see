from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from strix_console_service.contracts import (
    DiagnosticReport,
    SystemCheck,
    SystemReport,
    SystemSummary,
)

_MINIMUM_FREE_BYTES = 5 * 1024**3
_DEFAULT_SANDBOX_IMAGE = "ghcr.io/haodehaode378/strix-for-see-sandbox:latest"
_VERSION_PATTERN = re.compile(r"\d+(?:\.\d+){1,3}")


@dataclass(frozen=True)
class CommandResult:
    """Safe subprocess result used by readiness probes."""

    return_code: int
    stdout: str = ""


CommandRunner = Callable[[list[str]], CommandResult]


class SystemInspector:
    """Run bounded, non-mutating readiness probes."""

    def __init__(
        self,
        *,
        run_root: Path,
        environment: dict[str, str] | None = None,
        command_runner: CommandRunner | None = None,
        which: Callable[[str], str | None] = shutil.which,
        platform_name: str = sys.platform,
    ) -> None:
        self.run_root = run_root
        self.environment = environment if environment is not None else dict(os.environ)
        self.command_runner = command_runner or _run_command
        self.which = which
        self.platform_name = platform_name

    def inspect(self) -> SystemReport:
        checks = [
            self._windows_check(),
            SystemCheck(
                id="controlService",
                status="ready",
                requirement="required",
                value="connected",
            ),
            self._storage_check(),
            self._disk_check(),
            self._strix_check(),
            self._docker_cli_check(),
        ]
        docker_path = self.which("docker")
        docker_ready = docker_path is not None
        daemon_check = self._docker_daemon_check(docker_path)
        checks.append(daemon_check)
        checks.extend(
            [
                self._wsl_check(),
                self._git_check(),
                self._sandbox_check(
                    docker_path if docker_ready and daemon_check.status == "ready" else None
                ),
                self._provider_check(),
            ]
        )

        required = [check for check in checks if check.requirement == "required"]
        required_ready = sum(check.status == "ready" for check in required)
        optional_warnings = sum(
            check.requirement == "optional" and check.status != "ready" for check in checks
        )
        summary = SystemSummary(
            ready=required_ready == len(required),
            required_total=len(required),
            required_ready=required_ready,
            required_failures=len(required) - required_ready,
            optional_warnings=optional_warnings,
        )
        return SystemReport(generated_at=datetime.now(UTC), summary=summary, checks=checks)

    def diagnostics(self) -> DiagnosticReport:
        report = DiagnosticReport(system=self.inspect())
        raw = report.model_dump_json(by_alias=True)
        redacted = redact_text(raw, home=Path.home())
        return DiagnosticReport.model_validate_json(redacted)

    def _windows_check(self) -> SystemCheck:
        if self.platform_name == "win32":
            return SystemCheck(
                id="windows",
                status="ready",
                requirement="required",
                value=platform.release(),
            )
        return SystemCheck(
            id="windows",
            status="missing",
            requirement="required",
            issue="unsupportedPlatform",
        )

    def _storage_check(self) -> SystemCheck:
        probe = self.run_root if self.run_root.exists() else _nearest_existing_parent(self.run_root)
        if probe is not None and os.access(probe, os.W_OK):
            return SystemCheck(
                id="storage",
                status="ready",
                requirement="required",
                value=_display_path(self.run_root),
            )
        return SystemCheck(
            id="storage",
            status="error",
            requirement="required",
            value=_display_path(self.run_root),
            issue="notWritable",
        )

    def _disk_check(self) -> SystemCheck:
        probe = self.run_root if self.run_root.exists() else _nearest_existing_parent(self.run_root)
        if probe is None:
            return SystemCheck(
                id="disk",
                status="error",
                requirement="required",
                issue="unavailable",
            )
        try:
            free = shutil.disk_usage(probe).free
        except OSError:
            return SystemCheck(
                id="disk",
                status="error",
                requirement="required",
                issue="unavailable",
            )
        return SystemCheck(
            id="disk",
            status="ready" if free >= _MINIMUM_FREE_BYTES else "warning",
            requirement="required",
            value=f"{free / 1024**3:.1f} GB",
            issue=None if free >= _MINIMUM_FREE_BYTES else "lowDiskSpace",
        )

    def _strix_check(self) -> SystemCheck:
        configured_path = self.environment.get("STRIX_CONSOLE_STRIX_PATH")
        candidate = configured_path or self.which("strix")
        if candidate and Path(candidate).exists():
            return SystemCheck(
                id="strix",
                status="ready",
                requirement="required",
                value="configured",
            )
        return SystemCheck(
            id="strix",
            status="missing",
            requirement="required",
            issue="notBundled",
        )

    def _docker_cli_check(self) -> SystemCheck:
        if self.which("docker"):
            return SystemCheck(
                id="dockerCli",
                status="ready",
                requirement="required",
                value="detected",
            )
        return SystemCheck(
            id="dockerCli",
            status="missing",
            requirement="required",
            issue="notInstalled",
        )

    def _docker_daemon_check(self, docker_path: str | None) -> SystemCheck:
        if docker_path is None:
            return SystemCheck(
                id="dockerDaemon",
                status="missing",
                requirement="required",
                issue="dockerCliMissing",
            )
        result = self.command_runner(
            [docker_path, "info", "--format", "{{.ServerVersion}}"]
        )
        if result.return_code != 0:
            return SystemCheck(
                id="dockerDaemon",
                status="error",
                requirement="required",
                issue="notRunning",
            )
        version = _safe_version(result.stdout)
        return SystemCheck(
            id="dockerDaemon",
            status="ready",
            requirement="required",
            value=version or "running",
        )

    def _wsl_check(self) -> SystemCheck:
        wsl_path = self.which("wsl")
        if wsl_path is None:
            return SystemCheck(
                id="wsl",
                status="warning",
                requirement="optional",
                issue="notInstalled",
            )
        result = self.command_runner([wsl_path, "--status"])
        return SystemCheck(
            id="wsl",
            status="ready" if result.return_code == 0 else "warning",
            requirement="optional",
            value="available" if result.return_code == 0 else None,
            issue=None if result.return_code == 0 else "statusUnavailable",
        )

    def _git_check(self) -> SystemCheck:
        git_path = self.which("git")
        if git_path is None:
            return SystemCheck(
                id="git",
                status="warning",
                requirement="optional",
                issue="notInstalled",
            )
        result = self.command_runner([git_path, "--version"])
        version = _safe_version(result.stdout)
        value = (version or "detected") if result.return_code == 0 else None
        return SystemCheck(
            id="git",
            status="ready" if result.return_code == 0 else "warning",
            requirement="optional",
            value=value,
            issue=None if result.return_code == 0 else "commandFailed",
        )

    def _sandbox_check(self, docker_path: str | None) -> SystemCheck:
        image = self.environment.get("STRIX_CONSOLE_SANDBOX_IMAGE", _DEFAULT_SANDBOX_IMAGE)
        if docker_path is None:
            return SystemCheck(
                id="sandbox",
                status="warning",
                requirement="optional",
                value=image,
                issue="dockerUnavailable",
            )
        result = self.command_runner(
            [docker_path, "image", "inspect", image, "--format", "{{.Id}}"]
        )
        return SystemCheck(
            id="sandbox",
            status="ready" if result.return_code == 0 else "warning",
            requirement="optional",
            value=image,
            issue=None if result.return_code == 0 else "imageMissing",
        )

    def _provider_check(self) -> SystemCheck:
        configured = bool(
            self.environment.get("STRIX_LLM")
            and (
                self.environment.get("LLM_API_KEY")
                or self.environment.get("OPENAI_API_KEY")
                or self.environment.get("ANTHROPIC_API_KEY")
                or self.environment.get("GEMINI_API_KEY")
            )
        )
        return SystemCheck(
            id="provider",
            status="ready" if configured else "warning",
            requirement="optional",
            value="configured" if configured else None,
            issue=None if configured else "notConfigured",
        )


def redact_text(value: str, *, home: Path | None = None) -> str:
    """Redact common secret forms and the current user's home path."""

    redacted = value
    if home is not None:
        redacted = re.sub(re.escape(str(home)), "%USERPROFILE%", redacted, flags=re.IGNORECASE)
    redacted = re.sub(r"(?i)(?<=://)[^/@\s]+@", "[REDACTED]@", redacted)
    redacted = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", redacted)
    redacted = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "[REDACTED]", redacted)
    redacted = re.sub(
        r'(?i)(api[_-]?key|token|password)(["\']?\s*[:=]\s*["\']?)[^"\',\s}]+',
        r"\1\2[REDACTED]",
        redacted,
    )
    return redacted


def _run_command(command: list[str]) -> CommandResult:
    creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            creationflags=creation_flags,
        )
    except (OSError, subprocess.TimeoutExpired):
        return CommandResult(return_code=-1)
    return CommandResult(return_code=completed.returncode, stdout=completed.stdout.strip())


def _safe_version(value: str) -> str | None:
    match = _VERSION_PATTERN.search(value)
    return match.group(0) if match else None


def _nearest_existing_parent(path: Path) -> Path | None:
    candidate = path
    while not candidate.exists():
        parent = candidate.parent
        if parent == candidate:
            return None
        candidate = parent
    return candidate


def _display_path(path: Path) -> str:
    return redact_text(str(path), home=Path.home())
