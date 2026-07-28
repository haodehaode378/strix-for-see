import { FileSearch, RefreshCw } from "lucide-react";

import { PageHeader } from "../components/ui/PageHeader";
import { RunStateBadge } from "../components/ui/RunStateBadge";
import type { LocalRun } from "../features/local-runs/contracts";
import { formatRunDate } from "../features/local-runs/formatRunDate";
import { useLocalRuns } from "../features/local-runs/useLocalRuns";
import type { MessageKey } from "../shared/i18n/messages";
import { useLocale } from "../shared/i18n/useLocale";
import { NavigationLink } from "../shared/navigation/NavigationLink";

export function LocalRunsPage() {
  const { locale, t } = useLocale();
  const { data, state, refresh } = useLocalRuns();

  return (
    <div>
      <PageHeader
        eyebrow={t("localRuns.eyebrow")}
        title={t("localRuns.title")}
        description={t("localRuns.description")}
        actions={
          <button
            type="button"
            onClick={refresh}
            disabled={state === "loading"}
            className="inline-flex items-center gap-2 rounded-xl bg-[var(--accent)] px-4 py-2.5 text-sm font-semibold text-white transition disabled:cursor-wait disabled:opacity-60"
          >
            <RefreshCw className={`size-4 ${state === "loading" ? "animate-spin" : ""}`} />
            {t("localRuns.refresh")}
          </button>
        }
      />

      {state === "loading" && !data ? <RunSkeleton /> : null}
      {state === "error" && !data ? (
        <Notice title={t("localRuns.loadFailed")} action={refresh} />
      ) : null}
      {data ? (
        <div className="mt-7">
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-[var(--text-muted)]">
            <span>
              {data.runs.length} {t("localRuns.recordCount")} · {data.sources.length}{" "}
              {t("localRuns.sourceCount")}
            </span>
            <span>{formatRunDate(data.scannedAt, locale)}</span>
          </div>

          {data.sources.some((source) => !source.exists) ? (
            <p className="mt-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-xs leading-5 text-[var(--text-muted)]">
              {t("localRuns.missingSource")}
            </p>
          ) : null}

          {data.runs.length === 0 ? (
            <Notice title={t("localRuns.empty")} />
          ) : (
            <div className="mt-4 grid gap-3">
              {data.runs.map((run) => (
                <RunCard key={run.id} run={run} />
              ))}
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

function RunCard({ run }: { run: LocalRun }) {
  const { locale, t } = useLocale();
  const findingCount = Object.values(run.severityCounts).reduce(
    (total, value) => total + value,
    0,
  );

  return (
    <NavigationLink
      to={`/local-runs/${run.id}`}
      className="group grid gap-4 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 transition hover:-translate-y-0.5 hover:border-[var(--border-strong)] sm:grid-cols-[1fr_auto]"
    >
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="truncate font-semibold text-[var(--text)]">{run.name}</h2>
          <RunStateBadge state={run.state} />
        </div>
        <p className="mt-2 truncate font-mono text-xs text-[var(--text-muted)]">
          {run.target ?? run.path}
        </p>
        {run.diagnostic ? (
          <p className="mt-2 text-xs text-[var(--warning)]">
            {t(`localRuns.diagnostic.${run.diagnostic}` as MessageKey)}
          </p>
        ) : null}
      </div>
      <div className="flex items-end justify-between gap-5 sm:flex-col sm:items-end">
        <div className="flex gap-2 text-[11px]">
          {run.severityCounts.critical > 0 ? (
            <Severity label="C" value={run.severityCounts.critical} tone="danger" />
          ) : null}
          {run.severityCounts.high > 0 ? (
            <Severity label="H" value={run.severityCounts.high} tone="warning" />
          ) : null}
          {findingCount === 0 ? (
            <span className="text-[var(--text-muted)]">{t("localRuns.noFindings")}</span>
          ) : null}
        </div>
        <time className="text-xs text-[var(--text-muted)]">
          {formatRunDate(run.updatedAt, locale)}
        </time>
      </div>
    </NavigationLink>
  );
}

function Severity({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "danger" | "warning";
}) {
  return (
    <span
      className={`rounded-md px-2 py-1 font-semibold ${
        tone === "danger"
          ? "bg-red-500/10 text-[var(--danger)]"
          : "bg-amber-500/10 text-[var(--warning)]"
      }`}
    >
      {label} {value}
    </span>
  );
}

function RunSkeleton() {
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

function Notice({
  title,
  action,
}: {
  title: string;
  action?: () => void;
}) {
  const { t } = useLocale();
  return (
    <div className="mt-7 grid min-h-52 place-items-center rounded-2xl border border-dashed border-[var(--border-strong)] p-8 text-center">
      <div>
        <FileSearch className="mx-auto size-7 text-[var(--text-muted)]" />
        <p className="mt-3 text-sm text-[var(--text-muted)]">{title}</p>
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
