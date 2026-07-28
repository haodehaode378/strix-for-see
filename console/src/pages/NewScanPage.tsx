import {
  ArrowLeft,
  ArrowRight,
  Check,
  CircleAlert,
  FolderCode,
  Globe2,
  Network,
  Play,
  ShieldCheck,
  Waypoints,
} from "lucide-react";
import { useMemo, useRef, useState } from "react";

import {
  Field,
  inputClass,
  ProviderPanel,
} from "../components/scan/ProviderPanel";
import { PageHeader } from "../components/ui/PageHeader";
import type {
  CreateScanRequest,
  ProviderStatus,
  RiskMode,
  ScanProfile,
  TargetType,
} from "../features/scan-control/contracts";
import { createScan } from "../features/scan-control/scanClient";
import { useSystemReadiness } from "../features/system-readiness/useSystemReadiness";
import { ControlServiceError } from "../shared/api/controlServiceClient";
import type { MessageKey } from "../shared/i18n/messages";
import { useLocale } from "../shared/i18n/useLocale";
import { useNavigation } from "../shared/navigation/useNavigation";

const steps: MessageKey[] = [
  "newScan.step.target",
  "newScan.step.scope",
  "newScan.step.options",
  "newScan.step.provider",
  "newScan.step.review",
];

const targetTypes: Array<{
  value: TargetType;
  label: MessageKey;
  hint: MessageKey;
  icon: typeof Globe2;
}> = [
  {
    value: "web",
    label: "newScan.target.web",
    hint: "newScan.target.webHint",
    icon: Globe2,
  },
  {
    value: "local",
    label: "newScan.target.local",
    hint: "newScan.target.localHint",
    icon: FolderCode,
  },
  {
    value: "repository",
    label: "newScan.target.repository",
    hint: "newScan.target.repositoryHint",
    icon: Waypoints,
  },
  {
    value: "network",
    label: "newScan.target.network",
    hint: "newScan.target.networkHint",
    icon: Network,
  },
];

const submitErrors: Record<string, MessageKey> = {
  environmentNotReady: "newScan.error.environmentNotReady",
  providerNotConfigured: "newScan.error.providerNotConfigured",
  providerConnectivityNotVerified: "newScan.error.providerConnectivityNotVerified",
  authorizationRequired: "newScan.error.authorizationRequired",
  fullModeConfirmationRequired: "newScan.error.fullModeConfirmationRequired",
  instructionsContainSecret: "newScan.error.instructionsContainSecret",
  invalidTargetScheme: "newScan.error.invalidTarget",
  invalidTargetUrl: "newScan.error.invalidTarget",
  localDirectoryNotFound: "newScan.error.localDirectory",
  localDirectoryTooBroad: "newScan.error.localDirectoryTooBroad",
  invalidNetworkTarget: "newScan.error.invalidTarget",
  repositoryMustBePublic: "newScan.error.publicRepository",
};

const initialRequest: CreateScanRequest = {
  targetType: "web",
  target: "",
  scope: {
    allowedHosts: [],
    allowedPorts: [],
    allowedPaths: [],
    exclusions: [],
  },
  options: {
    riskMode: "safe",
    scanProfile: "standard",
    requestRatePerMinute: 30,
    maxDurationMinutes: 60,
    maxBudgetUsd: 10,
    instructions: "",
  },
  authorizationConfirmed: false,
  fullModeConfirmed: false,
};

