import type { RunState } from "../../features/local-runs/contracts";
import type { MessageKey } from "../../shared/i18n/messages";
import { useLocale } from "../../shared/i18n/useLocale";

const stateKeys: Record<RunState, MessageKey> = {
  active: "localRuns.state.active",
  completed: "localRuns.state.completed",
  interrupted: "localRuns.state.interrupted",
  partial: "localRuns.state.partial",
  malformed: "localRuns.state.malformed",
};

export function RunStateBadge({ state }: { state: RunState }) {
  const { t } = useLocale();
  const tone =
    state === "completed"
      ? "bg-[var(--accent-soft)] text-[var(--accent-strong)]"
      : state === "active"
        ? "bg-sky-500/10 text-sky-500"
        : state === "malformed"
          ? "bg-red-500/10 text-[var(--danger)]"
          : "bg-amber-500/10 text-[var(--warning)]";
  return (
    <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${tone}`}>
      {t(stateKeys[state])}
    </span>
  );
}
