import type { LucideIcon } from "lucide-react";

import { PageHeader } from "../components/ui/PageHeader";
import { useLocale } from "../shared/i18n/useLocale";

interface EmptySectionPageProps {
  title: string;
  description: string;
  icon: LucideIcon;
}

export function EmptySectionPage({ title, description, icon: Icon }: EmptySectionPageProps) {
  const { t } = useLocale();

  return (
    <div>
      <PageHeader eyebrow={t("app.phaseOne")} title={title} description={description} />
      <div className="mt-7 grid min-h-72 place-items-center border-y border-[var(--border)] py-12 text-center">
        <div>
          <Icon className="mx-auto size-6 text-[var(--text-muted)]" strokeWidth={1.6} />
          <p className="mt-4 text-sm font-medium">{t("common.notAvailable")}</p>
          <p className="mt-2 max-w-md text-sm leading-6 text-[var(--text-muted)]">
            {t("common.noFakeData")}
          </p>
        </div>
      </div>
    </div>
  );
}
