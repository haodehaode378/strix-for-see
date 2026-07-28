from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from strix_console_service.app import create_app
from strix_console_service.local_runs import LocalRunIndexer, RunRoot

ACCESS_TOKEN = "test-access-token"
BOOTSTRAP_TOKEN = "test-bootstrap-token"
AUTH_HEADERS = {"X-Strix-Access-Token": ACCESS_TOKEN}


def _write_run(root: Path, name: str, record: dict[str, object] | None) -> Path:
    run_path = root / name
    run_path.mkdir(parents=True)
    if record is not None:
        (run_path / "run.json").write_text(json.dumps(record), encoding="utf-8")
    return run_path


def test_indexer_exposes_all_supported_run_states(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    completed = _write_run(
        root,
        "completed",
        {
            "run_name": "Completed scan",
            "targets_info": [{"original": "https://example.com"}],
            "status": "completed",
            "end_time": "2026-07-28T02:00:00Z",
        },
    )
    (completed / "vulnerabilities.json").write_text(
        json.dumps([{"severity": "critical"}, {"severity": "high"}]),
        encoding="utf-8",
    )
    (completed / "penetration_test_report.md").write_text("# Report", encoding="utf-8")
    _write_run(root, "active", {"status": "running"})
    _write_run(root, "interrupted", {"status": "failed"})
    _write_run(root, "partial", None)
    malformed = _write_run(root, "malformed", None)
    (malformed / "run.json").write_text("{not-json", encoding="utf-8")

    response = LocalRunIndexer([RunRoot(root, writable=True)]).list_runs()

    assert {run.state for run in response.runs} == {
        "completed",
        "active",
        "interrupted",
        "partial",
        "malformed",
    }
    completed_summary = next(run for run in response.runs if run.name == "Completed scan")
    assert completed_summary.target == "https://example.com"
    assert completed_summary.severity_counts.critical == 1
    assert completed_summary.severity_counts.high == 1
    assert [artifact.name for artifact in completed_summary.artifacts] == [
        "run.json",
        "vulnerabilities.json",
        "penetration_test_report.md",
    ]


def test_indexer_refreshes_without_restart(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    root.mkdir()
    indexer = LocalRunIndexer([RunRoot(root, writable=True)])

    assert indexer.list_runs().runs == []
    _write_run(root, "later", {"status": "running"})

    assert [run.name for run in indexer.list_runs().runs] == ["later"]


def test_artifacts_are_allowlisted_and_confined_to_run(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    run_path = _write_run(root, "safe-run", {"status": "completed", "end_time": "now"})
    (run_path / "penetration_test_report.md").write_text("safe", encoding="utf-8")
    (run_path / "secret.txt").write_text("secret", encoding="utf-8")
    indexer = LocalRunIndexer([RunRoot(root, writable=True)])
    run_id = indexer.list_runs().runs[0].id

    artifact = indexer.resolve_artifact(run_id, "penetration_test_report.md")

    assert artifact is not None
    assert artifact.path.read_text(encoding="utf-8") == "safe"
    assert indexer.resolve_artifact(run_id, "secret.txt") is None
    assert indexer.resolve_artifact(run_id, "../secret.txt") is None


def test_target_credentials_are_redacted_from_api_projection(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    _write_run(
        root,
        "credentialed-target",
        {
            "status": "running",
            "targets_info": [
                {"original": "https://operator:secret@example.com/path?token=hidden"}
            ],
        },
    )

    target = LocalRunIndexer([RunRoot(root, writable=True)]).list_runs().runs[0].target

    assert target is not None
    assert "operator" not in target
    assert "secret" not in target
    assert "hidden" not in target


def test_local_run_api_requires_auth_and_downloads_allowlisted_artifact(
    tmp_path: Path,
) -> None:
    root = tmp_path / "runs"
    run_path = _write_run(root, "api-run", {"status": "running"})
    (run_path / "findings.sarif").write_text("{}", encoding="utf-8")
    app = create_app(
        access_token=ACCESS_TOKEN,
        bootstrap_token=BOOTSTRAP_TOKEN,
        run_roots=[RunRoot(root, writable=True)],
    )
    client = TestClient(app)

    unauthorized = client.get("/api/local-runs")
    listing = client.get("/api/local-runs", headers=AUTH_HEADERS)
    run_id = listing.json()["runs"][0]["id"]
    download = client.get(
        f"/api/local-runs/{run_id}/artifacts/findings.sarif",
        headers=AUTH_HEADERS,
    )
    blocked = client.get(
        f"/api/local-runs/{run_id}/artifacts/secret.txt",
        headers=AUTH_HEADERS,
    )

    assert unauthorized.status_code == 401
    assert listing.status_code == 200
    assert download.status_code == 200
    assert download.content == b"{}"
    assert blocked.status_code == 404
