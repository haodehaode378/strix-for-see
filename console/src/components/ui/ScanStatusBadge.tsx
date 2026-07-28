import type { ScanStatus } from "../../features/scan-control/contracts";
import type { MessageKey } from "../../shared/i18n/messages";
import { useLocale } from "../../shared/i18n/useLocale";

const statusKeys: Record<ScanStatus, MessageKey> = {
  validating: "scan.status.validating",
  queued: "scan.status.queued",
  preparing: "scan.status.preparing",
  running: "scan.status.running",
  reporting: "scan.status.reporting",
  completed: "scan.status.completed",
  stopping: "scan.status.stopping",
  stopped: "scan.status.stopped",
  terminating: "scan.status.terminating",
  terminated: "scan.status.terminated",
  failed: "scan.status.failed",
};

export function ScanStatusBadge({ status }: { status: ScanStatus }) {
  const { t } = useLocale();
  const tone =
    status === "completed"
      ? "bg-[var(--accent-soft)] text-[var(--accent-strong)]"
      : status === "running" || status === "reporting"
        ? "bg-sky-500/10 text-sky-500"
        : status === "failed" || status === "terminated"
          ? "bg-red-500/10 text-[var(--danger)]"
          : "bg-amber-500/10 text-[var(--warning)]";
  return (
    <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${tone}`}>
      {t(statusKeys[status])}
    </span>
  );
}
