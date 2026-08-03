import {
  CheckCircle2,
  KeyRound,
  LoaderCircle,
  PlugZap,
  Search,
} from "lucide-react";
import { useEffect, useState } from "react";

import type {
  ProviderKind,
  ProviderStatus,
} from "../../features/scan-control/contracts";
import {
  configureProvider,
  discoverProviderModels,
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
  authenticationFailed: "provider.error.authenticationFailed",
  connectionFailed: "provider.error.connectionFailed",
  invalidProviderResponse: "provider.error.invalidProviderResponse",
};

const apiBasePlaceholders: Record<ProviderKind, string> = {
  openai: "https://api.openai.com/v1",
  anthropic: "https://api.anthropic.com/v1",
  gemini: "https://generativelanguage.googleapis.com/v1beta",
  openaiCompatible: "https://api.example.com/v1",
  ollama: "http://127.0.0.1:11434/v1",
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
  const [models, setModels] = useState<string[]>([]);
  const [busy, setBusy] = useState<"discover" | "save" | "test" | null>(null);
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
        apiBase: selectedApiBase || null,
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

  const discover = async () => {
    setBusy("discover");
    setFeedback(null);
    try {
      const result = await discoverProviderModels({
        provider: selectedProvider,
        apiBase: selectedApiBase || null,
        apiKey: selectedProvider === "ollama" ? null : apiKey || null,
      });
      const discovered = result.models.map((value) =>
        toRuntimeModel(selectedProvider, value),
      );
      setModels(discovered);
      if (!selectedModel && discovered[0]) setModel(discovered[0]);
      setFeedback(
        discovered.length > 0 ? "provider.modelsLoaded" : "provider.noModels",
      );
    } catch (error) {
      const code = error instanceof ControlServiceError ? error.code : "";
      setFeedback(errorKeys[code] ?? "provider.error.modelsFailed");
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

      <fieldset className="mt-5">
        <legend className="text-xs font-medium text-[var(--text-muted)]">
          {t("provider.kind")}
        </legend>
        <div className="mt-2 grid gap-2 sm:grid-cols-3">
          {Object.entries(providerLabels).map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => {
                setProvider(value as ProviderKind);
                setModel("");
                setApiBase("");
                setModels([]);
                setFeedback(null);
              }}
              className={`rounded-xl border px-3 py-2.5 text-left text-sm font-semibold transition active:scale-[0.98] ${
                selectedProvider === value
                  ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent-strong)]"
                  : "border-[var(--border)] text-[var(--text-muted)] hover:border-[var(--border-strong)]"
              }`}
              aria-pressed={selectedProvider === value}
            >
              {label}
            </button>
          ))}
        </div>
      </fieldset>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <Field label={t("provider.apiBase")} hint={t("provider.apiBaseHint")}>
          <input
            value={selectedApiBase}
            onChange={(event) => setApiBase(event.target.value)}
            placeholder={apiBasePlaceholders[selectedProvider]}
            className={inputClass}
          />
        </Field>
        {selectedProvider !== "ollama" ? (
          <Field label={t("provider.apiKey")}>
            <input
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              autoComplete="new-password"
              placeholder={
                status?.provider === selectedProvider && status.hasApiKey
                  ? t("provider.keyStored")
                  : t("provider.keyPlaceholder")
              }
              className={inputClass}
            />
          </Field>
        ) : null}
        <Field label={t("provider.model")}>
          <input
            value={selectedModel}
            onChange={(event) => setModel(event.target.value)}
            placeholder={t("provider.modelPlaceholder")}
            className={inputClass}
            list="provider-model-options"
          />
          <datalist id="provider-model-options">
            {models.map((value) => <option key={value} value={value} />)}
          </datalist>
        </Field>
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => void discover()}
          disabled={busy !== null}
          className="inline-flex items-center gap-2 rounded-xl border border-[var(--border-strong)] px-4 py-2.5 text-sm font-semibold text-[var(--text)] transition active:scale-[0.98] disabled:opacity-50"
        >
          {busy === "discover" ? (
            <LoaderCircle className="size-4 animate-spin" />
          ) : (
            <Search className="size-4" />
          )}
          {t("provider.fetchModels")}
        </button>
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

function toRuntimeModel(provider: ProviderKind, model: string): string {
  if (model.includes("/")) return model;
  const prefix = provider === "openaiCompatible" ? "openai" : provider;
  return `${prefix}/${model}`;
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