export function NewScanPage() {
  const { t } = useLocale();
  const { navigate } = useNavigation();
  const readiness = useSystemReadiness();
  const [step, setStep] = useState(0);
  const [request, setRequest] = useState<CreateScanRequest>(initialRequest);
  const [provider, setProvider] = useState<ProviderStatus | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<MessageKey | null>(null);
  const idempotencyKey = useRef(crypto.randomUUID());

  const canContinue = useMemo(() => {
    if (step === 0) return request.target.trim().length > 0;
    if (step === 3) {
      return provider?.configured === true && provider.connectionVerified;
    }
    if (step === 4) {
      return (
        request.authorizationConfirmed &&
        (request.options.riskMode === "safe" || request.fullModeConfirmed)
      );
    }
    return true;
  }, [provider, request, step]);

  const launch = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const scan = await createScan(request, idempotencyKey.current);
      navigate(`/scans/${scan.id}`);
    } catch (caught) {
      const code = caught instanceof ControlServiceError ? caught.code : "";
      setError(submitErrors[code] ?? "newScan.error.launchFailed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <PageHeader
        eyebrow={t("newScan.eyebrow")}
        title={t("newScan.title")}
        description={t("newScan.description")}
      />

      <ol className="nav-scroll mt-6 flex gap-2 overflow-x-auto pb-2" aria-label={t("newScan.progress")}>
        {steps.map((label, index) => (
          <li
            key={label}
            className={`flex shrink-0 items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold ${
              index === step
                ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent-strong)]"
                : index < step
                  ? "border-[var(--border)] text-[var(--accent)]"
                  : "border-[var(--border)] text-[var(--text-muted)]"
            }`}
          >
            {index < step ? <Check className="size-3.5" /> : <span>{index + 1}</span>}
            {t(label)}
          </li>
        ))}
      </ol>

      <div className="mt-6">
        {step === 0 ? (
          <TargetStep request={request} setRequest={setRequest} />
        ) : null}
        {step === 1 ? (
          <ScopeStep request={request} setRequest={setRequest} />
        ) : null}
        {step === 2 ? (
          <OptionsStep request={request} setRequest={setRequest} />
        ) : null}
        {step === 3 ? <ProviderPanel onStatus={setProvider} /> : null}
        {step === 4 ? (
          <ReviewStep
            request={request}
            setRequest={setRequest}
            provider={provider}
            environmentReady={readiness.report?.summary.ready === true}
          />
        ) : null}
      </div>

      {error ? (
        <p
          className="mt-4 flex items-center gap-2 text-sm text-[var(--danger)]"
          role="alert"
        >
          <CircleAlert className="size-4" />
          {t(error)}
        </p>
      ) : null}

      <div className="mt-7 flex items-center justify-between border-t border-[var(--border)] pt-5">
        <button
          type="button"
          onClick={() => setStep((value) => Math.max(0, value - 1))}
          disabled={step === 0 || submitting}
          className="inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold text-[var(--text-muted)] transition active:scale-[0.98] disabled:opacity-30"
        >
          <ArrowLeft className="size-4" />
          {t("common.back")}
        </button>
        {step < steps.length - 1 ? (
          <button
            type="button"
            onClick={() => setStep((value) => Math.min(steps.length - 1, value + 1))}
            disabled={!canContinue}
            className="inline-flex items-center gap-2 rounded-xl bg-[var(--accent)] px-4 py-2.5 text-sm font-semibold text-white transition active:scale-[0.98] disabled:opacity-40"
          >
            {t("common.continue")}
            <ArrowRight className="size-4" />
          </button>
        ) : (
          <button
            type="button"
            onClick={() => void launch()}
            disabled={!canContinue || submitting}
            className="inline-flex items-center gap-2 rounded-xl bg-[var(--accent)] px-5 py-2.5 text-sm font-semibold text-white transition active:scale-[0.98] disabled:opacity-40"
          >
            <Play className="size-4" />
            {submitting ? t("newScan.launching") : t("newScan.launch")}
          </button>
        )}
      </div>
    </div>
  );
}

function TargetStep({
  request,
  setRequest,
}: ScanStepProps) {
  const { t } = useLocale();
  const placeholder: Record<TargetType, MessageKey> = {
    web: "newScan.placeholder.web",
    local: "newScan.placeholder.local",
    repository: "newScan.placeholder.repository",
    network: "newScan.placeholder.network",
  };
  return (
    <section>
      <SectionIntro title={t("newScan.targetTitle")} description={t("newScan.targetDescription")} />
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {targetTypes.map((type) => {
          const Icon = type.icon;
          return (
            <button
              key={type.value}
              type="button"
              onClick={() =>
                setRequest((current) => ({
                  ...current,
                  targetType: type.value,
                  target: "",
                }))
              }
              className={`rounded-2xl border p-4 text-left transition active:scale-[0.98] ${
                request.targetType === type.value
                  ? "border-[var(--accent)] bg-[var(--accent-soft)]"
                  : "border-[var(--border)] bg-[var(--surface)] hover:border-[var(--border-strong)]"
              }`}
            >
              <Icon className="size-5 text-[var(--accent)]" />
              <span className="mt-3 block text-sm font-semibold text-[var(--text)]">
                {t(type.label)}
              </span>
              <span className="mt-1 block text-xs leading-5 text-[var(--text-muted)]">
                {t(type.hint)}
              </span>
            </button>
          );
        })}
      </div>
      <div className="mt-5">
        <Field label={t("newScan.primaryTarget")}>
          <input
            value={request.target}
            onChange={(event) =>
              setRequest((current) => ({ ...current, target: event.target.value }))
            }
            placeholder={t(placeholder[request.targetType])}
            className={inputClass}
            autoFocus
          />
        </Field>
      </div>
    </section>
  );
}

