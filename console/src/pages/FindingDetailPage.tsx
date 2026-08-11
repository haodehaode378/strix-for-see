import { ArrowLeft, CheckCircle2, FileWarning, History, MapPin } from "lucide-react";
import { useState } from "react";

import { ReportExportPanel } from "../components/findings/ReportExportPanel";
import { SeverityBadge } from "../components/ui/SeverityBadge";
import type { FindingWorkflowState } from "../features/findings/contracts";
import { updateFinding } from "../features/findings/findingsClient";
import { findingExplanation } from "../features/findings/findingExplanation";
import { useFinding } from "../features/findings/useFindings";
import { formatRunDate } from "../features/local-runs/formatRunDate";
import type { MessageKey } from "../shared/i18n/messages";
import { useLocale } from "../shared/i18n/useLocale";
import { NavigationLink } from "../shared/navigation/NavigationLink";

export function FindingDetailPage({ id }: { id: string }) {
  const { locale, t } = useLocale();
  const { finding, setFinding, state } = useFinding(id);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  if (state === "loading" && !finding) {
    return (
      <div className="h-72 animate-pulse rounded-2xl border border-[var(--border)] bg-[var(--surface)]" />
    );
  }
  if (!finding) {
    return (
      <div className="grid min-h-72 place-items-center text-center">
        <FileWarning className="mx-auto size-8 text-[var(--warning)]" />
        <p className="mt-3 text-sm text-[var(--text-muted)]">{t("finding.notFound")}</p>
      </div>
    );
  }

  const nextStates: FindingWorkflowState[] =
    finding.workflowState === "pending"
      ? ["confirmed"]
      : finding.workflowState === "confirmed"
        ? ["acceptedRisk", "fixed", "falsePositive"]
        : [];
  const save = async (workflowState?: FindingWorkflowState) => {
    setBusy(true);
    setError(false);
    try {
      const updated = await updateFinding(finding.id, {
        workflowState,
        note: note.trim() || undefined,
      });
      setFinding(updated);
      setNote("");
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <NavigationLink
        to="/findings"
        className="mb-5 inline-flex items-center gap-2 text-sm font-semibold text-[var(--text-muted)] hover:text-[var(--text)]"
      >
        <ArrowLeft className="size-4" />
        {t("finding.back")}
      </NavigationLink>
      <header className="border-b border-[var(--border)] pb-6">
        <div className="flex flex-wrap items-center gap-2">
          <SeverityBadge severity={finding.severity} />
          <span className="rounded-md bg-[var(--surface-muted)] px-2 py-1 text-[11px]">
            {t(`findings.state.${finding.workflowState}` as MessageKey)}
          </span>
          {finding.cvss !== null ? (
            <span className="text-xs text-[var(--text-muted)]">CVSS {finding.cvss}</span>
          ) : null}
        </div>
        <h1 className="mt-4 max-w-4xl text-2xl font-semibold tracking-tight sm:text-3xl">
          {finding.title}
        </h1>
        <p className="mt-3 break-all font-mono text-xs text-[var(--text-muted)]">
          {[finding.method, finding.endpoint, finding.target].filter(Boolean).join(" · ") || "—"}
        </p>
      </header>

      <div className="mt-7 grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <main className="min-w-0 space-y-5">
          <FindingSection
            title={t("finding.plainExplanation")}
            value={t(`finding.explanation.${findingExplanation(finding)}` as MessageKey)}
          />
          <FindingSection title={t("finding.description")} value={finding.description} />
          <FindingSection title={t("finding.evidence")} value={finding.evidence} code />
          <FindingSection title={t("finding.impact")} value={finding.impact} />
          <FindingSection
            title={t("finding.analysis")}
            value={finding.technicalAnalysis}
          />
          <FindingSection title={t("finding.poc")} value={finding.pocDescription} />
          <FindingSection
            title={t("finding.pocCode")}
            value={finding.pocScriptCode}
            code
          />
          <FindingSection
            title={t("finding.remediation")}
            value={finding.remediationSteps}
          />
          <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
            <h2 className="flex items-center gap-2 text-sm font-semibold">
              <MapPin className="size-4 text-[var(--accent)]" />
              {t("finding.locations")}
            </h2>
            {finding.locations.length ? (
              <div className="mt-4 divide-y divide-[var(--border)]">
                {finding.locations.map((location, index) => (
                  <div key={`${location.file}-${index}`} className="py-3">
                    <p className="break-all font-mono text-xs">
                      {location.file ?? t("finding.partial")}
                      {location.startLine ? `:${location.startLine}` : ""}
                    </p>
                    {location.label ? (
                      <p className="mt-2 text-xs text-[var(--text-muted)]">{location.label}</p>
                    ) : null}
                    {location.snippet ? (
                      <pre className="mt-3 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-[var(--surface-muted)] p-4 text-xs">
                        {location.snippet}
                      </pre>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-xs text-[var(--text-muted)]">{t("finding.partial")}</p>
            )}
          </section>
        </main>

        <aside className="space-y-5">
          <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
            <h2 className="flex items-center gap-2 text-sm font-semibold">
              <CheckCircle2 className="size-4 text-[var(--accent)]" />
              {t("finding.review")}
            </h2>
            {nextStates.length ? (
              <div className="mt-4 flex flex-wrap gap-2">
                {nextStates.map((nextState) => (
                  <button
                    key={nextState}
                    type="button"
                    disabled={busy}
                    onClick={() => void save(nextState)}
                    className="rounded-xl border border-[var(--border)] px-3 py-2 text-xs font-semibold transition active:scale-[0.98] disabled:opacity-50"
                  >
                    {t(`findings.state.${nextState}` as MessageKey)}
                  </button>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-xs text-[var(--text-muted)]">
                {t("finding.terminalState")}
              </p>
            )}
            <label className="mt-5 grid gap-2 text-xs text-[var(--text-muted)]">
              {t("finding.note")}
              <textarea
                value={note}
                maxLength={4000}
                onChange={(event) => setNote(event.target.value)}
                placeholder={t("finding.notePlaceholder")}
                className="min-h-28 resize-y rounded-xl border border-[var(--border)] bg-[var(--surface-muted)] p-3 text-sm text-[var(--text)]"
              />
            </label>
            <button
              type="button"
              disabled={busy || !note.trim()}
              onClick={() => void save()}
              className="mt-3 rounded-xl bg-[var(--accent)] px-4 py-2.5 text-sm font-semibold text-white transition active:scale-[0.98] disabled:opacity-50"
            >
              {t("finding.addNote")}
            </button>
            {error ? (
              <p className="mt-3 text-xs text-[var(--danger)]" aria-live="polite">
                {t("finding.updateFailed")}
              </p>
            ) : null}
          </section>

          <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
            <h2 className="flex items-center gap-2 text-sm font-semibold">
              <History className="size-4 text-[var(--accent)]" />
              {t("finding.history")}
            </h2>
            {finding.history.length ? (
              <ol className="mt-4 space-y-4 border-l border-[var(--border)] pl-4">
                {[...finding.history].reverse().map((entry) => (
                  <li key={entry.id}>
                    <p className="text-xs">
                      {entry.kind === "noteAdded"
                        ? entry.note
                        : `${t(`findings.state.${entry.fromState}` as MessageKey)} → ${t(`findings.state.${entry.toState}` as MessageKey)}`}
                    </p>
                    <time className="mt-1 block text-[10px] text-[var(--text-muted)]">
                      {formatRunDate(entry.occurredAt, locale)}
                    </time>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="mt-3 text-xs text-[var(--text-muted)]">
                {t("finding.noHistory")}
              </p>
            )}
          </section>

          <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
            <h2 className="text-sm font-semibold">{t("finding.occurrences")}</h2>
            <div className="mt-3 space-y-3">
              {finding.occurrences.map((occurrence) => (
                <NavigationLink
                  key={`${occurrence.runId}-${occurrence.sourceFindingId}`}
                  to={`/local-runs/${occurrence.runId}`}
                  className="block rounded-xl bg-[var(--surface-muted)] p-3"
                >
                  <p className="truncate text-xs font-semibold">{occurrence.runName}</p>
                  <p className="mt-1 text-[10px] text-[var(--text-muted)]">
                    {formatRunDate(occurrence.observedAt, locale)}
                  </p>
                </NavigationLink>
              ))}
            </div>
          </section>
          <ReportExportPanel findingIds={[finding.id]} />
        </aside>
      </div>
    </div>
  );
}

function FindingSection({
  title,
  value,
  code = false,
}: {
  title: string;
  value: string | null;
  code?: boolean;
}) {
  const { t } = useLocale();
  return (
    <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
      <h2 className="text-sm font-semibold">{title}</h2>
      {value ? (
        code ? (
          <pre className="mt-4 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-[var(--surface-muted)] p-4 text-xs leading-5">
            {value}
          </pre>
        ) : (
          <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-[var(--text-muted)]">
            {value}
          </p>
        )
      ) : (
        <p className="mt-3 text-xs text-[var(--text-muted)]">{t("finding.partial")}</p>
      )}
    </section>
  );
}
