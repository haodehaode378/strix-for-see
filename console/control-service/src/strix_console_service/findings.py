from __future__ import annotations

import hashlib
import html
import io
import json
import os
import re
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFError, TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from strix_console_service.contracts import (
    ExportFindingsRequest,
    Finding,
    FindingExplanationDetails,
    FindingHistoryEntry,
    FindingLocation,
    FindingOccurrence,
    FindingsResponse,
    FindingWorkflowState,
    SeverityCounts,
    UpdateFindingRequest,
)
from strix_console_service.events import redact_event_value
from strix_console_service.local_runs import LocalRunIndexer
from strix_console_service.system_checks import redact_text

_SEVERITIES = {"critical", "high", "medium", "low"}
_TERMINAL_STATES = {"acceptedRisk", "fixed", "falsePositive"}
_MAX_FIELD = 100_000


class FindingStoreError(Exception):
    """Stable error returned by the local finding service."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class FindingStore:
    """Read authoritative findings and maintain a separate local review overlay."""

    def __init__(
        self, indexer: LocalRunIndexer, state_path: Path, export_root: Path | None = None
    ) -> None:
        self.indexer = indexer
        self.state_path = state_path
        self.export_root = export_root or state_path.parent.parent / "exports"
        self._lock = threading.RLock()

    def list_findings(
        self, *, run_id: str | None = None, run_name: str | None = None
    ) -> FindingsResponse:
        with self._lock:
            overlays = self._read_overlays()
            aggregates: dict[str, Finding] = {}
            runs = self.indexer.list_runs().runs
            if run_id is not None:
                runs = [run for run in runs if run.id == run_id]
            for run in runs:
                if run_name is not None and run.name != run_name:
                    continue
                artifact = self.indexer.resolve_artifact(run.id, "vulnerabilities.json")
                if artifact is None:
                    continue
                for item in _read_finding_file(artifact.path):
                    finding_id = _fingerprint(item, run.target)
                    occurrence = FindingOccurrence(
                        run_id=run.id,
                        run_name=run.name,
                        target=_safe_text(run.target),
                        source_finding_id=_string(item, "id"),
                        observed_at=_string(item, "timestamp"),
                    )
                    existing = aggregates.get(finding_id)
                    if existing is None:
                        overlay = overlays.get(_overlay_key(run.id, finding_id))
                        if not isinstance(overlay, dict):
                            overlay = overlays.get(finding_id, {})
                        aggregates[finding_id] = _project_finding(
                            finding_id, item, run.target, occurrence, overlay
                        )
                    else:
                        existing.occurrences.append(occurrence)

            findings = sorted(
                aggregates.values(),
                key=lambda item: (
                    {"critical": 0, "high": 1, "medium": 2, "low": 3}[item.severity],
                    item.title.casefold(),
                ),
            )
            counts = {severity: 0 for severity in _SEVERITIES}
            for finding in findings:
                counts[finding.severity] += 1
            return FindingsResponse(
                generated_at=datetime.now(UTC),
                findings=findings,
                severity_counts=SeverityCounts(**counts),
            )

    def get(self, finding_id: str, *, run_id: str | None = None) -> Finding | None:
        return next(
            (
                finding
                for finding in self.list_findings(run_id=run_id).findings
                if finding.id == finding_id
            ),
            None,
        )

    def update(
        self, finding_id: str, request: UpdateFindingRequest, *, run_id: str | None = None
    ) -> Finding:
        with self._lock:
            finding = self.get(finding_id, run_id=run_id)
            if finding is None:
                raise FindingStoreError("findingNotFound")
            if request.workflow_state is None and request.note is None:
                raise FindingStoreError("findingUpdateEmpty")

            overlays = self._read_overlays()
            overlay_key = _overlay_key(run_id, finding_id) if run_id else finding_id
            overlay = overlays.setdefault(
                overlay_key,
                {"workflowState": finding.workflow_state, "history": []},
            )
            history = overlay.setdefault("history", [])
            if not isinstance(history, list):
                history = []
                overlay["history"] = history

            now = datetime.now(UTC).isoformat()
            if (
                request.workflow_state is not None
                and request.workflow_state != finding.workflow_state
            ):
                if not _valid_transition(finding.workflow_state, request.workflow_state):
                    raise FindingStoreError("invalidFindingTransition")
                history.append(
                    {
                        "id": uuid.uuid4().hex,
                        "occurredAt": now,
                        "kind": "stateChanged",
                        "fromState": finding.workflow_state,
                        "toState": request.workflow_state,
                    }
                )
                overlay["workflowState"] = request.workflow_state
            if request.note is not None:
                history.append(
                    {
                        "id": uuid.uuid4().hex,
                        "occurredAt": now,
                        "kind": "noteAdded",
                        "note": _safe_text(request.note.strip()),
                    }
                )
            self._write_overlays(overlays)
            updated = self.get(finding_id, run_id=run_id)
            if updated is None:
                raise FindingStoreError("findingNotFound")
            return updated

    def export(self, request: ExportFindingsRequest) -> tuple[bytes, str, str]:
        run = self.indexer.get_run(request.run_id)
        if run is None:
            raise FindingStoreError("runNotFound")
        all_findings = self.list_findings(run_id=request.run_id).findings
        selected_ids = set(request.finding_ids)
        findings = (
            [finding for finding in all_findings if finding.id in selected_ids]
            if selected_ids
            else all_findings
        )
        if selected_ids and len(findings) != len(selected_ids):
            raise FindingStoreError("findingNotFound")
        if not findings:
            raise FindingStoreError("noFindingsToExport")

        report = _redact_for_export(findings, request)
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        extension = request.format if request.format != "markdown" else "md"
        run_label = run.name
        scope = f"-{_filename_part(run_label)}" if run_label else ""
        filename = f"strix-findings{scope}-{stamp}.{extension}"
        if request.format == "json":
            payload = json.dumps(
                [
                    item.model_dump(mode="json", by_alias=True, exclude_none=True)
                    for item in report
                ],
                ensure_ascii=False,
                indent=2,
            ).encode()
            return payload, "application/json; charset=utf-8", filename
        if request.format == "markdown":
            return (
                _render_markdown(report, request.locale).encode(),
                "text/markdown; charset=utf-8",
                filename,
            )
        if request.format == "html":
            return (
                _render_html(report, request.locale).encode(),
                "text/html; charset=utf-8",
                filename,
            )
        return _render_pdf(report, request.locale), "application/pdf", filename

    def export_to_file(self, request: ExportFindingsRequest) -> tuple[str, str]:
        payload, _media_type, filename = self.export(request)
        with self._lock:
            self.export_root.mkdir(parents=True, exist_ok=True)
            destination = self.export_root / filename
            counter = 2
            while destination.exists():
                candidate = f"{Path(filename).stem}-{counter}{Path(filename).suffix}"
                destination = self.export_root / candidate
                counter += 1
            temporary = destination.with_suffix(f"{destination.suffix}.tmp")
            temporary.write_bytes(payload)
            temporary.replace(destination)
        return destination.name, redact_text(str(destination), home=Path.home())

    def open_export_folder(self) -> None:
        self.export_root.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            raise OSError("exportFolderUnsupported")
        os.startfile(self.export_root)  # noqa: S606 - fixed local export directory

    def _read_overlays(self) -> dict[str, dict[str, Any]]:
        if not self.state_path.is_file():
            return {}
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def _write_overlays(self, overlays: dict[str, dict[str, Any]]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(overlays, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.state_path)


def _read_finding_file(path: Path) -> list[dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _fingerprint(item: dict[str, Any], run_target: str | None) -> str:
    locations = item.get("code_locations")
    first_location = locations[0] if isinstance(locations, list) and locations else {}
    if not isinstance(first_location, dict):
        first_location = {}
    parts = [
        run_target or _string(item, "target") or "",
        _string(item, "title") or "",
        _string(item, "cwe") or "",
        _string(item, "endpoint") or "",
        _string(item, "method") or "",
        str(first_location.get("file") or ""),
        str(first_location.get("start_line") or ""),
    ]
    normalized = "\0".join(re.sub(r"\s+", " ", part.strip().casefold()) for part in parts)
    return hashlib.sha256(f"finding-v1\0{normalized}".encode()).hexdigest()[:32]


def _project_finding(
    finding_id: str,
    item: dict[str, Any],
    run_target: str | None,
    occurrence: FindingOccurrence,
    overlay: dict[str, Any],
) -> Finding:
    raw_severity = (_string(item, "severity") or "low").lower()
    severity = raw_severity if raw_severity in _SEVERITIES else "low"
    raw_state = overlay.get("workflowState")
    state: FindingWorkflowState = (
        raw_state
        if raw_state in {"pending", "confirmed", "acceptedRisk", "fixed", "falsePositive"}
        else "pending"
    )
    history: list[FindingHistoryEntry] = []
    for raw in overlay.get("history", []):
        try:
            history.append(FindingHistoryEntry.model_validate(raw))
        except (ValueError, TypeError):
            continue
    locations: list[FindingLocation] = []
    raw_locations = item.get("code_locations")
    if isinstance(raw_locations, list):
        for raw in raw_locations[:100]:
            if not isinstance(raw, dict):
                continue
            locations.append(
                FindingLocation(
                    file=_safe_text(raw.get("file")),
                    start_line=_positive_int(raw.get("start_line")),
                    end_line=_positive_int(raw.get("end_line")),
                    label=_safe_text(raw.get("label")),
                    snippet=_safe_text(raw.get("snippet")),
                )
            )
    affected_inputs = _string_list(item.get("affected_inputs"))
    endpoint = _safe_text(item.get("endpoint"))
    method = _safe_text(item.get("method"))
    interface_or_feature: str | None = " ".join(
        value for value in [method, endpoint] if value
    )
    if not interface_or_feature:
        location = next((value for value in locations if value.label or value.file), None)
        interface_or_feature = (
            (location.label or location.file) if location is not None else None
        ) or _safe_text(item.get("target") or run_target)
    return Finding(
        id=finding_id,
        title=_safe_text(item.get("title")) or "Untitled finding",
        severity=severity,  # type: ignore[arg-type]
        workflow_state=state,
        target=_safe_text(item.get("target") or run_target),
        description=_safe_text(item.get("description")),
        impact=_safe_text(item.get("impact")),
        technical_analysis=_safe_text(item.get("technical_analysis")),
        evidence=_safe_text(item.get("evidence")),
        poc_description=_safe_text(item.get("poc_description")),
        poc_script_code=_safe_text(item.get("poc_script_code")),
        remediation_steps=_safe_text(item.get("remediation_steps")),
        endpoint=endpoint,
        method=method,
        affected_inputs=affected_inputs,
        cve=_safe_text(item.get("cve")),
        cwe=_safe_text(item.get("cwe")),
        cvss=_number(item.get("cvss")),
        locations=locations,
        occurrences=[occurrence],
        history=history,
        explanation=FindingExplanationDetails(
            interface_or_feature=interface_or_feature,
            affected_inputs=affected_inputs,
            prerequisites=_safe_text(item.get("assumptions")),
            trigger_behavior=_safe_text(item.get("poc_description")),
            real_impact=_safe_text(item.get("impact")),
        ),
    )


def _safe_text(value: Any) -> str | None:
    if value is None:
        return None
    safe = redact_event_value(str(value))
    if isinstance(safe, str):
        safe = re.sub(
            r"(?i)\b[A-Z]:\\Users\\[^\\\r\n]+",
            r"%USERPROFILE%",
            safe,
        )
    return safe[:_MAX_FIELD] if isinstance(safe, str) and safe else None


def _filename_part(value: str | None) -> str:
    if not value:
        return ""
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return normalized[:80] or "task"


def _overlay_key(run_id: str, finding_id: str) -> str:
    return f"run:{run_id}:finding:{finding_id}"


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value[:100]:
        text = _safe_text(item)
        if text and text not in result:
            result.append(text)
    return result


def _string(item: dict[str, Any], key: str) -> str | None:
    value = item.get(key)
    return value if isinstance(value, str) and value else None


def _positive_int(value: Any) -> int | None:
    return value if isinstance(value, int) and value > 0 else None


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) else None


def _valid_transition(current: FindingWorkflowState, target: FindingWorkflowState) -> bool:
    return (current == "pending" and target == "confirmed") or (
        current == "confirmed" and target in _TERMINAL_STATES
    )


def _redact_for_export(
    findings: list[Finding], request: ExportFindingsRequest
) -> list[Finding]:
    copies = [finding.model_copy(deep=True) for finding in findings]
    for finding in copies:
        if request.redaction.omit_evidence:
            finding.evidence = None
        if request.redaction.omit_poc:
            finding.poc_description = None
            finding.poc_script_code = None
            finding.explanation.trigger_behavior = None
        if request.redaction.omit_paths:
            finding.locations = []
    return copies


_LABELS = {
    "zh-CN": {
        "title": "Strix 漏洞报告",
        "summary": "发现数量",
        "severity": "严重程度",
        "state": "处理状态",
        "target": "目标",
        "description": "描述",
        "evidence": "证据",
        "impact": "影响",
        "analysis": "技术分析",
        "poc": "验证过程",
        "remediation": "修复建议",
        "locations": "受影响位置",
        "occurrences": "出现记录",
        "partial": "未提供",
        "explanationInterface": "哪个接口或功能?",
        "explanationInput": "哪个参数或输入?",
        "explanationPrerequisites": "需要什么权限和前置条件?",
        "explanationTrigger": "预期触发什么行为?",
        "explanationImpact": "会产生什么真实影响?",
    },
    "en-US": {
        "title": "Strix Findings Report",
        "summary": "Findings",
        "severity": "Severity",
        "state": "Workflow state",
        "target": "Target",
        "description": "Description",
        "evidence": "Evidence",
        "impact": "Impact",
        "analysis": "Technical analysis",
        "poc": "Proof of concept",
        "remediation": "Remediation",
        "locations": "Affected locations",
        "occurrences": "Occurrences",
        "partial": "Not provided",
        "explanationInterface": "Affected interface or feature",
        "explanationInput": "Affected parameter or input",
        "explanationPrerequisites": "Permissions and prerequisites",
        "explanationTrigger": "Expected trigger behavior",
        "explanationImpact": "Real-world impact",
    },
}
_SEVERITY_LABELS = {
    "zh-CN": {"critical": "严重", "high": "高危", "medium": "中危", "low": "低危"},
    "en-US": {"critical": "Critical", "high": "High", "medium": "Medium", "low": "Low"},
}
_STATE_LABELS = {
    "zh-CN": {
        "pending": "待处理",
        "confirmed": "已确认",
        "acceptedRisk": "已接受风险",
        "fixed": "已修复",
        "falsePositive": "误报",
    },
    "en-US": {
        "pending": "Pending",
        "confirmed": "Confirmed",
        "acceptedRisk": "Accepted risk",
        "fixed": "Fixed",
        "falsePositive": "False positive",
    },
}


def _render_markdown(findings: list[Finding], locale: str) -> str:
    labels = _LABELS[locale]
    lines = [f"# {labels['title']}", "", f"{labels['summary']}: {len(findings)}", ""]
    for finding in findings:
        lines.extend(
            [
                f"## {_md(finding.title)}",
                "",
                f"- {labels['severity']}: {_SEVERITY_LABELS[locale][finding.severity]}",
                f"- {labels['state']}: {_STATE_LABELS[locale][finding.workflow_state]}",
                f"- {labels['target']}: {_md(finding.target or labels['partial'])}",
            ]
        )
        for label, value in _sections(finding, labels):
            if value:
                lines.extend(["", f"### {label}", "", _md(value)])
        if finding.locations:
            lines.extend(["", f"### {labels['locations']}", ""])
            lines.extend(
                f"- {_md(location.file or labels['partial'])}"
                for location in finding.locations
            )
        lines.extend(["", f"{labels['occurrences']}: {len(finding.occurrences)}", ""])
    return "\n".join(lines)


def _md(value: str) -> str:
    return value.replace("<", "&lt;").replace(">", "&gt;")


def _render_html(findings: list[Finding], locale: str) -> str:
    labels = _LABELS[locale]
    cards: list[str] = []
    for finding in findings:
        sections = "".join(
            f"<section><h3>{html.escape(label)}</h3><pre>{html.escape(value)}</pre></section>"
            for label, value in _sections(finding, labels)
            if value
        )
        locations = "".join(
            f"<li><code>{html.escape(location.file or labels['partial'])}</code></li>"
            for location in finding.locations
        )
        location_section = (
            f"<section><h3>{html.escape(labels['locations'])}</h3>"
            f"<ul>{locations}</ul></section>"
            if locations
            else ""
        )
        cards.append(
            f"<article><header><span class='severity {finding.severity}'>"
            f"{html.escape(_SEVERITY_LABELS[locale][finding.severity])}</span>"
            f"<h2>{html.escape(finding.title)}</h2></header>"
            f"<dl><dt>{html.escape(labels['state'])}</dt>"
            f"<dd>{html.escape(_STATE_LABELS[locale][finding.workflow_state])}</dd>"
            f"<dt>{html.escape(labels['target'])}</dt>"
            f"<dd>{html.escape(finding.target or labels['partial'])}</dd></dl>"
            f"{sections}{location_section}"
            f"<footer>{html.escape(labels['occurrences'])}: "
            f"{len(finding.occurrences)}</footer></article>"
        )
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta http-equiv='Content-Security-Policy' "
        "content=\"default-src 'none'; style-src 'unsafe-inline'\">"
        f"<title>{html.escape(labels['title'])}</title><style>"
        "body{font:14px system-ui;color:#17211f;background:#f3f5f4;"
        "max-width:960px;margin:0 auto;padding:40px}"
        "h1{font-size:28px}article{background:white;border:1px solid #d7dfdc;"
        "border-radius:16px;padding:24px;margin:20px 0}"
        "header{display:flex;gap:12px;align-items:center}h2{font-size:20px}"
        "h3{font-size:14px;margin-top:22px}"
        "dl{display:grid;grid-template-columns:130px 1fr;gap:8px}"
        "dt{color:#667570}dd{margin:0}"
        "pre{white-space:pre-wrap;word-break:break-word;font:13px ui-monospace;"
        "background:#edf1ef;padding:14px;border-radius:10px}"
        ".severity{font-weight:700}.critical{color:#b42318}.high{color:#b54708}"
        ".medium{color:#986801}.low{color:#17785f}"
        "footer{color:#667570;margin-top:20px}</style></head><body>"
        f"<h1>{html.escape(labels['title'])}</h1>"
        f"<p>{html.escape(labels['summary'])}: {len(findings)}</p>"
        + "".join(cards)
        + "</body></html>"
    )


def _render_pdf(findings: list[Finding], locale: str) -> bytes:
    labels = _LABELS[locale]
    font = "Helvetica"
    if locale == "zh-CN":
        font = _register_cjk_font()
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=labels["title"],
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ConsoleTitle",
        parent=styles["Title"],
        fontName=font,
        textColor=colors.HexColor("#153d35"),
        alignment=TA_CENTER,
        spaceAfter=12,
    )
    heading = ParagraphStyle(
        "FindingHeading",
        parent=styles["Heading2"],
        fontName=font,
        textColor=colors.HexColor("#153d35"),
        spaceAfter=8,
    )
    body = ParagraphStyle(
        "ConsoleBody",
        parent=styles["BodyText"],
        fontName=font,
        fontSize=9,
        leading=13,
        spaceAfter=8,
    )
    story: list[Any] = [
        Paragraph(html.escape(labels["title"]), title_style),
        Paragraph(f"{html.escape(labels['summary'])}: {len(findings)}", body),
        Spacer(1, 5 * mm),
    ]
    for index, finding in enumerate(findings):
        if index:
            story.append(PageBreak())
        story.append(Paragraph(html.escape(finding.title), heading))
        story.append(
            Paragraph(
                f"<b>{html.escape(labels['severity'])}:</b> "
                f"{html.escape(_SEVERITY_LABELS[locale][finding.severity])} &nbsp; "
                f"<b>{html.escape(labels['state'])}:</b> "
                f"{html.escape(_STATE_LABELS[locale][finding.workflow_state])}",
                body,
            )
        )
        story.append(
            Paragraph(
                f"<b>{html.escape(labels['target'])}:</b> "
                f"{html.escape(finding.target or labels['partial'])}",
                body,
            )
        )
        for label, value in _sections(finding, labels):
            if value:
                story.append(Paragraph(html.escape(label), heading))
                story.append(Paragraph(_pdf_text(value), body))
        if finding.locations:
            story.append(Paragraph(html.escape(labels["locations"]), heading))
            for location in finding.locations:
                story.append(Paragraph(_pdf_text(location.file or labels["partial"]), body))
        story.append(
            Paragraph(f"{html.escape(labels['occurrences'])}: {len(finding.occurrences)}", body)
        )

    def footer(canvas: Canvas, document: BaseDocTemplate) -> None:
        canvas.saveState()
        canvas.setFont(font, 8)
        page_label = "页" if locale == "zh-CN" else "Page"
        canvas.setFillColor(colors.HexColor("#667570"))
        canvas.drawRightString(
            A4[0] - 20 * mm,
            10 * mm,
            f"Strix Console · {page_label} {document.page}",
        )
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()


def _register_cjk_font() -> str:
    embedded_name = "StrixConsoleCJK"
    if embedded_name in pdfmetrics.getRegisteredFontNames():
        return embedded_name
    windows_root = Path(os.environ.get("WINDIR", r"C:\Windows"))
    font_path = windows_root / "Fonts" / "msyh.ttc"
    if font_path.is_file():
        try:
            pdfmetrics.registerFont(TTFont(embedded_name, font_path, subfontIndex=0))
            return embedded_name
        except (OSError, TTFError, ValueError):
            pass
    fallback = "STSong-Light"
    try:
        pdfmetrics.registerFont(UnicodeCIDFont(fallback))
    except KeyError:
        pass
    return fallback


def _sections(finding: Finding, labels: dict[str, str]) -> list[tuple[str, str | None]]:
    poc = "\n\n".join(
        value for value in [finding.poc_description, finding.poc_script_code] if value
    )
    explanation = finding.explanation
    affected_inputs = ", ".join(explanation.affected_inputs)
    return [
        (labels["explanationInterface"], explanation.interface_or_feature or labels["partial"]),
        (labels["explanationInput"], affected_inputs or labels["partial"]),
        (labels["explanationPrerequisites"], explanation.prerequisites or labels["partial"]),
        (labels["explanationTrigger"], explanation.trigger_behavior or labels["partial"]),
        (labels["explanationImpact"], explanation.real_impact or labels["partial"]),
        (labels["description"], finding.description),
        (labels["evidence"], finding.evidence),
        (labels["impact"], finding.impact),
        (labels["analysis"], finding.technical_analysis),
        (labels["poc"], poc or None),
        (labels["remediation"], finding.remediation_steps),
    ]


def _pdf_text(value: str) -> str:
    return "<br/>".join(html.escape(line) for line in value.splitlines())
