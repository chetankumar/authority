import { useEffect, useRef, useState } from "react";

import { ApiError } from "../../api/client";
import {
  createModel,
  patchModel,
  syncProviderModels,
  type ModelConfig,
  type ModelInput,
  type Provider,
} from "../../api/settings";
import { ComboboxInput } from "../../components/ComboboxInput";
import { Modal } from "../../components/Modal";
import { Button, Field, Input, Select } from "../../components/ui";
import { useProviderModels } from "../../queries/settings";

const PROVIDERS: { value: Provider; label: string }[] = [
  { value: "anthropic", label: "Anthropic" },
  { value: "openai", label: "OpenAI" },
  { value: "gemini", label: "Gemini" },
  { value: "openrouter", label: "OpenRouter" },
  { value: "openai-compatible", label: "OpenAI-compatible (LM Studio, etc.)" },
  { value: "ollama", label: "Ollama" },
];

const BASE_URL_PLACEHOLDER: Partial<Record<Provider, string>> = {
  "openai-compatible": "http://localhost:1234/v1",
  ollama: "http://localhost:11434",
};

const MODEL_NAME_PLACEHOLDER: Partial<Record<Provider, string>> = {
  anthropic: "claude-sonnet-4-6",
  openai: "gpt-4.1",
  gemini: "gemini-2.5-flash",
  openrouter: "anthropic/claude-sonnet-4.5",
  "openai-compatible": "local-model",
  ollama: "llama3.2",
};

const DEFAULT_ENV: Partial<Record<Provider, string>> = {
  anthropic: "ANTHROPIC_API_KEY",
  openai: "OPENAI_API_KEY",
  gemini: "GOOGLE_API_KEY",
  openrouter: "OPENROUTER_API_KEY",
};

const STALE_MS = 24 * 60 * 60 * 1000;

const VISIBLE_FIELDS = new Set(["label", "modelName", "apiKey", "baseUrl", "_form"]);

function needsKey(p: Provider) {
  return p === "anthropic" || p === "openai" || p === "gemini" || p === "openrouter";
}
function needsBaseUrl(p: Provider) {
  return p === "openai-compatible" || p === "ollama";
}

function isStale(syncedAt: string | null | undefined): boolean {
  if (!syncedAt) return true;
  const t = Date.parse(syncedAt);
  if (Number.isNaN(t)) return true;
  return Date.now() - t > STALE_MS;
}

