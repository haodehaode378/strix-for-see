import { FileSearch } from "lucide-react";
import { useEffect, useMemo } from "react";

import { useLocalRuns } from "../features/local-runs/useLocalRuns";
import { useLocale } from "../shared/i18n/useLocale";
import { NavigationLink } from "../shared/navigation/NavigationLink";
import { useNavigation } from "../shared/navigation/useNavigation";

export function LegacyRunFindingsPage({ runName }: { runName: string }) {
  const { t } = useLocale();
  const { navigate } = useNavigation();
  const { data, state } = useLocalRuns();
  const matches = useMemo(
    () => data?.runs.filter((run) => run.name === runName) ?? [],
    [data, runName],
  );

  useEffect(() => {
    if (matches.length === 1) {
      navigate(`/findings/task/${encodeURIComponent(matches[0].id)}`);
    }
  }, [matches, navigate]);

  if (state === "loading" || matches.length === 1) {
    return (
      <div
        className="h-40 animate-pulse rounded-2xl border border-[var(--border)] bg-[var(--surface)]"
        aria-busy="true"
      />
    );
  }

  return (
    <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6">
      <FileSearch className="size-7 text-[var(--accent)]" />
      <h1 className="mt-4 text-xl font-semibold">{t("findings.legacy.title")}</h1>
      <p className="mt-2 text-sm text-[var(--text-muted)]">
        {state === "error"
          ? t("findings.loadFailed")
          : matches.length
            ? t("findings.legacy.duplicate")
            : t("findings.legacy.notFound")}
      </p>
      {matches.length > 1 ? (
        <div className="mt-5 grid gap-3">
          {matches.map((run) => (
            <NavigationLink
              key={run.id}
              to={`/findings/task/${encodeURIComponent(run.id)}`}
              className="rounded-xl border border-[var(--border)] bg-[var(--surface-muted)] p-4 transition hover:border-[var(--border-strong)] active:scale-[0.99]"
            >
              <span className="block font-semibold">{run.name}</span>
              <span className="mt-1 block truncate font-mono text-xs text-[var(--text-muted)]">
                {run.path}
              </span>
            </NavigationLink>
          ))}
        </div>
      ) : null}
    </section>
  );
}
