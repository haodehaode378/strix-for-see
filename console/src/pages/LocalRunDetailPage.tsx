import { ArrowLeft, Download, FileWarning } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "../components/ui/PageHeader";
import { RunStateBadge } from "../components/ui/RunStateBadge";
import { formatRunDate } from "../features/local-runs/formatRunDate";
import { downloadArtifact } from "../features/local-runs/localRunsClient";
import { useLocalRun } from "../features/local-runs/useLocalRun";
import { useLocale } from "../shared/i18n/useLocale";
import { NavigationLink } from "../shared/navigation/NavigationLink";

export function LocalRunDetailPage({ id }: { id: string }) {
  const { locale, t } = useLocale();
  const { run, state } = useLocalRun(id);
  const [downloadError, setDownloadError] = useState(false);

  if (state === "loading") {
    return (
      <div className="h-72 animate-pulse rounded-2xl border border-[var(--border)] bg-[var(--surface)]" />
    );
  }
  if (!run) {
    return (
      <div className="grid min-h-72 place-items-center text-center">
        <div>
          <FileWarning className="mx-auto size-8 text-[var(--warning)]" />
          <p className="mt-3 text-sm text-[var(--text-muted)]">{t("localRun.notFound")}</p>
          <NavigationLink
            to="/local-runs"
            className="mt-4 inline-block text-sm font-semibold text-[var(--accent)]"
          >
            {t("localRun.back")}
          </NavigationLink>
        </div>
      </div>
    );
  }

  const fields = [
    [t("localRun.target"), run.target ?? "—"],
    [t("localRun.mode"), run.scanMode ?? "—"],
    [t("localRun.engineStatus"), run.engineStatus ?? "—"],
    [t("localRun.started"), formatRunDate(run.startTime, locale)],
    [t("localRun.ended"), formatRunDate(run.endTime, locale)],
    [t("localRun.updated"), formatRunDate(run.updatedAt, locale)],
  ];

  const handleDownload = async (name: string) => {
    setDownloadError(false);
    try {
      await downloadArtifact(run.id, name);
    } catch {
      setDownloadError(true);
    }
  };

  return (
    <div>
      <NavigationLink
        to="/local-runs"
        className="mb-5 inline-flex items-center gap-2 text-sm font-semibold text-[var(--text-muted)] hover:text-[var(--text)]"
      >
        <ArrowLeft className="size-4" />
        {t("localRun.back")}
      </NavigationLink>
      <PageHeader
        eyebrow={t("localRun.eyebrow")}
        title={run.name}
        description={run.path}
        actions={<RunStateBadge state={run.state} />}
      />

      <div className="mt-7 grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
          <h2 className="text-sm font-semibold text-[var(--text)]">{t("localRun.details")}</h2>
          <dl className="mt-4 divide-y divide-[var(--border)]">
            {fields.map(([label, value]) => (
              <div key={label} className="grid gap-1 py-3 sm:grid-cols-[140px_1fr]">
                <dt className="text-xs text-[var(--text-muted)]">{label}</dt>
                <dd className="break-all text-sm text-[var(--text)]">{value}</dd>
              </div>
            ))}
          </dl>
        </section>

        <div className="space-y-6">
          <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
            <h2 className="text-sm font-semibold text-[var(--text)]">
              {t("localRun.severity")}
            </h2>
            <div className="mt-4 grid grid-cols-4 gap-2 text-center">
              {Object.entries(run.severityCounts).map(([severity, count]) => (
                <div key={severity} className="rounded-xl bg-[var(--surface-muted)] p-3">
                  <strong className="block text-lg text-[var(--text)]">{count}</strong>
                  <span className="text-[10px] text-[var(--text-muted)] uppercase">
                    {severity}
                  </span>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
            <h2 className="text-sm font-semibold text-[var(--text)]">
              {t("localRun.artifacts")}
            </h2>
            {run.artifacts.length === 0 ? (
              <p className="mt-3 text-xs text-[var(--text-muted)]">
                {t("localRun.noArtifacts")}
              </p>
            ) : (
              <div className="mt-3 space-y-2">
                {run.artifacts.map((artifact) => (
                  <button
                    key={artifact.name}
                    type="button"
                    onClick={() => void handleDownload(artifact.name)}
                    className="flex w-full items-center justify-between gap-3 rounded-xl border border-[var(--border)] px-3 py-2.5 text-left transition hover:border-[var(--border-strong)]"
                  >
                    <span className="min-w-0 truncate font-mono text-xs text-[var(--text)]">
                      {artifact.name}
                    </span>
                    <Download className="size-4 shrink-0 text-[var(--accent)]" />
                  </button>
                ))}
              </div>
            )}
            {downloadError ? (
              <p className="mt-3 text-xs text-[var(--danger)]" aria-live="polite">
                {t("localRun.downloadFailed")}
              </p>
            ) : null}
          </section>
        </div>
      </div>
    </div>
  );
}
