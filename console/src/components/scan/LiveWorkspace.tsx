import {
  Activity,
  Bot,
  Boxes,
  CircleDot,
  FileText,
  Gauge,
  Send,
  ShieldCheck,
  Wrench,
} from "lucide-react";
import { FormEvent, useMemo, useState } from "react";

import type {
  LiveConnectionState,
  Scan,
  ScanEvent,
} from "../../features/scan-control/contracts";
import { steerScan } from "../../features/scan-control/scanClient";
import type { MessageKey } from "../../shared/i18n/messages";
import { useLocale } from "../../shared/i18n/useLocale";
import { NavigationLink } from "../../shared/navigation/NavigationLink";

type Tab =
  | "overview"
  | "agents"
  | "activity"
  | "tools"
  | "findings"
  | "runtime"
  | "report";

const tabs: Array<{ id: Tab; icon: typeof Activity }> = [
  { id: "overview", icon: Gauge },
  { id: "agents", icon: Bot },
  { id: "activity", icon: Activity },
  { id: "tools", icon: Wrench },
  { id: "findings", icon: ShieldCheck },
  { id: "runtime", icon: Boxes },
  { id: "report", icon: FileText },
];

export function LiveWorkspace({
  scan,
  events,
  connection,
}: {
  scan: Scan;
  events: ScanEvent[];
  connection: LiveConnectionState;
}) {
  const { t } = useLocale();
  const [tab, setTab] = useState<Tab>("overview");
  const [message, setMessage] = useState("");
  const [steeringState, setSteeringState] = useState<
    "idle" | "sending" | "accepted" | "error"
  >("idle");
  const agents = useMemo(() => latestAgents(events), [events]);
  const toolEvents = events.filter((event) => event.type.startsWith("tool."));
  const findings = events.filter((event) => event.type === "finding.created");
  const usage = [...events]
    .reverse()
    .find((event) => event.type === "usage.updated")?.payload;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!message.trim()) return;
    setSteeringState("sending");
    try {
      await steerScan(scan.id, message.trim());
      setMessage("");
      setSteeringState("accepted");
    } catch {
      setSteeringState("error");
    }
  };

  return (
    <section className="mt-7 overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)]">
      <div className="flex flex-col gap-4 border-b border-[var(--border)] p-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-[var(--text)]">
            {t("live.title")}
          </h2>
          <p className="mt-1 text-xs text-[var(--text-muted)]">
            {t("live.description")}
          </p>
        </div>
        <ConnectionState state={connection} />
      </div>

      <div className="overflow-x-auto border-b border-[var(--border)]">
        <div className="flex min-w-max gap-1 p-2" role="tablist">
          {tabs.map(({ id, icon: Icon }) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              onClick={() => setTab(id)}
              className={`inline-flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-semibold transition active:scale-[0.98] ${
                tab === id
                  ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                  : "text-[var(--text-muted)] hover:text-[var(--text)]"
              }`}
            >
              <Icon className="size-4" />
              {t(`live.tab.${id}` as MessageKey)}
            </button>
          ))}
        </div>
      </div>

      <div className="min-h-72 p-5">
        {tab === "overview" ? (
          <Overview
            scan={scan}
            events={events}
            agentCount={agents.length}
            toolCount={toolEvents.length}
            findingCount={findings.length}
            usage={usage}
          />
        ) : null}
        {tab === "agents" ? <Agents agents={agents} /> : null}
        {tab === "activity" ? <EventList events={events} /> : null}
        {tab === "tools" ? <EventList events={toolEvents} /> : null}
        {tab === "findings" ? (
          <ScanFindings
            events={findings}
            runName={scan.engineRunName}
          />
        ) : null}
        {tab === "runtime" ? <Runtime scan={scan} events={events} /> : null}
        {tab === "report" ? <ScanReport runName={scan.engineRunName} /> : null}
      </div>

      {scan.status === "running" ? (
        <form
          onSubmit={submit}
          className="border-t border-[var(--border)] bg-[var(--surface-raised)] p-4"
        >
          <label
            htmlFor="steering-message"
            className="text-xs font-semibold text-[var(--text)]"
          >
            {t("live.steering")}
          </label>
          <div className="mt-2 flex flex-col gap-2 sm:flex-row">
            <input
              id="steering-message"
              value={message}
              onChange={(event) => {
                setMessage(event.target.value);
                setSteeringState("idle");
              }}
              maxLength={2000}
              placeholder={t("live.steeringPlaceholder")}
              className="min-w-0 flex-1 rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2.5 text-sm text-[var(--text)] outline-none focus:border-[var(--accent)]"
            />
            <button
              type="submit"
              disabled={!message.trim() || steeringState === "sending"}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-[var(--accent)] px-4 py-2.5 text-sm font-semibold text-white transition active:scale-[0.98] disabled:opacity-50"
            >
              <Send className="size-4" />
              {t("live.send")}
            </button>
          </div>
          <p
            className={`mt-2 text-xs ${
              steeringState === "error"
                ? "text-[var(--danger)]"
                : "text-[var(--text-muted)]"
            }`}
            aria-live="polite"
          >
            {steeringState === "accepted"
              ? t("live.steeringAccepted")
              : steeringState === "error"
                ? t("live.steeringError")
                : t("live.steeringHint")}
          </p>
        </form>
      ) : null}
    </section>
  );
}

