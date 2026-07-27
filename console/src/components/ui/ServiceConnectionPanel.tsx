import { AlertCircle, CheckCircle2, LoaderCircle } from "lucide-react";

import { useServiceHealth } from "../../features/service-health/useServiceHealth";
import { useLocale } from "../../shared/i18n/useLocale";
import { StatusIndicator } from "./StatusIndicator";

export function ServiceConnectionPanel() {
  const { t } = useLocale();
  const { state, health, retry } = useServiceHealth();

  if (state === "loading") {
    return (
      <div
        className="mt-4 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5"
        aria-live="polite"
      >
        <div className="flex items-center gap-3">
          <LoaderCircle className="size-5 animate-spin text-[var(--warning)]" />
          <div>
            <p className="text-sm font-semibold">{t("service.checking")}</p>
            <p className="mt-1 text-xs text-[var(--text-muted)]">{t("service.checkingHint")}</p>
          </div>
        </div>
      </div>
    );
  }

  if (state === "connected" && health) {
    return (
      <div
        className="mt-4 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5"
        aria-live="polite"
      >
        <div className="flex items-start justify-between gap-4">
          <CheckCircle2 className="mt-0.5 size-5 text-[var(--accent)]" />
          <StatusIndicator tone="success" label={t("service.connected")} />
        </div>
        <dl className="mt-6 grid grid-cols-2 gap-4 border-t border-[var(--border)] pt-4 text-xs">
          <div>
            <dt className="text-[var(--text-muted)]">{t("service.version")}</dt>
            <dd className="mt-1 font-semibold">{health.serviceVersion}</dd>
          </div>
          <div>
            <dt className="text-[var(--text-muted)]">{t("service.schema")}</dt>
            <dd className="mt-1 font-semibold">{health.schemaVersion}</dd>
          </div>
        </dl>
      </div>
    );
  }

  return (
    <div
      className="mt-4 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5"
      role="alert"
    >
      <div className="flex items-start gap-3">
        <AlertCircle className="mt-0.5 size-5 shrink-0 text-[var(--danger)]" />
        <div>
          <p className="text-sm font-semibold">{t("service.unavailable")}</p>
          <p className="mt-1 text-xs leading-5 text-[var(--text-muted)]">
            {t("service.unavailableHint")}
          </p>
          <button
            type="button"
            onClick={retry}
            className="mt-4 rounded-lg border border-[var(--border-strong)] px-3 py-2 text-xs font-semibold transition hover:bg-[var(--surface-muted)] active:scale-[0.98]"
          >
            {t("service.retry")}
          </button>
        </div>
      </div>
    </div>
  );
}
