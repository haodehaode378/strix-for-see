import { Download, FileJson2, FileText, FolderOpen } from "lucide-react";
import { useState } from "react";

import type { ExportResult, ReportFormat } from "../../features/findings/contracts";
import {
  exportFindings,
  openExportFolder,
} from "../../features/findings/findingsClient";
import { useLocale } from "../../shared/i18n/useLocale";

export function ReportExportPanel({
  findingIds = [],
  runId,
  runName,
}: {
  findingIds?: string[];
  runId: string;
  runName?: string;
}) {
  const { locale, t } = useLocale();
  const [format, setFormat] = useState<ReportFormat>("pdf");
  const [reportLocale, setReportLocale] = useState<"zh-CN" | "en-US">(locale);
  const [omitEvidence, setOmitEvidence] = useState(true);
  const [omitPoc, setOmitPoc] = useState(true);
  const [omitPaths, setOmitPaths] = useState(true);
  const [state, setState] = useState<"idle" | "busy" | "error">("idle");
  const [result, setResult] = useState<ExportResult | null>(null);
  const [openState, setOpenState] = useState<"idle" | "busy" | "error">("idle");

  const handleExport = async () => {
    setState("busy");
    setResult(null);
    setOpenState("idle");
    try {
      const exported = await exportFindings({
        format,
        locale: reportLocale,
        runId,
        findingIds,
        redaction: { omitEvidence, omitPoc, omitPaths },
      });
      setResult(exported);
      setState("idle");
    } catch {
      setState("error");
    }
  };

  const handleOpenFolder = async () => {
    setOpenState("busy");
    try {
      await openExportFolder();
      setOpenState("idle");
    } catch {
      setOpenState("error");
    }
  };

  return (
    <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
      <h2 className="flex items-center gap-2 text-sm font-semibold">
        <FileText className="size-4 text-[var(--accent)]" />
        {t("report.title")}
      </h2>
      <p className="mt-2 text-xs leading-5 text-[var(--text-muted)]">
        {t("report.description")}
      </p>
      {runName ? (
        <p className="mt-2 break-all text-xs font-semibold text-[var(--text)]">
          {t("report.taskScope")} {runName}
        </p>
      ) : null}
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <label className="grid gap-2 text-xs text-[var(--text-muted)]">
          {t("report.format")}
          <select
            value={format}
            onChange={(event) => setFormat(event.target.value as ReportFormat)}
            className="rounded-xl border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-2.5 text-sm text-[var(--text)]"
          >
            <option value="pdf">PDF</option>
            <option value="html">HTML</option>
            <option value="markdown">Markdown</option>
            <option value="json">JSON</option>
          </select>
        </label>
        <label className="grid gap-2 text-xs text-[var(--text-muted)]">
          {t("report.language")}
          <select
            value={reportLocale}
            onChange={(event) =>
              setReportLocale(event.target.value as "zh-CN" | "en-US")
            }
            className="rounded-xl border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-2.5 text-sm text-[var(--text)]"
          >
            <option value="zh-CN">{t("report.language.zh")}</option>
            <option value="en-US">{t("report.language.en")}</option>
          </select>
        </label>
      </div>
      <fieldset className="mt-4 grid gap-2">
        <legend className="mb-2 text-xs font-semibold text-[var(--text)]">
          {t("report.redaction")}
        </legend>
        {[
          [omitEvidence, setOmitEvidence, t("report.omitEvidence")],
          [omitPoc, setOmitPoc, t("report.omitPoc")],
          [omitPaths, setOmitPaths, t("report.omitPaths")],
        ].map(([checked, setter, label]) => (
          <label key={String(label)} className="flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              checked={checked as boolean}
              onChange={(event) =>
                (setter as React.Dispatch<React.SetStateAction<boolean>>)(
                  event.target.checked,
                )
              }
            />
            {label as string}
          </label>
        ))}
      </fieldset>
      <button
        type="button"
        onClick={() => void handleExport()}
        disabled={state === "busy"}
        className="mt-5 inline-flex items-center gap-2 rounded-xl bg-[var(--accent)] px-4 py-2.5 text-sm font-semibold text-white transition active:scale-[0.98] disabled:opacity-50"
      >
        {format === "json" ? <FileJson2 className="size-4" /> : <Download className="size-4" />}
        {state === "busy" ? t("report.exporting") : t("report.export")}
      </button>
      {state === "error" ? (
        <p className="mt-3 text-xs text-[var(--danger)]" aria-live="polite">
          {t("report.failed")}
        </p>
      ) : null}
      {result ? (
        <div
          className="mt-4 rounded-xl border border-[var(--success)]/30 bg-[var(--success)]/10 p-3 text-xs"
          aria-live="polite"
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="font-semibold text-[var(--text)]">{t("report.saved")}</p>
            <button
              type="button"
              onClick={() => void handleOpenFolder()}
              disabled={openState === "busy"}
              className="inline-flex items-center gap-2 rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] px-3 py-2 font-semibold text-[var(--text)] transition active:scale-[0.98] disabled:opacity-50"
            >
              <FolderOpen className="size-4" />
              {openState === "busy" ? t("report.openingFolder") : t("report.openFolder")}
            </button>
          </div>
          <p className="mt-1 break-all font-mono text-[var(--text-muted)]">
            {result.displayPath}
          </p>
          {openState === "error" ? (
            <p className="mt-2 text-[var(--danger)]" aria-live="polite">
              {t("report.openFolderFailed")}
            </p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