function ScanFindings({
  events,
  runName,
}: {
  events: ScanEvent[];
  runName: string;
}) {
  const { t } = useLocale();
  return (
    <div>
      <EventList events={events} />
      <NavigationLink
        to={`/findings/run/${encodeURIComponent(runName)}`}
        className="mt-5 inline-flex rounded-xl bg-[var(--accent)] px-4 py-2.5 text-sm font-semibold text-white transition active:scale-[0.98]"
      >
        {t("live.findings.open")}
      </NavigationLink>
    </div>
  );
}

function ScanReport({ runName }: { runName: string }) {
  const { t } = useLocale();
  return (
    <div className="grid min-h-56 place-items-center text-center">
      <div className="max-w-md">
        <FileText className="mx-auto size-7 text-[var(--accent)]" />
        <h3 className="mt-3 text-sm font-semibold">{t("live.report.title")}</h3>
        <p className="mt-2 text-xs leading-5 text-[var(--text-muted)]">
          {t("live.report.description")}
        </p>
        <NavigationLink
          to={`/findings/run/${encodeURIComponent(runName)}`}
          className="mt-5 inline-flex rounded-xl bg-[var(--accent)] px-4 py-2.5 text-sm font-semibold text-white transition active:scale-[0.98]"
        >
          {t("live.report.open")}
        </NavigationLink>
      </div>
    </div>
  );
}

function ConnectionState({ state }: { state: LiveConnectionState }) {
  const { t } = useLocale();
  return (
    <span
      className="inline-flex items-center gap-2 text-xs font-semibold text-[var(--text-muted)]"
      aria-live="polite"
    >
      <CircleDot
        className={`size-4 ${state === "live" ? "text-[var(--success)]" : "text-[var(--warning)]"}`}
      />
      {t(`live.connection.${state}`)}
    </span>
  );
}

function Overview({
  scan,
  events,
  agentCount,
  toolCount,
  findingCount,
  usage,
}: {
  scan: Scan;
  events: ScanEvent[];
  agentCount: number;
  toolCount: number;
  findingCount: number;
  usage: Record<string, unknown> | undefined;
}) {
  const { t } = useLocale();
  const metrics = [
    [t("live.metric.phase"), t(`scan.status.${scan.status}` as MessageKey)],
    [t("live.metric.agents"), String(agentCount)],
    [t("live.metric.tools"), String(toolCount)],
    [t("live.metric.findings"), String(findingCount)],
  ];
  return (
    <div>
      <dl className="grid gap-px overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--border)] sm:grid-cols-2 lg:grid-cols-4">
        {metrics.map(([label, value]) => (
          <div key={label} className="bg-[var(--surface)] p-4">
            <dt className="text-xs text-[var(--text-muted)]">{label}</dt>
            <dd className="mt-2 text-xl font-semibold text-[var(--text)]">{value}</dd>
          </div>
        ))}
      </dl>
      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
            {t("live.latestActivity")}
          </h3>
          <EventList events={events.slice(-5)} compact />
        </div>
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
            {t("live.usage")}
          </h3>
          <pre className="mt-3 max-h-52 overflow-auto whitespace-pre-wrap rounded-xl bg-[var(--surface-raised)] p-3 text-xs leading-5 text-[var(--text-muted)]">
            {usage ? JSON.stringify(usage, null, 2) : t("live.noUsage")}
          </pre>
        </div>
      </div>
    </div>
  );
}

type AgentView = {
  id: string;
  name: string;
  parentId: string | null;
  status: string;
  task: string;
};