function ScopeStep({ request, setRequest }: ScanStepProps) {
  const { t } = useLocale();
  const updateList = (
    key: keyof CreateScanRequest["scope"],
    value: string,
  ) => {
    const values =
      key === "allowedPorts"
        ? value
            .split(",")
            .map((item) => Number(item.trim()))
            .filter(Number.isInteger)
        : splitList(value);
    setRequest((current) => ({
      ...current,
      scope: { ...current.scope, [key]: values },
    }));
  };
  return (
    <section>
      <SectionIntro title={t("newScan.scopeTitle")} description={t("newScan.scopeDescription")} />
      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <Field label={t("newScan.allowedHosts")} hint={t("newScan.commaHint")}>
          <input
            defaultValue={request.scope.allowedHosts.join(", ")}
            onBlur={(event) => updateList("allowedHosts", event.target.value)}
            className={inputClass}
          />
        </Field>
        <Field label={t("newScan.allowedPorts")} hint={t("newScan.commaHint")}>
          <input
            defaultValue={request.scope.allowedPorts.join(", ")}
            onBlur={(event) => updateList("allowedPorts", event.target.value)}
            placeholder="80, 443"
            className={inputClass}
          />
        </Field>
        <Field label={t("newScan.allowedPaths")} hint={t("newScan.pathsHint")}>
          <input
            defaultValue={request.scope.allowedPaths.join(", ")}
            onBlur={(event) => updateList("allowedPaths", event.target.value)}
            placeholder="/api, /account"
            className={inputClass}
          />
        </Field>
        <Field label={t("newScan.exclusions")} hint={t("newScan.commaHint")}>
          <input
            defaultValue={request.scope.exclusions.join(", ")}
            onBlur={(event) => updateList("exclusions", event.target.value)}
            placeholder="/logout, production billing"
            className={inputClass}
          />
        </Field>
      </div>
    </section>
  );
}

function OptionsStep({ request, setRequest }: ScanStepProps) {
  const { t } = useLocale();
  const updateOptions = (updates: Partial<CreateScanRequest["options"]>) =>
    setRequest((current) => ({
      ...current,
      options: { ...current.options, ...updates },
      fullModeConfirmed:
        updates.riskMode === "safe" ? false : current.fullModeConfirmed,
    }));
  return (
    <section>
      <SectionIntro title={t("newScan.optionsTitle")} description={t("newScan.optionsDescription")} />
      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <Field label={t("newScan.riskMode")}>
          <select
            value={request.options.riskMode}
            onChange={(event) =>
              updateOptions({ riskMode: event.target.value as RiskMode })
            }
            className={inputClass}
          >
            <option value="safe">{t("newScan.mode.safe")}</option>
            <option value="full">{t("newScan.mode.full")}</option>
          </select>
        </Field>
        <Field label={t("newScan.scanProfile")}>
          <select
            value={request.options.scanProfile}
            onChange={(event) =>
              updateOptions({ scanProfile: event.target.value as ScanProfile })
            }
            className={inputClass}
          >
            <option value="quick">{t("newScan.profile.quick")}</option>
            <option value="standard">{t("newScan.profile.standard")}</option>
            <option value="deep">{t("newScan.profile.deep")}</option>
          </select>
        </Field>
        <NumberField
          label={t("newScan.rate")}
          value={request.options.requestRatePerMinute}
          min={1}
          max={120}
          onChange={(value) => updateOptions({ requestRatePerMinute: value })}
        />
        <NumberField
          label={t("newScan.duration")}
          value={request.options.maxDurationMinutes}
          min={5}
          max={1440}
          onChange={(value) => updateOptions({ maxDurationMinutes: value })}
        />
        <NumberField
          label={t("newScan.budget")}
          value={request.options.maxBudgetUsd}
          min={0.01}
          max={1000}
          step={0.01}
          onChange={(value) => updateOptions({ maxBudgetUsd: value })}
        />
      </div>
      <div className="mt-4">
        <Field
          label={t("newScan.instructions")}
          hint={t("newScan.instructionsHint")}
        >
          <textarea
            value={request.options.instructions}
            onChange={(event) => updateOptions({ instructions: event.target.value })}
            rows={5}
            className={inputClass}
          />
        </Field>
      </div>
      {request.options.riskMode === "full" ? (
        <div className="mt-4 flex gap-3 rounded-xl border border-[color-mix(in_srgb,var(--warning)_45%,var(--border))] bg-amber-500/5 p-4">
          <CircleAlert className="mt-0.5 size-5 shrink-0 text-[var(--warning)]" />
          <p className="text-xs leading-5 text-[var(--text-muted)]">
            {t("newScan.fullModeWarning")}
          </p>
        </div>
      ) : null}
    </section>
  );
}

