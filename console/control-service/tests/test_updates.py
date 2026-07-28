from pathlib import Path
from time import sleep

import pytest
from fastapi.testclient import TestClient

from strix_console_service.app import create_app
from strix_console_service.audit import AuditLog
from strix_console_service.local_runs import RunRoot
from strix_console_service.system_checks import CommandResult
from strix_console_service.updates import UpdateError, UpdateService, _parse_pull_progress

ACCESS_TOKEN = "test-access-token"
BOOTSTRAP_TOKEN = "test-bootstrap-token"
HEADERS = {"X-Strix-Access-Token": ACCESS_TOKEN}
DIGEST = f"sha256:{'a' * 64}"


def _fetcher(url: str) -> dict[str, object]:
    if url.endswith("/releases/latest"):
        return {
            "tag_name": "v0.2.0",
            "draft": False,
            "prerelease": False,
            "html_url": "https://github.com/haodehaode378/strix-for-see/releases/tag/v0.2.0",
            "published_at": "2026-07-28T00:00:00Z",
            "assets": [{"name": "latest.json"}],
        }
    return {
        "version": "1.4.0",
        "image": "ghcr.io/haodehaode378/strix-for-see-sandbox:1.4.0",
        "digest": DIGEST,
        "sizeBytes": 123_456,
        "minimumAppVersion": "0.1.0",
        "maximumAppVersion": "0.9.0",
    }


def test_update_checks_are_stable_fixed_source_and_compatible() -> None:
    commands: list[list[str]] = []

    def command_runner(command: list[str]) -> CommandResult:
        commands.append(command)
        return CommandResult(1)

    service = UpdateService(
        scan_active=lambda: False,
        fetch_json=_fetcher,
        command_runner=command_runner,
    )

    application = service.check_application()
    sandbox = service.check_sandbox()

    assert application.available
    assert application.installable
    assert application.latest_version == "0.2.0"
    assert sandbox.compatible
    assert sandbox.available
    assert sandbox.size_bytes == 123_456
    assert commands[0][0:3] == ["docker", "image", "inspect"]


def test_updates_are_blocked_while_a_scan_is_active() -> None:
    service = UpdateService(scan_active=lambda: True, fetch_json=_fetcher)
    service.check_sandbox()

    with pytest.raises(UpdateError, match="scanActive"):
        service.authorize_application_update()
    with pytest.raises(UpdateError, match="scanActive"):
        service.start_sandbox_pull(confirmed=True)


def test_sandbox_pull_requires_confirmation_and_uses_resolved_digest() -> None:
    pulled: list[str] = []

    def pull_runner(image: str, _progress: object) -> int:
        pulled.append(image)
        return 0

    service = UpdateService(
        scan_active=lambda: False,
        fetch_json=_fetcher,
        command_runner=lambda _command: CommandResult(0),
        pull_runner=pull_runner,
    )
    service.check_sandbox()

    with pytest.raises(UpdateError, match="sandboxConfirmationRequired"):
        service.start_sandbox_pull(confirmed=False)
    service.start_sandbox_pull(confirmed=True)

    for _ in range(100):
        if service.pull_status().state == "completed":
            break
        sleep(0.001)
    assert pulled == [
        f"ghcr.io/haodehaode378/strix-for-see-sandbox:1.4.0@{DIGEST}"
    ]
    assert service.pull_status().downloaded_bytes == 123_456


def test_update_api_never_accepts_an_image_from_the_browser(tmp_path: Path) -> None:
    service = UpdateService(
        scan_active=lambda: False,
        fetch_json=_fetcher,
        command_runner=lambda _command: CommandResult(1),
        pull_runner=lambda _image, _progress: 1,
    )
    client = TestClient(
        create_app(
            access_token=ACCESS_TOKEN,
            bootstrap_token=BOOTSTRAP_TOKEN,
            run_roots=[RunRoot(tmp_path / "runs", writable=True)],
            update_service=service,
        )
    )

    checked = client.get("/api/updates/sandbox", headers=HEADERS)
    started = client.post(
        "/api/updates/sandbox/pull",
        headers=HEADERS,
        json={"confirmed": True, "image": "evil.example/image:latest"},
    )

    assert checked.status_code == 200
    assert started.status_code == 200
    assert started.json()["image"].startswith(
        "ghcr.io/haodehaode378/strix-for-see-sandbox:"
    )


def test_audit_summary_ignores_corrupt_lines_and_never_stores_bodies(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    audit = AuditLog(path)
    audit.append("provider.configured", "success")
    with path.open("a", encoding="utf-8") as handle:
        handle.write("{broken\n")

    summary = audit.summary()

    assert summary.total_events == 1
    assert summary.corrupt_entries == 1
    assert summary.recent_actions == ["provider.configured"]
    assert "apiKey" not in path.read_text(encoding="utf-8")


def test_docker_pull_progress_is_parsed_without_exposing_output() -> None:
    assert _parse_pull_progress(
        "a1b2c3: Downloading [=======>]  12.5MB/40MB"
    ) == ("a1b2c3", 13_107_200)
    assert _parse_pull_progress("a1b2c3: Pull complete") is None
