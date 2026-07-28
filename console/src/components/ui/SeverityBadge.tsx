import type { FindingSeverity } from "../../features/findings/contracts";
import type { MessageKey } from "../../shared/i18n/messages";
import { useLocale } from "../../shared/i18n/useLocale";

const tones: Record<FindingSeverity, string> = {
  critical: "bg-red-500/12 text-[var(--danger)]",
  high: "bg-orange-500/12 text-orange-500",
  medium: "bg-amber-500/12 text-[var(--warning)]",
  low: "bg-emerald-500/12 text-[var(--accent)]",
};

export function SeverityBadge({ severity }: { severity: FindingSeverity }) {
  const { t } = useLocale();
  return (
    <span
      className={`inline-flex rounded-md px-2 py-1 text-[11px] font-semibold ${tones[severity]}`}
    >
      {t(`findings.severity.${severity}` as MessageKey)}
    </span>
  );
}
