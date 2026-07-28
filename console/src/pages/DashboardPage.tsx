import { ArrowRight, CirclePlus, Server, ShieldCheck } from "lucide-react";

import { PageHeader } from "../components/ui/PageHeader";
import { ScanStatusBadge } from "../components/ui/ScanStatusBadge";
import { ServiceConnectionPanel } from "../components/ui/ServiceConnectionPanel";
import { useScans } from "../features/scan-control/useScans";
import { useLocale } from "../shared/i18n/useLocale";
import { NavigationLink } from "../shared/navigation/NavigationLink";

export function DashboardPage() {
  const { t } = useLocale();
  const { scans, state } = useScans();
  const currentScan = scans.find((scan) =>
    ["queued", "preparing", "running", "reporting", "stopping", "terminating"].includes(
      scan.status,
    ),
  );
  const queuedCount = scans.filter((scan) => scan.status === "queued").length;

  return (
    <div>
      <PageHeader
        eyebrow={t("dashboard.eyebrow")}
        title={t("dashboard.title")}
        description={t("dashboard.description")}
        actions={
          <NavigationLink
            to="/scans/new"
            className="inline-flex items-center gap-2 rounded-xl bg-[var(--accent)] px-4 py-2.5 text-sm font-semibold text-[#071512] transition hover:bg-[var(--accent-strong)] active:scale-[0.98]"
          >
            <CirclePlus className="size-4" />
            {t("dashboard.newScan")}
          </NavigationLink>
        }
      />

      <section className="mt-7 grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(280px,0.65fr)]">
        <div className="min-w-0">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-semibold tracking-[-0.02em]">{t("dashboard.current")}</h2>
              <p className="mt-1 text-xs text-[var(--text-muted)]">{t("dashboard.currentHint")}</p>
            </div>
          </div>

          <div className="mt-4 grid min-h-64 place-items-center rounded-2xl border border-dashed border-[var(--border-strong)] bg-[color-mix(in_srgb,var(--surface)_75%,transparent)] p-8">
            {state === "loading" ? (
              <div className="h-24 w-full animate-pulse rounded-xl bg-[var(--surface-muted)]" />
            ) : currentScan ? (
              <div className="w-full text-left">
                <div className="flex flex-wrap items-center gap-2">
                  <ScanStatusBadge status={currentScan.status} />
                  {queuedCount > 0 ? (
                    <span className="text-xs text-[var(--text-muted)]">
                      {queuedCount} {t("dashboard.queued")}
                    </span>
                  ) : null}
                </div>
                <h3 className="mt-5 break-all text-xl font-semibold tracking-[-0.03em]">
                  {currentScan.target}
                </h3>
                <p className="mt-2 text-sm text-[var(--text-muted)]">
                  {t("dashboard.realActivity")}
                </p>
                <NavigationLink
                  to={`/scans/${currentScan.id}`}
                  className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-[var(--accent-strong)] transition hover:gap-3"
                >
                  {t("dashboard.openScan")}
                  <ArrowRight className="size-4" />
                </NavigationLink>
              </div>
            ) : (
              <div className="text-center">
              <span className="mx-auto grid size-11 place-items-center rounded-2xl bg-[var(--surface-muted)] text-[var(--text-muted)]">
                <ShieldCheck className="size-5" strokeWidth={1.7} />
              </span>
              <h3 className="mt-4 text-sm font-semibold">{t("dashboard.noActiveScan")}</h3>
              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[var(--text-muted)]">
                {t("dashboard.noActiveScanHint")}
              </p>
              <NavigationLink
                to="/scans/new"
                className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-[var(--accent-strong)] transition hover:gap-3"
              >
                {t("dashboard.prepareScan")}
                <ArrowRight className="size-4" />
              </NavigationLink>
              </div>
            )}
          </div>
        </div>

        <div>
          <div className="flex items-center gap-2">
            <Server className="size-4 text-[var(--text-muted)]" />
            <h2 className="text-base font-semibold tracking-[-0.02em]">{t("dashboard.system")}</h2>
          </div>
          <ServiceConnectionPanel />
        </div>
      </section>

      <section className="mt-8 border-t border-[var(--border)] pt-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold tracking-[-0.02em]">{t("dashboard.recent")}</h2>
            <p className="mt-1 text-xs text-[var(--text-muted)]">{t("dashboard.recentEmpty")}</p>
          </div>
          <NavigationLink
            to="/local-runs"
            className="text-xs font-semibold text-[var(--accent-strong)] hover:underline"
          >
            {t("dashboard.viewRecords")}
          </NavigationLink>
        </div>
      </section>
    </div>
  );
}
