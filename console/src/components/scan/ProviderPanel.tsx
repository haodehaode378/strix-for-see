import { CheckCircle2, KeyRound, LoaderCircle, PlugZap } from "lucide-react";
import { useEffect, useState } from "react";

import type {
  ProviderKind,
  ProviderStatus,
} from "../../features/scan-control/contracts";
import {
  configureProvider,
  testProvider,
} from "../../features/scan-control/scanClient";
import { useProvider } from "../../features/scan-control/useProvider";
import { ControlServiceError } from "../../shared/api/controlServiceClient";
import type { MessageKey } from "../../shared/i18n/messages";
import { useLocale } from "../../shared/i18n/useLocale";

const providerLabels: Record<ProviderKind, string> = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  gemini: "Gemini",
  openaiCompatible: "OpenAI-compatible",
  ollama: "Ollama",
};

const errorKeys: Record<string, MessageKey> = {
  apiKeyRequired: "provider.error.apiKeyRequired",
  apiBaseRequired: "provider.error.apiBaseRequired",
  invalidApiBase: "provider.error.invalidApiBase",
  secretStoreFailed: "provider.error.secretStoreFailed",
};

export function ProviderPanel({
  onStatus,
}: {
  onStatus: (status: ProviderStatus) => void;
}) {
  const { t } = useLocale();
  const { status, state, setStatus } = useProvider();
  const [provider, setProvider] = useState<ProviderKind | null>(null);
  const [model, setModel] = useState<string | null>(null);
  const [apiBase, setApiBase] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState<"save" | "test" | null>(null);
  const [feedback, setFeedback] = useState<MessageKey | null>(null);

  useEffect(() => {
    if (!status) return;
    onStatus(status);
  }, [onStatus, status]);

  const save = async () => {
    const selectedProvider = provider ?? status?.provider ?? "openai";
    const selectedModel = model ?? status?.model ?? "";
    const selectedApiBase = apiBase ?? status?.apiBase ?? "";
    setBusy("save");
    setFeedback(null);
    try {
      const result = await configureProvider({
        provider: selectedProvider,
        model: selectedModel,
        apiBase:
          selectedProvider === "openaiCompatible" || selectedProvider === "ollama"
            ? selectedApiBase || null
            : null,
        apiKey: selectedProvider === "ollama" ? null : apiKey || null,
      });
      setApiKey("");
      setStatus(result);
      onStatus(result);
      setFeedback("provider.saved");
    } catch (error) {
      const code = error instanceof ControlServiceError ? error.code : "";
      setFeedback(errorKeys[code] ?? "provider.error.saveFailed");
    } finally {
      setBusy(null);
    }
  };

  const test = async () => {
    setBusy("test");
    setFeedback(null);
    try {
      const result = await testProvider();
      setFeedback(result.ok ? "provider.testPassed" : "provider.testFailed");
      if (result.ok && status) {
        const verified = { ...status, connectionVerified: true };
        setStatus(verified);
        onStatus(verified);
      }
    } catch {
      setFeedback("provider.testFailed");
    } finally {
      setBusy(null);
    }
  };

  if (state === "loading") {
    return (
      <div className="h-48 animate-pulse rounded-2xl border border-[var(--border)] bg-[var(--surface)]" />
    );
  }

  const selectedProvider = provider ?? status?.provider ?? "openai";
  const selectedModel = model ?? status?.model ?? "";
  const selectedApiBase = apiBase ?? status?.apiBase ?? "";

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        void save();
      }}
      className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="flex items-center gap-2 text-sm font-semibold text-[var(--text)]">
            <KeyRound className="size-4 text-[var(--accent)]" />
            {t("provider.title")}
          </h2>
          <p className="mt-1 text-xs leading-5 text-[var(--text-muted)]">
            {t("provider.description")}
          </p>
        </div>
        {status?.configured && status.connectionVerified ? (
          <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--accent)]">
            <CheckCircle2 className="size-4" />
            {t("provider.configured")}
          </span>
        ) : null}
      </div>

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <Field label={t("provider.kind")}>
          <select
            value={selectedProvider}
            onChange={(event) => setProvider(event.target.value as ProviderKind)}
            className={inputClass}
          >
            {Object.entries(providerLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("provider.model")}>
          <input
            value={selectedModel}
            onChange={(event) => setModel(event.target.value)}
            placeholder={t("provider.modelPlaceholder")}
            className={inputClass}
          />
        </Field>
        {selectedProvider === "openaiCompatible" || selectedProvider === "ollama" ? (
          <Field label={t("provider.apiBase")}>
            <input
              value={selectedApiBase}
              onChange={(event) => setApiBase(event.target.value)}
              placeholder={
                selectedProvider === "ollama"
                  ? "http://127.0.0.1:11434/v1"
                  : "https://api.example.com/v1"
              }
              className={inputClass}
            />
          </Field>
        ) : null}
        {selectedProvider !== "ollama" ? (
          <Field label={t("provider.apiKey")}>
            <input
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              autoComplete="new-password"
              placeholder={
                status?.hasApiKey
                  ? t("provider.keyStored")
                  : t("provider.keyPlaceholder")
              }
              className={inputClass}
            />
          </Field>
        ) : null}
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={busy !== null || !selectedModel.trim()}
          className="inline-flex items-center gap-2 rounded-xl bg-[var(--accent)] px-4 py-2.5 text-sm font-semibold text-white transition active:scale-[0.98] disabled:opacity-50"
        >
          {busy === "save" ? (
            <LoaderCircle className="size-4 animate-spin" />
          ) : (
            <KeyRound className="size-4" />
          )}
          {t("provider.save")}
        </button>
        <button
          type="button"
          onClick={() => void test()}
          disabled={busy !== null || !status?.configured}
          className="inline-flex items-center gap-2 rounded-xl border border-[var(--border)] px-4 py-2.5 text-sm font-semibold text-[var(--text-muted)] transition active:scale-[0.98] disabled:opacity-50"
        >
          <PlugZap className="size-4" />
          {t("provider.test")}
        </button>
        <p className="text-xs text-[var(--text-muted)]" aria-live="polite">
          {feedback ? t(feedback) : ""}
        </p>
      </div>
    </form>
  );
}

export const inputClass =
  "w-full rounded-xl border border-[var(--border)] bg-[var(--surface-raised)] px-3.5 py-2.5 text-sm text-[var(--text)] outline-none transition placeholder:text-[var(--text-muted)] focus:border-[var(--accent)]";

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="grid gap-2 text-xs font-medium text-[var(--text-muted)]">
      <span>{label}</span>
      {children}
      {hint ? <span className="font-normal leading-5">{hint}</span> : null}
    </label>
  );
}
