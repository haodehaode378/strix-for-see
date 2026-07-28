import {
  ArrowLeft,
  Ban,
  CircleAlert,
  Clock3,
  OctagonX,
  Shield,
} from "lucide-react";
import { useState } from "react";

import { PageHeader } from "../components/ui/PageHeader";
import { ScanStatusBadge } from "../components/ui/ScanStatusBadge";
import { formatRunDate } from "../features/local-runs/formatRunDate";
import { stopScan, terminateScan } from "../features/scan-control/scanClient";
import { useScan } from "../features/scan-control/useScans";
import type { MessageKey } from "../shared/i18n/messages";
import { useLocale } from "../shared/i18n/useLocale";
import { NavigationLink } from "../shared/navigation/NavigationLink";

const errorKeys: Record<string, MessageKey> = {
  processStartFailed: "scan.error.processStartFailed",
  providerNotConfigured: "scan.error.providerNotConfigured",
  durationLimitReached: "scan.error.durationLimitReached",
  processControlLost: "scan.error.processControlLost",
  serviceRestarted: "scan.error.serviceRestarted",
  serviceRestartedProcessStillRunning:
    "scan.error.serviceRestartedProcessStillRunning",
};

export function ScanDetailPage({ id }: { id: string }) {
  const { locale, t } = useLocale();
  const { scan, state, refresh, setScan } = useScan(id);
  const [busy, setBusy] = useState(false);
  const [confirmTerminate, setConfirmTerminate] = useState(false);
  const [actionError, setActionError] = useState(false);

  if (state === "loading" && !scan) {
    return (
      <div className="h-72 animate-pulse rounded-2xl border border-[var(--border)] bg-[var(--surface)]" />
    );
  }
  if (!scan) {
    return (
      <div className="grid min-h-72 place-items-center text-sm text-[var(--text-muted)]">
        {t("scan.notFound")}
      </div>
    );
  }

  const stoppable = ["queued", "preparing", "running", "reporting"].includes(
    scan.status,
  );
  const terminable = ["preparing", "running", "reporting", "stopping"].includes(
    scan.status,
  );
  const act = async (action: "stop" | "terminate") => {
    setBusy(true);
    setActionError(false);
    try {
      setScan(action === "stop" ? await stopScan(scan.id) : await terminateScan(scan.id));
      setConfirmTerminate(false);
    } catch {
      setActionError(true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <NavigationLink
        to="/scans"
        className="mb-5 inline-flex items-center gap-2 text-sm font-semibold text-[var(--text-muted)] hover:text-[var(--text)]"
      >
        <ArrowLeft className="size-4" />
        {t("scan.back")}
      </NavigationLink>
      <PageHeader
        eyebrow={t("scan.eyebrow")}
        title={scan.target}
        description={scan.engineRunName}
        actions={<ScanStatusBadge status={scan.status} />}
      />

      <div className="mt-7 grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
        <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
          <h2 className="text-sm font-semibold text-[var(--text)]">{t("scan.plan")}</h2>
          <dl className="mt-4 divide-y divide-[var(--border)]">
            <Detail label={t("scan.targetType")} value={t(`newScan.target.${scan.targetType}` as MessageKey)} />
            <Detail
              label={t("newScan.riskMode")}
              value={t(`newScan.mode.${scan.options.riskMode}`)}
            />
            <Detail
              label={t("newScan.scanProfile")}
              value={t(`newScan.profile.${scan.options.scanProfile}`)}
            />
            <Detail
              label={t("newScan.rate")}
              value={String(scan.options.requestRatePerMinute)}
            />
            <Detail
              label={t("newScan.duration")}
              value={`${scan.options.maxDurationMinutes} ${t("common.minutes")}`}
            />
            <Detail
              label={t("newScan.budget")}
              value={`$${scan.options.maxBudgetUsd.toFixed(2)}`}
            />
          </dl>
        </section>

        <div className="space-y-6">
          <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-[var(--text)]">
              <Clock3 className="size-4 text-[var(--accent)]" />
              {t("scan.lifecycle")}
            </h2>
            <dl className="mt-4 space-y-3">
              <Detail label={t("scan.created")} value={formatRunDate(scan.createdAt, locale)} compact />
              <Detail label={t("scan.started")} value={formatRunDate(scan.startedAt, locale)} compact />
              <Detail label={t("scan.ended")} value={formatRunDate(scan.endedAt, locale)} compact />
              {scan.queuePosition ? (
                <Detail
                  label={t("scans.queuePosition")}
                  value={String(scan.queuePosition)}
                  compact
                />
              ) : null}
            </dl>
          </section>

          {scan.errorCode ? (
            <section className="rounded-2xl border border-[color-mix(in_srgb,var(--danger)_35%,var(--border))] bg-red-500/5 p-5">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-[var(--danger)]">
                <CircleAlert className="size-4" />
                {t("scan.attention")}
              </h2>
              <p className="mt-2 text-xs leading-5 text-[var(--text-muted)]">
                {t(errorKeys[scan.errorCode] ?? "scan.error.unknown")}
              </p>
            </section>
          ) : null}

          {stoppable || terminable ? (
            <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-[var(--text)]">
                <Shield className="size-4 text-[var(--accent)]" />
                {t("scan.controls")}
              </h2>
              <p className="mt-2 text-xs leading-5 text-[var(--text-muted)]">
                {t("scan.controlsHint")}
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                {stoppable ? (
                  <button
                    type="button"
                    onClick={() => void act("stop")}
                    disabled={busy}
                    className="inline-flex items-center gap-2 rounded-xl border border-[var(--border)] px-4 py-2.5 text-sm font-semibold text-[var(--text)] transition active:scale-[0.98] disabled:opacity-50"
                  >
                    <Ban className="size-4" />
                    {scan.status === "queued" ? t("scan.cancelQueued") : t("scan.safeStop")}
                  </button>
                ) : null}
                {terminable ? (
                  confirmTerminate ? (
                    <button
                      type="button"
                      onClick={() => void act("terminate")}
                      disabled={busy}
                      className="inline-flex items-center gap-2 rounded-xl bg-[var(--danger)] px-4 py-2.5 text-sm font-semibold text-white transition active:scale-[0.98]"
                    >
                      <OctagonX className="size-4" />
                      {t("scan.confirmTerminate")}
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setConfirmTerminate(true)}
                      disabled={busy}
                      className="inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold text-[var(--danger)] transition active:scale-[0.98]"
                    >
                      <OctagonX className="size-4" />
                      {t("scan.emergencyTerminate")}
                    </button>
                  )
                ) : null}
              </div>
              {confirmTerminate ? (
                <p className="mt-3 text-xs leading-5 text-[var(--danger)]">
                  {t("scan.terminateWarning")}
                </p>
              ) : null}
              {actionError ? (
                <button
                  type="button"
                  onClick={refresh}
                  className="mt-3 text-xs font-semibold text-[var(--danger)]"
                >
                  {t("scan.actionFailed")}
                </button>
              ) : null}
            </section>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function Detail({
  label,
  value,
  compact = false,
}: {
  label: string;
  value: string;
  compact?: boolean;
}) {
  return (
    <div
      className={
        compact
          ? "grid grid-cols-[110px_1fr] gap-3"
          : "grid gap-1 py-3 sm:grid-cols-[160px_1fr]"
      }
    >
      <dt className="text-xs text-[var(--text-muted)]">{label}</dt>
      <dd className="break-all text-sm text-[var(--text)]">{value}</dd>
    </div>
  );
}