export function ModelModal({
  existing,
  onClose,
  onSaved,
}: {
  existing: ModelConfig | null;
  onClose: () => void;
  onSaved: (model: ModelConfig) => void;
}) {
  const [label, setLabel] = useState(existing?.label ?? "");
  const [provider, setProvider] = useState<Provider>(existing?.provider ?? "anthropic");
  const [modelName, setModelName] = useState(existing?.modelName ?? "");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState(existing?.baseUrl ?? "");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [syncError, setSyncError] = useState<string | null>(null);
  const autoKeyRef = useRef<string | null>(null);

  const catalogBase = needsBaseUrl(provider) ? baseUrl.trim() || null : null;
  const catalogReady = !needsBaseUrl(provider) || Boolean(catalogBase);
  const catalog = useProviderModels(provider, catalogBase, catalogReady);
  const suggestions = (catalog.data?.models ?? []).map((m) => ({ value: m.id, label: m.name }));

  async function refreshModels() {
    if (needsBaseUrl(provider) && !baseUrl.trim()) {
      setSyncError("Enter a base URL before refreshing the model list.");
      return;
    }
    setSyncing(true);
    setSyncError(null);
    try {
      await syncProviderModels({
        provider,
        baseUrl: needsBaseUrl(provider) ? baseUrl.trim() : null,
        apiKey: apiKey.trim() || undefined,
      });
      await catalog.refetch();
    } catch (err) {
      if (err instanceof ApiError) setSyncError(err.message);
      else setSyncError("Couldn't refresh the model list.");
    } finally {
      setSyncing(false);
    }
  }

  useEffect(() => {
    if (!catalogReady || !catalog.isFetched || syncing) return;
    const key = `${provider}|${catalogBase ?? ""}`;
    if (autoKeyRef.current === key) return;
    if (!isStale(catalog.data?.syncedAt)) {
      autoKeyRef.current = key;
      return;
    }
    autoKeyRef.current = key;
    void refreshModels();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refresh when provider/baseUrl/cache identity changes
  }, [provider, catalogBase, catalogReady, catalog.isFetched, catalog.data?.syncedAt]);

  async function save() {
    setSaving(true);
    setFields({});
    try {
      const body: Partial<ModelInput> = {
        label: label.trim(),
        provider,
        modelName: modelName.trim(),
        baseUrl: needsBaseUrl(provider) ? baseUrl.trim() : null,
      };
      if (apiKey.trim()) body.apiKey = apiKey.trim();

      const saved = existing
        ? await patchModel(existing.id, body)
        : await createModel(body as ModelInput);
      onSaved(saved);
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        const next = { ...err.fields };
        const unmapped = Object.entries(next).filter(([k]) => !VISIBLE_FIELDS.has(k));
        if (unmapped.length && !next._form) {
          next._form = unmapped.map(([, msg]) => msg).join(" ") || err.message;
        }
        setFields(next);
      } else if (err instanceof ApiError) setFields({ _form: err.message });
      else setFields({ _form: "Couldn't save the model." });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      title={existing ? "Edit model" : "Add model"}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" onClick={save} disabled={saving}>
            {saving ? "Saving…" : "Save model"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {fields._form && <p className="text-[0.8125rem] text-danger">{fields._form}</p>}

        <Field label="Label" error={fields.label}>
          <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Sonnet 4.6" />
        </Field>

        <Field label="Provider">
          <Select
            value={provider}
            onChange={(e) => {
              setProvider(e.target.value as Provider);
              autoKeyRef.current = null;
              setSyncError(null);
            }}
          >
            {PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </Select>
        </Field>

        <div>
          <div className="mb-1 flex items-center justify-between gap-2">
            <span className="text-[0.75rem] tracking-[0.02em] text-ink-soft">Model name</span>
            <Button
              variant="ghost"
              type="button"
              className="h-7 px-2 text-[0.75rem]"
              onClick={() => void refreshModels()}
              disabled={syncing}
            >
              {syncing ? "Refreshing…" : "Refresh models"}
            </Button>
          </div>
          <ComboboxInput
            value={modelName}
            onChange={setModelName}
            options={suggestions}
            placeholder={MODEL_NAME_PLACEHOLDER[provider] ?? "model-id"}
          />
          {fields.modelName ? (
            <span className="mt-1 block text-[0.75rem] text-danger">{fields.modelName}</span>
          ) : (
            <span className="mt-1 block text-[0.75rem] text-ink-faint">
              {syncError
                ? syncError
                : catalog.data?.syncedAt
                  ? `Suggestions from last sync · ${catalog.data.syncedAt}`
                  : "Type any model id. Refresh loads provider suggestions."}
            </span>
          )}
        </div>

        {needsKey(provider) && (
          <Field
            label="API key"
            hint={
              existing
                ? `Leave blank to keep the stored key. Or paste a key, use $\{ENV_VAR}, or clear it to use ${DEFAULT_ENV[provider]}.`
                : `Leave blank to use ${DEFAULT_ENV[provider]} from the environment. Or paste a key or $\{ENV_VAR}.`
            }
            error={fields.apiKey}
          >
            <Input
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={existing?.apiKeyMasked ?? `${DEFAULT_ENV[provider]} (from environment)`}
            />
          </Field>
        )}

        {needsBaseUrl(provider) && (
          <Field label="Base URL" error={fields.baseUrl}>
            <Input
              value={baseUrl}
              onChange={(e) => {
                setBaseUrl(e.target.value);
                autoKeyRef.current = null;
              }}
              placeholder={BASE_URL_PLACEHOLDER[provider]}
            />
          </Field>
        )}
      </div>
    </Modal>
  );
}
