import { RefreshCw } from "lucide-react";

import { PageHeader } from "../components/ui/PageHeader";
import { ServiceConnectionPanel } from "../components/ui/ServiceConnectionPanel";
import { useLocale } from "../shared/i18n/useLocale";

export function EnvironmentPage() {
  const { t } = useLocale();

  return (
    <div>
      <PageHeader
        eyebrow={t("environment.eyebrow")}
        title={t("environment.title")}
        description={t("environment.description")}
        actions={
          <button
            type="button"
            disabled
            className="inline-flex cursor-not-allowed items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-2.5 text-sm font-semibold text-[var(--text-muted)] opacity-60"
          >
            <RefreshCw className="size-4" />
            {t("environment.recheck")}
          </button>
        }
      />
      <div className="mt-7 max-w-2xl">
        <ServiceConnectionPanel />
        <p className="mt-4 text-xs leading-5 text-[var(--text-muted)]">
          {t("environment.phaseNotice")}
        </p>
      </div>
    </div>
  );
}
