from __future__ import annotations

import json
import os
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
    display_name: str | None = None,
    target: str = "https://example.com",
    finding_id: str = "vuln-0001",
) -> None:
    run = root / name
    run.mkdir(parents=True)
    (run / "run.json").write_text(
        json.dumps(
            {
                "run_name": display_name or name,
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
                    "affected_inputs": ["profile.bio"],
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
    run_id = store.indexer.list_runs().runs[0].id

    payload, actual_media_type, _filename = store.export(
        ExportFindingsRequest.model_validate(
            {
                "format": report_format,
                "locale": "en-US",
                "runId": run_id,
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


def test_export_is_scoped_to_one_task(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    _write_finding_run(root, "selected-task")
    _write_finding_run(root, "other-task")
    store = FindingStore(
        LocalRunIndexer([RunRoot(root, writable=True)]),
        tmp_path / "state" / "findings.json",
    )
    run_id = next(run.id for run in store.indexer.list_runs().runs if run.name == "selected-task")

    payload, _media_type, filename = store.export(
        ExportFindingsRequest.model_validate(
            {"format": "json", "locale": "zh-CN", "runId": run_id}
        )
    )
    exported = json.loads(payload)

    assert "selected-task" in filename
    assert [item["runName"] for item in exported[0]["occurrences"]] == ["selected-task"]


def test_duplicate_task_names_are_isolated_by_run_id(tmp_path: Path) -> None:
    first_root = tmp_path / "first-root"
    second_root = tmp_path / "second-root"
    _write_finding_run(first_root, "run-a", display_name="duplicate")
    _write_finding_run(second_root, "run-b", display_name="duplicate")
    store = FindingStore(
        LocalRunIndexer(
            [RunRoot(first_root, writable=True), RunRoot(second_root, writable=True)]
        ),
        tmp_path / "state" / "findings.json",
    )
    first_run, second_run = store.indexer.list_runs().runs
    first_finding = store.list_findings(run_id=first_run.id).findings[0]
    second_finding = store.list_findings(run_id=second_run.id).findings[0]

    store.update(
        first_finding.id,
        UpdateFindingRequest(workflow_state="confirmed", note="first run only"),
        run_id=first_run.id,
    )

    updated_first = store.get(first_finding.id, run_id=first_run.id)
    untouched_second = store.get(second_finding.id, run_id=second_run.id)
    assert updated_first is not None and updated_first.workflow_state == "confirmed"
    assert [entry.note for entry in updated_first.history if entry.note] == ["first run only"]
    assert untouched_second is not None and untouched_second.workflow_state == "pending"
    assert untouched_second.history == []

    for report_format in ("html", "pdf", "markdown", "json"):
        payload, _media_type, _filename = store.export(
            ExportFindingsRequest.model_validate(
                {"format": report_format, "runId": first_run.id}
            )
        )
        assert payload
        if report_format == "json":
            exported = json.loads(payload)
            assert [item["runId"] for item in exported[0]["occurrences"]] == [
                first_run.id
            ]


def test_export_to_file_returns_redacted_display_path(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    export_root = tmp_path / "exports"
    _write_finding_run(root, "saved-report")
    store = FindingStore(
        LocalRunIndexer([RunRoot(root, writable=True)]),
        tmp_path / "state" / "findings.json",
        export_root,
    )
    run_id = store.indexer.list_runs().runs[0].id

    filename, display_path = store.export_to_file(
        ExportFindingsRequest(format="markdown", run_id=run_id)
    )

    assert (export_root / filename).read_bytes().startswith(b"# ")
    assert str(Path.home()) not in display_path


def test_export_folder_opens_only_the_fixed_export_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    export_root = tmp_path / "exports"
    opened: list[Path] = []
    monkeypatch.setattr(os, "startfile", lambda path: opened.append(Path(path)))
    store = FindingStore(
        LocalRunIndexer([RunRoot(tmp_path / "runs", writable=True)]),
        tmp_path / "state" / "findings.json",
        export_root,
    )

    store.open_export_folder()

    assert opened == [export_root]


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
    run_id = client.get("/api/local-runs", headers=AUTH_HEADERS).json()["runs"][0]["id"]
    finding_id = listing.json()["findings"][0]["id"]
    updated = client.patch(
        f"/api/runs/{run_id}/findings/{finding_id}",
        headers=AUTH_HEADERS,
        json={"workflowState": "confirmed", "note": "Confirmed locally"},
    )
    export = client.post(
        "/api/findings/export",
        headers=AUTH_HEADERS,
        json={"format": "json", "locale": "en-US", "runId": run_id},
    )
    saved = client.post(
        "/api/findings/export-file",
        headers=AUTH_HEADERS,
        json={"format": "html", "locale": "zh-CN", "runId": run_id},
    )

    assert listing.status_code == 200
    assert updated.status_code == 200
    assert updated.json()["workflowState"] == "confirmed"
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("application/json")
    assert export.headers["content-disposition"].startswith("attachment;")
    assert saved.status_code == 200
    assert saved.json()["runName"] == "api"
    assert saved.json()["filename"].endswith(".html")
    assert "exports" in saved.json()["displayPath"]
