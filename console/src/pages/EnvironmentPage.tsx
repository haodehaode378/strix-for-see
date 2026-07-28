import {
  CheckCircle2,
  CircleAlert,
  Clipboard,
  RefreshCw,
  XCircle,
} from "lucide-react";
import { useState } from "react";

import { PageHeader } from "../components/ui/PageHeader";
import type {
  CheckStatus,
  SystemCheck,
} from "../features/system-readiness/contracts";
import { getDiagnostics } from "../features/system-readiness/systemClient";
import { useSystemReadiness } from "../features/system-readiness/useSystemReadiness";
import type { MessageKey } from "../shared/i18n/messages";
import { useLocale } from "../shared/i18n/useLocale";

const checkLabels: Record<string, MessageKey> = {
  windows: "environment.check.windows",
  controlService: "environment.check.controlService",
  storage: "environment.check.storage",
  disk: "environment.check.disk",
  strix: "environment.check.strix",
  dockerCli: "environment.check.dockerCli",
  dockerDaemon: "environment.check.dockerDaemon",
  wsl: "environment.check.wsl",
  git: "environment.check.git",
  sandbox: "environment.check.sandbox",
  provider: "environment.check.provider",
};

const issueLabels: Record<string, MessageKey> = {
  unsupportedPlatform: "environment.issue.unsupportedPlatform",
  notWritable: "environment.issue.notWritable",
  unavailable: "environment.issue.unavailable",
  lowDiskSpace: "environment.issue.lowDiskSpace",
  notBundled: "environment.issue.notBundled",
  notInstalled: "environment.issue.notInstalled",
  dockerCliMissing: "environment.issue.dockerCliMissing",
  notRunning: "environment.issue.notRunning",
  statusUnavailable: "environment.issue.statusUnavailable",
  commandFailed: "environment.issue.commandFailed",
  dockerUnavailable: "environment.issue.dockerUnavailable",
  imageMissing: "environment.issue.imageMissing",
  notConfigured: "environment.issue.notConfigured",
};

const statusLabels: Record<CheckStatus, MessageKey> = {
  ready: "environment.status.ready",
  warning: "environment.status.warning",
  missing: "environment.status.missing",
  error: "environment.status.error",
};

export function EnvironmentPage({ setup = false }: { setup?: boolean }) {
  const { t } = useLocale();
  const { state, report, retry, recheck } = useSystemReadiness();
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");

  const copyDiagnostics = async () => {
    try {
      const diagnostics = await getDiagnostics();
      await navigator.clipboard.writeText(JSON.stringify(diagnostics, null, 2));
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
  };

  return (
    <div>
      <PageHeader
        eyebrow={t(setup ? "setup.eyebrow" : "environment.eyebrow")}
        title={t(setup ? "setup.title" : "environment.title")}
        description={t(setup ? "setup.description" : "environment.description")}
        actions={
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void copyDiagnostics()}
              className="inline-flex items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-2.5 text-sm font-semibold text-[var(--text-muted)] transition hover:border-[var(--border-strong)] hover:text-[var(--text)]"
            >
              <Clipboard className="size-4" />
              {t("environment.copyDiagnostics")}
            </button>
            <button
              type="button"
              onClick={() => void recheck()}
              disabled={state === "loading"}
              className="inline-flex items-center gap-2 rounded-xl bg-[var(--accent)] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[var(--accent-strong)] disabled:cursor-wait disabled:opacity-60"
            >
              <RefreshCw
                className={`size-4 ${state === "loading" ? "animate-spin" : ""}`}
              />
              {t("environment.recheck")}
            </button>
          </div>
        }
      />

      <p className="sr-only" aria-live="polite">
        {copyState === "copied"
          ? t("environment.diagnosticsCopied")
          : copyState === "failed"
            ? t("environment.diagnosticsFailed")
            : ""}
      </p>

      {state === "loading" && !report ? <LoadingPanel /> : null}
      {state === "error" && !report ? (
        <ErrorPanel onRetry={retry} message={t("environment.loadFailed")} />
      ) : null}
      {report ? (
        <div className="mt-7 space-y-6">
          <section
            className={`rounded-2xl border p-5 ${
              report.summary.ready
                ? "border-[color-mix(in_srgb,var(--accent)_45%,var(--border))] bg-[var(--accent-soft)]"
                : "border-[color-mix(in_srgb,var(--warning)_45%,var(--border))] bg-[var(--surface)]"
            }`}
          >
            <div className="flex items-start gap-4">
              {report.summary.ready ? (
                <CheckCircle2 className="mt-0.5 size-6 shrink-0 text-[var(--accent)]" />
              ) : (
                <CircleAlert className="mt-0.5 size-6 shrink-0 text-[var(--warning)]" />
              )}
              <div>
                <h2 className="font-semibold text-[var(--text)]">
                  {t(
                    report.summary.ready
                      ? "environment.summaryReady"
                      : "environment.summaryNeedsAction",
                  )}
                </h2>
                <p className="mt-1 text-sm leading-6 text-[var(--text-muted)]">
                  {report.summary.requiredReady}/{report.summary.requiredTotal}{" "}
                  {t("environment.requiredReady")}
                  {report.summary.optionalWarnings > 0
                    ? ` · ${report.summary.optionalWarnings} ${t("environment.optionalWarnings")}`
                    : ""}
                </p>
              </div>
            </div>
          </section>

          <CheckGroup
            title={t("environment.required")}
            description={t("environment.requiredHint")}
            checks={report.checks.filter((check) => check.requirement === "required")}
          />
          <CheckGroup
            title={t("environment.optional")}
            description={t("environment.optionalHint")}
            checks={report.checks.filter((check) => check.requirement === "optional")}
          />
        </div>
      ) : null}
    </div>
  );
}

