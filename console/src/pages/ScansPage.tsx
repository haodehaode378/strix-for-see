import { ListPlus, RefreshCw, ScanSearch } from "lucide-react";

import { PageHeader } from "../components/ui/PageHeader";
import { ScanStatusBadge } from "../components/ui/ScanStatusBadge";
import { useScans } from "../features/scan-control/useScans";
import { formatRunDate } from "../features/local-runs/formatRunDate";
import { useLocale } from "../shared/i18n/useLocale";
import { NavigationLink } from "../shared/navigation/NavigationLink";

export function ScansPage() {
  const { locale, t } = useLocale();
  const { scans, state, refresh } = useScans();

  return (
    <div>
      <PageHeader
        eyebrow={t("scans.eyebrow")}
        title={t("scans.title")}
        description={t("scans.description")}
        actions={
          <div className="flex gap-2">
            <button
              type="button"
              onClick={refresh}
              className="inline-flex items-center gap-2 rounded-xl border border-[var(--border)] px-3.5 py-2.5 text-sm font-semibold text-[var(--text-muted)] transition active:scale-[0.98]"
              aria-label={t("scans.refresh")}
            >
              <RefreshCw className="size-4" />
            </button>
            <NavigationLink
              to="/scans/new"
              className="inline-flex items-center gap-2 rounded-xl bg-[var(--accent)] px-4 py-2.5 text-sm font-semibold text-white transition active:scale-[0.98]"
            >
              <ListPlus className="size-4" />
              {t("scans.create")}
            </NavigationLink>
          </div>
        }
      />

      {state === "loading" ? <ScanSkeleton /> : null}
      {state === "error" ? (
        <EmptyState message={t("scans.loadFailed")} action={refresh} />
      ) : null}
      {state === "ready" && scans.length === 0 ? (
        <EmptyState message={t("scans.empty")} />
      ) : null}
      {scans.length > 0 ? (
        <div className="mt-7 overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)]">
          {scans.map((scan) => (
            <NavigationLink
              key={scan.id}
              to={`/scans/${scan.id}`}
              className="grid gap-3 border-b border-[var(--border)] px-5 py-4 transition last:border-b-0 hover:bg-[var(--surface-raised)] sm:grid-cols-[1fr_auto] sm:items-center"
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="truncate text-sm font-semibold text-[var(--text)]">
                    {scan.target}
                  </h2>
                  <ScanStatusBadge status={scan.status} />
                </div>
                <p className="mt-1.5 text-xs text-[var(--text-muted)]">
                  {t(`newScan.profile.${scan.options.scanProfile}`)} ·{" "}
                  {t(`newScan.mode.${scan.options.riskMode}`)}
                  {scan.queuePosition
                    ? ` · ${t("scans.queuePosition")} ${scan.queuePosition}`
                    : ""}
                </p>
              </div>
              <div className="text-xs text-[var(--text-muted)] sm:text-right">
                <p>{formatRunDate(scan.createdAt, locale)}</p>
                {scan.errorCode ? (
                  <p className="mt-1 text-[var(--danger)]">{t("scans.needsAttention")}</p>
                ) : null}
              </div>
            </NavigationLink>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function ScanSkeleton() {
  return (
    <div className="mt-7 grid gap-2" aria-busy="true">
      {[0, 1, 2].map((item) => (
        <div
          key={item}
          className="h-20 animate-pulse rounded-2xl border border-[var(--border)] bg-[var(--surface)]"
        />
      ))}
    </div>
  );
}

function EmptyState({
  message,
  action,
}: {
  message: string;
  action?: () => void;
}) {
  const { t } = useLocale();
  return (
    <div className="mt-7 grid min-h-56 place-items-center rounded-2xl border border-dashed border-[var(--border-strong)] p-8 text-center">
      <div>
        <ScanSearch className="mx-auto size-8 text-[var(--text-muted)]" />
        <p className="mt-3 text-sm text-[var(--text-muted)]">{message}</p>
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
