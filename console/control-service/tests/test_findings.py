from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from strix_console_service.app import create_app
from strix_console_service.contracts import ExportFindingsRequest, UpdateFindingRequest
from strix_console_service.findings import FindingStore, FindingStoreError
from strix_console_service.local_runs import LocalRunIndexer, RunRoot

ACCESS_TOKEN = "test-access-token"
BOOTSTRAP_TOKEN = "test-bootstrap-token"
AUTH_HEADERS = {"X-Strix-Access-Token": ACCESS_TOKEN}


def _write_finding_run(
    root: Path,
    name: str,
    *,
    target: str = "https://example.com",
    finding_id: str = "vuln-0001",
) -> None:
    run = root / name
    run.mkdir(parents=True)
    (run / "run.json").write_text(
        json.dumps(
            {
                "run_name": name,
                "status": "completed",
                "end_time": "2026-07-28T02:00:00Z",
                "targets_info": [{"original": target}],
            }
        ),
        encoding="utf-8",
    )
    (run / "vulnerabilities.json").write_text(
        json.dumps(
            [
                {
                    "id": finding_id,
                    "title": "Stored XSS <script>alert(1)</script>",
                    "severity": "high",
                    "target": target,
                    "endpoint": "/profile",
                    "method": "POST",
                    "cwe": "CWE-79",
                    "description": "A stored payload executes in another browser.",
                    "evidence": "Authorization: Bearer secret-value",
                    "poc_description": "Submit the payload.",
                    "poc_script_code": "<img src=x onerror=alert(1)>",
                    "remediation_steps": "Encode untrusted output.",
                    "code_locations": [
                        {
                            "file": "C:\\Users\\operator\\project\\profile.tsx",
                            "start_line": 42,
                            "snippet": "<div dangerouslySetInnerHTML={value} />",
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )


def test_findings_are_deduplicated_across_runs_and_redacted(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    _write_finding_run(root, "first", finding_id="vuln-0001")
    _write_finding_run(root, "second", finding_id="vuln-0042")
    store = FindingStore(
        LocalRunIndexer([RunRoot(root, writable=True)]),
        tmp_path / "state" / "findings.json",
    )

    response = store.list_findings()

    assert len(response.findings) == 1
    finding = response.findings[0]
    assert len(finding.occurrences) == 2
    assert response.severity_counts.high == 1
    assert "secret-value" not in (finding.evidence or "")
    assert "operator" not in (finding.locations[0].file or "")
    assert "%USERPROFILE%" in (finding.locations[0].file or "")


def test_workflow_and_notes_persist_without_changing_run_files(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    _write_finding_run(root, "review")
    vulnerability_path = root / "review" / "vulnerabilities.json"
    original = vulnerability_path.read_bytes()
    state_path = tmp_path / "state" / "findings.json"
    store = FindingStore(LocalRunIndexer([RunRoot(root, writable=True)]), state_path)
    finding_id = store.list_findings().findings[0].id

    store.update(
        finding_id,
        UpdateFindingRequest(workflow_state="confirmed", note="已人工复现"),
    )
    reloaded = FindingStore(LocalRunIndexer([RunRoot(root, writable=True)]), state_path)
    finding = reloaded.get(finding_id)

    assert finding is not None
    assert finding.workflow_state == "confirmed"
    assert [entry.kind for entry in finding.history] == ["stateChanged", "noteAdded"]
    assert vulnerability_path.read_bytes() == original


def test_invalid_workflow_transition_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    _write_finding_run(root, "review")
    store = FindingStore(
        LocalRunIndexer([RunRoot(root, writable=True)]),
        tmp_path / "state" / "findings.json",
    )
    finding_id = store.list_findings().findings[0].id

    with pytest.raises(FindingStoreError, match="invalidFindingTransition"):
        store.update(finding_id, UpdateFindingRequest(workflow_state="fixed"))


def test_missing_optional_fields_remain_visible_as_partial_data(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    run = root / "partial"
    run.mkdir(parents=True)
    (run / "run.json").write_text(
        json.dumps({"run_name": "partial", "status": "running"}),
        encoding="utf-8",
    )
    (run / "vulnerabilities.json").write_text(
        json.dumps([{"title": "Minimal finding", "severity": "medium"}]),
        encoding="utf-8",
    )
    store = FindingStore(
        LocalRunIndexer([RunRoot(root, writable=True)]),
        tmp_path / "state" / "findings.json",
    )

    finding = store.list_findings().findings[0]

    assert finding.title == "Minimal finding"
    assert finding.description is None
    assert finding.locations == []
    assert finding.occurrences[0].run_name == "partial"


@pytest.mark.parametrize(
    ("report_format", "media_type", "prefix"),
    [
        ("html", "text/html; charset=utf-8", b"<!doctype html>"),
        ("markdown", "text/markdown; charset=utf-8", b"# "),
        ("json", "application/json; charset=utf-8", b"["),
        ("pdf", "application/pdf", b"%PDF"),
    ],
)
def test_exports_have_correct_types_and_apply_redaction(
    tmp_path: Path,
    report_format: str,
    media_type: str,
    prefix: bytes,
) -> None:
    root = tmp_path / "runs"
    _write_finding_run(root, "report")
    store = FindingStore(
        LocalRunIndexer([RunRoot(root, writable=True)]),
        tmp_path / "state" / "findings.json",
    )

    payload, actual_media_type, _filename = store.export(
        ExportFindingsRequest.model_validate(
            {
                "format": report_format,
                "locale": "en-US",
                "redaction": {
                    "omitEvidence": True,
                    "omitPoc": True,
                    "omitPaths": True,
                },
            }
        )
    )

    assert actual_media_type == media_type
    assert payload.startswith(prefix)
    assert b"secret-value" not in payload
    assert b"onerror" not in payload
    assert b"project\\\\profile" not in payload
    if report_format == "html":
        assert b"<script>alert(1)</script>" not in payload
        assert b"Content-Security-Policy" in payload
    if report_format == "json":
        exported = json.loads(payload)
        assert "evidence" not in exported[0]
        assert "pocScriptCode" not in exported[0]
        assert exported[0]["locations"] == []


def test_findings_api_supports_read_update_and_download(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    _write_finding_run(root, "api")
    client = TestClient(
        create_app(
            access_token=ACCESS_TOKEN,
            bootstrap_token=BOOTSTRAP_TOKEN,
            run_roots=[RunRoot(root, writable=True)],
        )
    )

    listing = client.get("/api/findings", headers=AUTH_HEADERS)
    finding_id = listing.json()["findings"][0]["id"]
    updated = client.patch(
        f"/api/findings/{finding_id}",
        headers=AUTH_HEADERS,
        json={"workflowState": "confirmed", "note": "Confirmed locally"},
    )
    export = client.post(
        "/api/findings/export",
        headers=AUTH_HEADERS,
        json={"format": "json", "locale": "en-US"},
    )

    assert listing.status_code == 200
    assert updated.status_code == 200
    assert updated.json()["workflowState"] == "confirmed"
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("application/json")
    assert export.headers["content-disposition"].startswith("attachment;")
