import { Download, RefreshCw, Settings2, ShieldCheck } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";

import { ProviderPanel } from "../components/scan/ProviderPanel";
import { PageHeader } from "../components/ui/PageHeader";
import type {
  ApplicationUpdate,
  SandboxPullStatus,
  SandboxUpdate,
} from "../features/updates/contracts";
import {
  installDesktopUpdate,
  isDesktopRuntime,
  type UpdateProgress,
} from "../features/updates/desktopUpdater";
import {
  authorizeApplicationUpdate,
  checkApplicationUpdate,
  checkSandboxUpdate,
  getSandboxPullStatus,
  startSandboxPull,
} from "../features/updates/updatesClient";
import { useLocale } from "../shared/i18n/useLocale";

export function SettingsPage() {
  const { locale, t } = useLocale();
  const [application, setApplication] = useState<ApplicationUpdate | null>(null);
  const [sandbox, setSandbox] = useState<SandboxUpdate | null>(null);
  const [pull, setPull] = useState<SandboxPullStatus | null>(null);
  const [appProgress, setAppProgress] = useState<UpdateProgress | null>(null);
  const [confirmApp, setConfirmApp] = useState(false);
  const [confirmSandbox, setConfirmSandbox] = useState(false);
  const [busy, setBusy] = useState<"check" | "app" | "sandbox" | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (pull?.state !== "downloading" && pull?.state !== "verifying") return;
    const timer = window.setInterval(() => {
      void getSandboxPullStatus().then(setPull).catch(() => setError("pullStatus"));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [pull?.state]);

  const checkUpdates = async () => {
    setBusy("check");
    setError(null);
    const [applicationResult, sandboxResult] = await Promise.allSettled([
      checkApplicationUpdate(),
      checkSandboxUpdate(),
    ]);
    if (applicationResult.status === "fulfilled") {
      setApplication(applicationResult.value);
    }
    if (sandboxResult.status === "fulfilled") {
      setSandbox(sandboxResult.value);
    }
    if (
      applicationResult.status === "rejected" ||
      sandboxResult.status === "rejected"
    ) {
      setError("check");
    }
    setBusy(null);
  };

  const updateApplication = async () => {
    setBusy("app");
    setError(null);
    try {
      await authorizeApplicationUpdate();
      await installDesktopUpdate(setAppProgress);
    } catch {
      setError("app");
    } finally {
      setBusy(null);
    }
  };

  const updateSandbox = async () => {
    setBusy("sandbox");
    setError(null);
    try {
      setPull(await startSandboxPull());
    } catch {
      setError("sandbox");
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="space-y-8">
      <PageHeader
        eyebrow={t("settings.eyebrow")}
        title={t("settings.title")}
        description={t("settings.description")}
        actions={
          <button
            type="button"
            onClick={() => void checkUpdates()}
            disabled={busy !== null}
            className="inline-flex items-center gap-2 rounded-xl bg-[var(--accent)] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
          >
            <RefreshCw className="size-4" aria-hidden="true" />
            {busy === "check" ? t("settings.checking") : t("settings.checkUpdates")}
          </button>
        }
      />

      <ProviderPanel onStatus={ignoreProviderStatus} />

      <div className="grid gap-5 xl:grid-cols-2">
        <UpdateCard
          icon={Settings2}
          title={t("settings.application.title")}
          description={t("settings.application.description")}
        >
          <VersionRows
            current={application?.currentVersion}
            latest={application?.latestVersion}
          />
          <p className="text-sm text-[var(--text-muted)]">
            {!application
              ? t("settings.notChecked")
              : application.available
                ? t("settings.updateAvailable")
                : t("settings.upToDate")}
          </p>
          {application?.available ? (
            <>
              {!isDesktopRuntime() ? (
                <p className="rounded-xl bg-[var(--surface-muted)] p-3 text-sm text-[var(--text-muted)]">
                  {t("settings.application.desktopOnly")}
                </p>
              ) : null}
              <Confirmation
                checked={confirmApp}
                onChange={setConfirmApp}
                label={t("settings.application.confirm")}
              />
              <button
                type="button"
                disabled={
                  !confirmApp ||
                  !application.installable ||
                  !isDesktopRuntime() ||
                  busy !== null
                }
                onClick={() => void updateApplication()}
                className="inline-flex items-center gap-2 rounded-xl border border-[var(--border-strong)] px-4 py-2.5 text-sm font-semibold disabled:opacity-50"
              >
                <Download className="size-4" aria-hidden="true" />
                {t("settings.application.install")}
              </button>
              {appProgress ? (
                <Progress
                  value={appProgress.downloadedBytes}
                  total={appProgress.totalBytes}
                  locale={locale}
                />
              ) : null}
            </>
          ) : null}
        </UpdateCard>

        <UpdateCard
          icon={ShieldCheck}
          title={t("settings.sandbox.title")}
          description={t("settings.sandbox.description")}
        >
          <VersionRows current={sandbox?.currentVersion} latest={sandbox?.latestVersion} />
          {sandbox ? (
            <dl className="grid gap-2 text-sm">
              <InfoRow label={t("settings.sandbox.size")} value={formatBytes(sandbox.sizeBytes, locale)} />
              <InfoRow
                label={t("settings.sandbox.compatibility")}
                value={
                  sandbox.compatible
                    ? t("settings.sandbox.compatible")
                    : t("settings.sandbox.incompatible")
                }
              />
            </dl>
          ) : (
            <p className="text-sm text-[var(--text-muted)]">{t("settings.notChecked")}</p>
          )}
          {sandbox?.available && sandbox.compatible ? (
            <>
              <Confirmation
                checked={confirmSandbox}
                onChange={setConfirmSandbox}
                label={t("settings.sandbox.confirm")}
              />
              <button
                type="button"
                disabled={!confirmSandbox || busy !== null || pull?.state === "downloading"}
                onClick={() => void updateSandbox()}
                className="inline-flex items-center gap-2 rounded-xl border border-[var(--border-strong)] px-4 py-2.5 text-sm font-semibold disabled:opacity-50"
              >
                <Download className="size-4" aria-hidden="true" />
                {t("settings.sandbox.pull")}
              </button>
            </>
          ) : null}
          {pull && pull.state !== "idle" ? (
            <div aria-live="polite">
              <p className="mb-2 text-sm text-[var(--text-muted)]">
                {t(`settings.sandbox.state.${pull.state}`)}
              </p>
              <Progress
                value={pull.downloadedBytes}
                total={pull.totalBytes}
                locale={locale}
              />
            </div>
          ) : null}
          <p className="text-xs leading-5 text-[var(--text-muted)]">
            {t("settings.sandbox.retention")}
          </p>
        </UpdateCard>
      </div>

      {error ? (
        <p role="alert" className="rounded-xl border border-[var(--danger)] p-3 text-sm text-[var(--danger)]">
          {t("settings.error")}
        </p>
      ) : null}
    </section>
  );
}

function ignoreProviderStatus() {}

function UpdateCard({
  icon: Icon,
  title,
  description,
  children,
}: {
  icon: typeof Settings2;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <article className="space-y-5 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6">
      <div className="flex gap-3">
        <Icon className="mt-0.5 size-5 text-[var(--accent)]" aria-hidden="true" />
        <div>
          <h2 className="font-semibold">{title}</h2>
          <p className="mt-1 text-sm leading-6 text-[var(--text-muted)]">{description}</p>
        </div>
      </div>
      {children}
    </article>
  );
}

function VersionRows({ current, latest }: { current?: string | null; latest?: string | null }) {
  const { t } = useLocale();
  return (
    <dl className="grid grid-cols-2 gap-3">
      <InfoRow label={t("settings.currentVersion")} value={current ?? "—"} />
      <InfoRow label={t("settings.latestVersion")} value={latest ?? "—"} />
    </dl>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-[var(--text-muted)]">{label}</dt>
      <dd className="mt-1 break-all text-sm font-medium">{value}</dd>
    </div>
  );
}

function Confirmation({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
}) {
  return (
    <label className="flex items-start gap-3 rounded-xl bg-[var(--surface-muted)] p-3 text-sm leading-5">
      <input
        type="checkbox"
        className="mt-1"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      {label}
    </label>
  );
}

function Progress({ value, total, locale }: { value: number; total: number; locale: string }) {
  const maximum = Math.max(total, 1);
  return (
    <div>
      <progress className="h-2 w-full accent-[var(--accent)]" max={maximum} value={value} />
      <p className="mt-1 text-xs text-[var(--text-muted)]">
        {formatBytes(value, locale)} / {formatBytes(total, locale)}
      </p>
    </div>
  );
}

function formatBytes(value: number, locale: string): string {
  if (value <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(
    value / 1024 ** index,
  )} ${units[index]}`;
}
