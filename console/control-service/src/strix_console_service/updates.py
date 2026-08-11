from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
from collections.abc import Callable
from typing import Any, Protocol
from urllib.request import Request, urlopen

from strix_console_service import __version__
from strix_console_service.contracts import (
    ApplicationUpdate,
    SandboxPullStatus,
    SandboxUpdate,
)
from strix_console_service.system_checks import CommandResult

_REPOSITORY = "haodehaode378/strix-for-see"
_APPLICATION_RELEASE_URL = f"https://api.github.com/repos/{_REPOSITORY}/releases/latest"
_SANDBOX_VERSION = "1.3.0"
_SANDBOX_IMAGE = f"ghcr.io/usestrix/strix-sandbox:{_SANDBOX_VERSION}"
_SANDBOX_DIGEST = "sha256:f6906c3114e504fd1a218fcf028d7a0e46851118403a438b63956de6ea7c4331"
_SANDBOX_SIZE_BYTES = 1_442_839_765
_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
_PULL_PROGRESS_PATTERN = re.compile(
    r"^(?P<layer>[0-9a-f]+):\s+Downloading.*?"
    r"(?P<current>\d+(?:\.\d+)?)\s*(?P<current_unit>[kMGT]?B)"
    r"/(?P<total>\d+(?:\.\d+)?)\s*(?P<total_unit>[kMGT]?B)",
    re.IGNORECASE,
)


class UpdateError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class JsonFetcher(Protocol):
    def __call__(self, url: str) -> dict[str, Any]: ...


PullRunner = Callable[[str, Callable[[int], None]], int]


class UpdateService:
    """Fixed-source application and Sandbox updates with active-scan guards."""

    def __init__(
        self,
        *,
        scan_active: Callable[[], bool],
        fetch_json: JsonFetcher | None = None,
        command_runner: Callable[[list[str]], CommandResult] | None = None,
        pull_runner: PullRunner | None = None,
    ) -> None:
        self.scan_active = scan_active
        self.fetch_json = fetch_json or _fetch_json
        self.command_runner = command_runner or _run_command
        self.pull_runner = pull_runner or _pull_image
        self._sandbox: SandboxUpdate | None = None
        self._pull_status = SandboxPullStatus()
        self._lock = threading.Lock()

    def check_application(self) -> ApplicationUpdate:
        release = self.fetch_json(_APPLICATION_RELEASE_URL)
        if release.get("draft") is True or release.get("prerelease") is True:
            raise UpdateError("stableReleaseUnavailable")
        latest = _version(str(release.get("tag_name", "")))
        assets = release.get("assets", [])
        installable = isinstance(assets, list) and any(
            isinstance(item, dict) and item.get("name") == "latest.json" for item in assets
        )
        return ApplicationUpdate(
            current_version=__version__,
            latest_version=latest,
            available=_version_tuple(latest) > _version_tuple(__version__),
            installable=installable,
            release_url=_https_url(release.get("html_url")),
            published_at=release.get("published_at"),
        )

    def authorize_application_update(self) -> None:
        if self.scan_active():
            raise UpdateError("scanActive")

    def check_sandbox(self) -> SandboxUpdate:
        current = self._local_sandbox_version()
        result = SandboxUpdate(
            current_version=current,
            latest_version=_SANDBOX_VERSION,
            image=_SANDBOX_IMAGE,
            digest=_SANDBOX_DIGEST,
            size_bytes=_SANDBOX_SIZE_BYTES,
            compatible=True,
            available=current != _SANDBOX_VERSION,
        )
        with self._lock:
            self._sandbox = result
        return result

    def start_sandbox_pull(self, *, confirmed: bool) -> SandboxPullStatus:
        if not confirmed:
            raise UpdateError("sandboxConfirmationRequired")
        if self.scan_active():
            raise UpdateError("scanActive")
        with self._lock:
            if self._pull_status.state in {"downloading", "verifying"}:
                raise UpdateError("sandboxPullInProgress")
            sandbox = self._sandbox
            if sandbox is None:
                raise UpdateError("sandboxCheckRequired")
            if not sandbox.compatible:
                raise UpdateError("sandboxIncompatible")
            resolved_image = f"{sandbox.image}@{sandbox.digest}"
            self._pull_status = SandboxPullStatus(
                state="downloading",
                version=sandbox.latest_version,
                image=sandbox.image,
                total_bytes=sandbox.size_bytes,
            )
        threading.Thread(
            target=self._pull_worker,
            args=(resolved_image,),
            name="strix-console-sandbox-pull",
            daemon=True,
        ).start()
        return self.pull_status()

    def pull_status(self) -> SandboxPullStatus:
        with self._lock:
            return self._pull_status.model_copy()

    def _pull_worker(self, resolved_image: str) -> None:
        def progress(downloaded: int) -> None:
            with self._lock:
                self._pull_status.downloaded_bytes = min(
                    max(downloaded, self._pull_status.downloaded_bytes),
                    self._pull_status.total_bytes,
                )

        return_code = self.pull_runner(resolved_image, progress)
        with self._lock:
            if return_code != 0:
                self._pull_status.state = "failed"
                self._pull_status.error_code = "sandboxPullFailed"
                return
            self._pull_status.state = "verifying"
        result = self.command_runner(["docker", "image", "inspect", resolved_image])
        if result.return_code == 0:
            result = self.command_runner(
                ["docker", "image", "tag", resolved_image, self._pull_status.image or ""]
            )
        with self._lock:
            if result.return_code == 0:
                self._pull_status.state = "completed"
                self._pull_status.downloaded_bytes = self._pull_status.total_bytes
            else:
                self._pull_status.state = "failed"
                self._pull_status.error_code = "sandboxVerificationFailed"

    def _local_sandbox_version(self) -> str | None:
        result = self.command_runner(
            [
                "docker",
                "image",
                "inspect",
                _SANDBOX_IMAGE,
                "--format",
                "{{.Id}}",
            ]
        )
        return _SANDBOX_VERSION if result.return_code == 0 else None