function ReviewStep({
  request,
  setRequest,
  provider,
  environmentReady,
}: ScanStepProps & {
  provider: ProviderStatus | null;
  environmentReady: boolean;
}) {
  const { t } = useLocale();
  return (
    <section>
      <SectionIntro title={t("newScan.reviewTitle")} description={t("newScan.reviewDescription")} />
      <div className="mt-5 divide-y divide-[var(--border)] rounded-2xl border border-[var(--border)] bg-[var(--surface)]">
        <ReviewRow label={t("newScan.primaryTarget")} value={request.target} />
        <ReviewRow
          label={t("newScan.riskMode")}
          value={t(
            request.options.riskMode === "safe"
              ? "newScan.mode.safe"
              : "newScan.mode.full",
          )}
        />
        <ReviewRow
          label={t("provider.title")}
          value={provider?.model ?? t("provider.notConfigured")}
          ready={provider?.configured === true && provider.connectionVerified}
        />
        <ReviewRow
          label={t("nav.environment")}
          value={t(
            environmentReady
              ? "environment.status.ready"
              : "environment.summaryNeedsAction",
          )}
          ready={environmentReady}
        />
      </div>

      <div className="mt-5 space-y-3">
        <Confirmation
          checked={request.authorizationConfirmed}
          onChange={(checked) =>
            setRequest((current) => ({
              ...current,
              authorizationConfirmed: checked,
            }))
          }
          label={t("newScan.authorizationConfirmation")}
        />
        {request.options.riskMode === "full" ? (
          <Confirmation
            checked={request.fullModeConfirmed}
            onChange={(checked) =>
              setRequest((current) => ({
                ...current,
                fullModeConfirmed: checked,
              }))
            }
            label={t("newScan.fullModeConfirmation")}
            warning
          />
        ) : null}
      </div>
    </section>
  );
}

function SectionIntro({ title, description }: { title: string; description: string }) {
  return (
    <div>
      <h2 className="text-lg font-semibold tracking-[-0.02em] text-[var(--text)]">{title}</h2>
      <p className="mt-1 max-w-[65ch] text-sm leading-6 text-[var(--text-muted)]">
        {description}
      </p>
    </div>
  );
}

function NumberField({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (value: number) => void;
}) {
  return (
    <Field label={label}>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(event) => onChange(Number(event.target.value))}
        className={inputClass}
      />
    </Field>
  );
}

function ReviewRow({
  label,
  value,
  ready,
}: {
  label: string;
  value: string;
  ready?: boolean;
}) {
  return (
    <div className="grid gap-1 px-4 py-3 sm:grid-cols-[160px_1fr]">
      <span className="text-xs text-[var(--text-muted)]">{label}</span>
      <span className="flex items-center gap-2 break-all text-sm text-[var(--text)]">
        {typeof ready === "boolean" ? (
          ready ? (
            <ShieldCheck className="size-4 shrink-0 text-[var(--accent)]" />
          ) : (
            <CircleAlert className="size-4 shrink-0 text-[var(--warning)]" />
          )
        ) : null}
        {value}
      </span>
    </div>
  );
}

function Confirmation({
  checked,
  onChange,
  label,
  warning = false,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  warning?: boolean;
}) {
  return (
    <label
      className={`flex cursor-pointer items-start gap-3 rounded-xl border p-4 text-sm leading-6 ${
        warning
          ? "border-[color-mix(in_srgb,var(--warning)_45%,var(--border))]"
          : "border-[var(--border)]"
      }`}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-1 size-4 accent-[var(--accent)]"
      />
      <span className="text-[var(--text)]">{label}</span>
    </label>
  );
}

interface ScanStepProps {
  request: CreateScanRequest;
  setRequest: React.Dispatch<React.SetStateAction<CreateScanRequest>>;
}

function splitList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}