function CheckGroup({
  title,
  description,
  checks,
}: {
  title: string;
  description: string;
  checks: SystemCheck[];
}) {
  const { t } = useLocale();
  return (
    <section>
      <div className="mb-3">
        <h2 className="text-sm font-semibold text-[var(--text)]">{title}</h2>
        <p className="mt-1 text-xs text-[var(--text-muted)]">{description}</p>
      </div>
      <div className="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)]">
        {checks.map((check) => {
          const Icon = check.status === "ready" ? CheckCircle2 : check.status === "error" ? XCircle : CircleAlert;
          return (
            <div
              key={check.id}
              className="grid gap-3 border-b border-[var(--border)] px-4 py-4 last:border-b-0 sm:grid-cols-[1fr_auto] sm:items-center"
            >
              <div className="flex min-w-0 items-start gap-3">
                <Icon
                  className={`mt-0.5 size-5 shrink-0 ${
                    check.status === "ready"
                      ? "text-[var(--accent)]"
                      : check.status === "error" || check.status === "missing"
                        ? "text-[var(--danger)]"
                        : "text-[var(--warning)]"
                  }`}
                />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-[var(--text)]">
                    {t(checkLabels[check.id] ?? "common.unknown")}
                  </p>
                  {check.issue ? (
                    <p className="mt-1 text-xs leading-5 text-[var(--text-muted)]">
                      {t(issueLabels[check.issue] ?? "environment.issue.unavailable")}
                    </p>
                  ) : null}
                </div>
              </div>
              <div className="flex items-center gap-3 pl-8 sm:pl-0">
                {check.value ? (
                  <span className="max-w-72 truncate font-mono text-xs text-[var(--text-muted)]">
                    {check.value}
                  </span>
                ) : null}
                <span className="rounded-full border border-[var(--border)] px-2.5 py-1 text-[11px] font-semibold text-[var(--text-muted)]">
                  {t(statusLabels[check.status])}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function LoadingPanel() {
  return (
    <div className="mt-7 space-y-3" aria-busy="true">
      {[0, 1, 2].map((item) => (
        <div
          key={item}
          className="h-20 animate-pulse rounded-2xl border border-[var(--border)] bg-[var(--surface)]"
        />
      ))}
    </div>
  );
}

function ErrorPanel({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  const { t } = useLocale();
  return (
    <div className="mt-7 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6">
      <p className="text-sm text-[var(--text-muted)]">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-4 rounded-xl bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white"
      >
        {t("common.retry")}
      </button>
    </div>
  );
}
