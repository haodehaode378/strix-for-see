import { ArrowLeft, FileSearch, RefreshCw, ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";

import { ReportExportPanel } from "../components/findings/ReportExportPanel";
import { PageHeader } from "../components/ui/PageHeader";
import { SeverityBadge } from "../components/ui/SeverityBadge";
import type {
  Finding,
  FindingSeverity,
  FindingWorkflowState,
} from "../features/findings/contracts";
import { useFindings } from "../features/findings/useFindings";
import { formatRunDate } from "../features/local-runs/formatRunDate";
import type { MessageKey } from "../shared/i18n/messages";
import { useLocale } from "../shared/i18n/useLocale";
import { NavigationLink } from "../shared/navigation/NavigationLink";

const severities: Array<FindingSeverity | "all"> = [
  "all",
  "critical",
  "high",
  "medium",
  "low",
];
const states: Array<FindingWorkflowState | "all"> = [
  "all",
  "pending",
  "confirmed",
  "acceptedRisk",
  "fixed",
  "falsePositive",
];

function initialFilter(name: string): string {
  return new URLSearchParams(window.location.search).get(name) ?? "all";
}

export function FindingsPage({ runName: routeRunName }: { runName?: string }) {
  const { locale, t } = useLocale();
  const runName = routeRunName ?? new URLSearchParams(window.location.search).get("run") ?? undefined;
  const { data, state, refresh } = useFindings(runName);
  const [severity, setSeverity] = useState(initialFilter("severity"));
  const [workflow, setWorkflow] = useState(initialFilter("state"));
  const [target, setTarget] = useState(initialFilter("target"));
  const [dateFrom, setDateFrom] = useState(initialFilter("from") === "all" ? "" : initialFilter("from"));

  const tasks = useMemo(() => buildTaskSummaries(data?.findings ?? []), [data]);

  const targets = useMemo(
    () =>
      [...new Set((data?.findings ?? []).map((finding) => finding.target).filter(Boolean))].sort(),
    [data],
  );
  const filtered = useMemo(
    () =>
      (data?.findings ?? []).filter((finding) => {
        const severityMatch = severity === "all" || finding.severity === severity;
        const stateMatch = workflow === "all" || finding.workflowState === workflow;
        const targetMatch = target === "all" || finding.target === target;
        const dateMatch =
          !dateFrom ||
          finding.occurrences.some(
            (occurrence) =>
              occurrence.observedAt &&
              new Date(occurrence.observedAt).getTime() >= new Date(dateFrom).getTime(),
          );
        return severityMatch && stateMatch && targetMatch && dateMatch;
      }),
    [data, dateFrom, severity, target, workflow],
  );

  const setFilter = (name: string, value: string, setter: (value: string) => void) => {
    setter(value);
    const params = new URLSearchParams(window.location.search);
    if (value && value !== "all") params.set(name, value);
    else params.delete(name);
    window.history.replaceState({}, "", `${window.location.pathname}?${params.toString()}`);
  };

  return (
    <div>
      <PageHeader
        eyebrow={t(runName ? "findings.task.eyebrow" : "findings.eyebrow")}
        title={t(runName ? "findings.task.title" : "findings.title")}
        description={
          runName ? `${t("findings.runScope")} ${runName}` : t("findings.description")
        }
        actions={
          <button
            type="button"
            onClick={refresh}
            className="inline-flex items-center gap-2 rounded-xl border border-[var(--border)] px-4 py-2.5 text-sm font-semibold transition active:scale-[0.98]"
          >
            <RefreshCw className="size-4" />
            {t("findings.refresh")}
          </button>
        }
      />

      {state === "loading" && !data ? <FindingSkeleton /> : null}
      {state === "error" && !data ? (
        <Notice text={t("findings.loadFailed")} action={refresh} />
      ) : null}
      {data ? (
        runName ? <>
          <NavigationLink
            to="/findings"
            className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-[var(--text-muted)] hover:text-[var(--text)]"
          >
            <ArrowLeft className="size-4" />
            {t("findings.backToTasks")}
          </NavigationLink>
          <section className="mt-7 grid gap-px overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--border)] sm:grid-cols-4">
            {severities.slice(1).map((item) => (
              <div key={item} className="bg-[var(--surface)] p-4">
                <span className="text-xs text-[var(--text-muted)]">
                  {t(`findings.severity.${item}` as MessageKey)}
                </span>
                <strong className="mt-2 block text-2xl tabular-nums">
                  {data.severityCounts[item as FindingSeverity]}
                </strong>
              </div>
            ))}
          </section>

          <section className="mt-5 grid gap-3 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 md:grid-cols-4">
            <FilterSelect
              label={t("findings.filterSeverity")}
              value={severity}
              onChange={(value) => setFilter("severity", value, setSeverity)}
              options={severities.map((item) => [
                item,
                item === "all"
                  ? t("findings.all")
                  : t(`findings.severity.${item}` as MessageKey),
              ])}
            />
            <FilterSelect
              label={t("findings.filterState")}
              value={workflow}
              onChange={(value) => setFilter("state", value, setWorkflow)}
              options={states.map((item) => [
                item,
                item === "all"
                  ? t("findings.all")
                  : t(`findings.state.${item}` as MessageKey),
              ])}
            />
            <FilterSelect
              label={t("findings.filterTarget")}
              value={target}
              onChange={(value) => setFilter("target", value, setTarget)}
              options={[
                ["all", t("findings.all")],
                ...targets.map((item) => [item as string, item as string] as [string, string]),
              ]}
            />
            <label className="grid gap-2 text-xs text-[var(--text-muted)]">
              {t("findings.filterDate")}
              <input
                type="date"
                value={dateFrom}
                onChange={(event) =>
                  setFilter("from", event.target.value, setDateFrom)
                }
                className="rounded-xl border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-2.5 text-sm text-[var(--text)]"
              />
            </label>
          </section>

          {filtered.length === 0 ? (
            <Notice text={data.findings.length ? t("findings.noMatches") : t("findings.empty")} />
          ) : (
            <div className="mt-5 grid gap-3">
              {filtered.map((finding) => (
                <NavigationLink
                  key={finding.id}
                  to={`/findings/${finding.id}`}
                  className="group grid gap-4 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 transition hover:-translate-y-0.5 hover:border-[var(--border-strong)] sm:grid-cols-[1fr_auto]"
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <SeverityBadge severity={finding.severity} />
                      <span className="rounded-md bg-[var(--surface-muted)] px-2 py-1 text-[11px] text-[var(--text-muted)]">
                        {t(`findings.state.${finding.workflowState}` as MessageKey)}
                      </span>
                    </div>
                    <h2 className="mt-3 font-semibold">{finding.title}</h2>
                    <p className="mt-2 truncate font-mono text-xs text-[var(--text-muted)]">
                      {finding.endpoint ?? finding.target ?? "—"}
                    </p>
                  </div>
                  <div className="flex items-end justify-between gap-4 text-xs text-[var(--text-muted)] sm:flex-col sm:items-end">
                    <span>
                      {finding.occurrences.length} {t("findings.occurrences")}
                    </span>
                    <span>
                      {formatRunDate(finding.occurrences[0]?.observedAt, locale)}
                    </span>
                  </div>
                </NavigationLink>
              ))}
            </div>
          )}
          {filtered.length > 0 ? (
            <div className="mt-7">
              <ReportExportPanel findingIds={filtered.map((finding) => finding.id)} />
            </div>
          ) : null}
        </> : tasks.length ? (
          <div className="mt-7 grid gap-3">
            {tasks.map((task) => (
              <NavigationLink
                key={task.runName}
                to={`/findings/run/${encodeURIComponent(task.runName)}`}
                className="group grid gap-4 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 transition hover:-translate-y-0.5 hover:border-[var(--border-strong)] active:scale-[0.99] sm:grid-cols-[1fr_auto]"
              >
                <div className="min-w-0">
                  <h2 className="truncate font-semibold">{task.runName}</h2>
                  <p className="mt-2 truncate font-mono text-xs text-[var(--text-muted)]">
                    {task.target ?? t("finding.partial")}
                  </p>
                  <p className="mt-3 text-xs text-[var(--text-muted)]">
                    {task.findingCount} {t("findings.task.findingCount")}
                  </p>
                </div>
                <div className="flex items-end justify-between gap-4 sm:flex-col sm:items-end">
                  <div className="flex flex-wrap justify-end gap-2">
                    {severities.slice(1).map((item) =>
                      task.severityCounts[item as FindingSeverity] ? (
                        <span
                          key={item}
                          className="rounded-md bg-[var(--surface-muted)] px-2 py-1 text-[11px] text-[var(--text-muted)]"
                        >
                          {t(`findings.severity.${item}` as MessageKey)} {task.severityCounts[item as FindingSeverity]}
                        </span>
                      ) : null,
                    )}
                  </div>
                  <time className="text-xs text-[var(--text-muted)]">
                    {formatRunDate(task.observedAt, locale)}
                  </time>
                </div>
              </NavigationLink>
            ))}
          </div>
        ) : (
          <Notice text={data.findings.length ? t("findings.noTaskRecords") : t("findings.empty")} />
        )
      ) : null}
    </div>
  );
}

function buildTaskSummaries(findings: Finding[]) {
  const tasks = new Map<
    string,
    {
      runName: string;
      target: string | null;
      observedAt: string | null;
      findingIds: Set<string>;
      severityCounts: Record<FindingSeverity, number>;
    }
  >();
  for (const finding of findings) {
    for (const occurrence of finding.occurrences) {
      const task = tasks.get(occurrence.runName) ?? {
        runName: occurrence.runName,
        target: occurrence.target ?? finding.target,
        observedAt: occurrence.observedAt,
        findingIds: new Set<string>(),
        severityCounts: { critical: 0, high: 0, medium: 0, low: 0 },
      };
      if (!task.findingIds.has(finding.id)) {
        task.findingIds.add(finding.id);
        task.severityCounts[finding.severity] += 1;
      }
      if (
        occurrence.observedAt &&
        (!task.observedAt || occurrence.observedAt > task.observedAt)
      ) {
        task.observedAt = occurrence.observedAt;
      }
      tasks.set(occurrence.runName, task);
    }
  }
  return [...tasks.values()]
    .map(({ findingIds, ...task }) => ({ ...task, findingCount: findingIds.size }))
    .sort((left, right) => (right.observedAt ?? "").localeCompare(left.observedAt ?? ""));
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<[string, string]>;
}) {
  return (
    <label className="grid gap-2 text-xs text-[var(--text-muted)]">
      {label}
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-xl border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-2.5 text-sm text-[var(--text)]"
      >
        {options.map(([option, labelText]) => (
          <option key={option} value={option}>
            {labelText}
          </option>
        ))}
      </select>
    </label>
  );
}

function FindingSkeleton() {
  return (
    <div className="mt-7 grid gap-3" aria-busy="true">
      {[0, 1, 2].map((item) => (
        <div
          key={item}
          className="h-28 animate-pulse rounded-2xl border border-[var(--border)] bg-[var(--surface)]"
        />
      ))}
    </div>
  );
}

function Notice({ text, action }: { text: string; action?: () => void }) {
  const { t } = useLocale();
  return (
    <div className="mt-7 grid min-h-52 place-items-center rounded-2xl border border-dashed border-[var(--border-strong)] p-8 text-center">
      <div>
        {action ? (
          <FileSearch className="mx-auto size-7 text-[var(--warning)]" />
        ) : (
          <ShieldCheck className="mx-auto size-7 text-[var(--text-muted)]" />
        )}
        <p className="mt-3 text-sm text-[var(--text-muted)]">{text}</p>
        {action ? (
          <button
            type="button"
            onClick={action}
            className="mt-4 text-sm font-semibold text-[var(--accent)]"
          >
            {t("common.retry")}
          </button>
        ) : null}
      </div>
    </div>
  );
}