def _fetch_json(url: str) -> dict[str, Any]:
    request = Request(  # noqa: S310
        url,
        headers={
            "Accept": "application/vnd.github+json, application/json",
            "User-Agent": f"Strix-Console/{__version__}",
        },
    )
    with urlopen(request, timeout=10) as response:  # noqa: S310
        payload = response.read(1_048_577)
    if len(payload) > 1_048_576:
        raise UpdateError("updateResponseTooLarge")
    result = json.loads(payload)
    if not isinstance(result, dict):
        raise UpdateError("invalidUpdateResponse")
    return result


def _run_command(command: list[str]) -> CommandResult:
    try:
        completed = subprocess.run(  # noqa: S603
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return CommandResult(return_code=-1)
    return CommandResult(completed.returncode, completed.stdout.strip())


def _pull_image(image: str, progress: Callable[[int], None]) -> int:
    docker = shutil.which("docker")
    if docker is None:
        return -1
    process = subprocess.Popen(  # noqa: S603
        [docker, "pull", image],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    layers: dict[str, int] = {}
    if process.stdout is not None:
        for line in process.stdout:
            parsed = _parse_pull_progress(line)
            if parsed is not None:
                layer, downloaded = parsed
                layers[layer] = downloaded
                progress(sum(layers.values()))
    return process.wait()


def _parse_pull_progress(line: str) -> tuple[str, int] | None:
    match = _PULL_PROGRESS_PATTERN.search(line.strip())
    if match is None:
        return None
    return (
        match.group("layer"),
        _bytes(float(match.group("current")), match.group("current_unit")),
    )


def _bytes(value: float, unit: str) -> int:
    powers = {"b": 0, "kb": 1, "mb": 2, "gb": 3, "tb": 4}
    return int(value * 1024 ** powers[unit.lower()])


def _version(value: str) -> str:
    normalized = value.removeprefix("v")
    if not _VERSION_PATTERN.fullmatch(normalized):
        raise UpdateError("invalidReleaseVersion")
    return normalized


def _version_tuple(value: str) -> tuple[int, int, int]:
    core = value.split("-", 1)[0].split("+", 1)[0]
    major, minor, patch = core.split(".")
    return int(major), int(minor), int(patch)


def _https_url(value: object) -> str | None:
    return value if isinstance(value, str) and value.startswith("https://") else None