function latestAgents(events: ScanEvent[]): AgentView[] {
  const agents = new Map<string, AgentView>();
  for (const event of events) {
    if (event.type !== "agent.updated") continue;
    const id = String(event.payload.id ?? event.actor?.id ?? "");
    if (!id) continue;
    agents.set(id, {
      id,
      name: String(event.payload.name ?? id),
      parentId: event.payload.parentId ? String(event.payload.parentId) : null,
      status: String(event.payload.status ?? "unknown"),
      task: String(event.payload.task ?? ""),
    });
  }
  return [...agents.values()];
}

function Agents({ agents }: { agents: AgentView[] }) {
  const { t } = useLocale();
  if (!agents.length) return <Empty text={t("live.emptyAgents")} />;
  return (
    <div className="divide-y divide-[var(--border)]">
      {agents.map((agent) => (
        <div
          key={agent.id}
          className="grid gap-2 py-4 sm:grid-cols-[minmax(0,1fr)_120px]"
        >
          <div className={agent.parentId ? "pl-6" : ""}>
            <p className="text-sm font-semibold text-[var(--text)]">{agent.name}</p>
            <p className="mt-1 truncate text-xs text-[var(--text-muted)]">
              {agent.task || agent.id}
            </p>
          </div>
          <span className="text-xs font-semibold text-[var(--accent)]">
            {agent.status}
          </span>
        </div>
      ))}
    </div>
  );
}

function EventList({
  events,
  compact = false,
}: {
  events: ScanEvent[];
  compact?: boolean;
}) {
  const { locale, t } = useLocale();
  if (!events.length) return <Empty text={t("live.emptyEvents")} />;
  return (
    <div className={compact ? "mt-3 divide-y divide-[var(--border)]" : "divide-y divide-[var(--border)]"}>
      {[...events].reverse().map((event) => (
        <article key={event.eventId} className="grid gap-1 py-3 sm:grid-cols-[150px_1fr]">
          <time className="text-xs text-[var(--text-muted)]">
            {new Intl.DateTimeFormat(locale, {
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            }).format(new Date(event.occurredAt))}
          </time>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-[var(--text)]">{event.type}</p>
            <p className="mt-1 line-clamp-2 break-all text-xs text-[var(--text-muted)]">
              {eventSummary(event)}
            </p>
          </div>
        </article>
      ))}
    </div>
  );
}

function Runtime({ scan, events }: { scan: Scan; events: ScanEvent[] }) {
  const { t } = useLocale();
  const [notificationPermission, setNotificationPermission] = useState(
    typeof Notification === "undefined" ? "unsupported" : Notification.permission,
  );
  const runtime = [...events]
    .reverse()
    .find((event) => event.type === "runtime.updated")?.payload;
  return (
    <dl className="divide-y divide-[var(--border)]">
      <Row label={t("live.runtime.process")} value={scan.processId?.toString() ?? "—"} />
      <Row label={t("live.runtime.run")} value={scan.engineRunName} />
      <Row
        label={t("live.runtime.health")}
        value={runtime ? JSON.stringify(runtime) : t("live.runtime.pending")}
      />
      {notificationPermission === "default" ? (
        <div className="py-4">
          <button
            type="button"
            onClick={() => {
              void Notification.requestPermission().then(setNotificationPermission);
            }}
            className="rounded-xl border border-[var(--border)] px-4 py-2.5 text-sm font-semibold text-[var(--text)] transition active:scale-[0.98]"
          >
            {t("live.notifications.enable")}
          </button>
          <p className="mt-2 text-xs text-[var(--text-muted)]">
            {t("live.notifications.hint")}
          </p>
        </div>
      ) : null}
    </dl>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1 py-3 sm:grid-cols-[160px_1fr]">
      <dt className="text-xs text-[var(--text-muted)]">{label}</dt>
      <dd className="break-all text-sm text-[var(--text)]">{value}</dd>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return (
    <div className="grid min-h-48 place-items-center text-center text-sm text-[var(--text-muted)]">
      {text}
    </div>
  );
}

function eventSummary(event: ScanEvent) {
  if (typeof event.payload.content === "string") return event.payload.content;
  if (typeof event.payload.toolName === "string") return event.payload.toolName;
  if (typeof event.payload.title === "string") return event.payload.title;
  if (typeof event.payload.status === "string") return event.payload.status;
  return Object.keys(event.payload).join(", ");
}
