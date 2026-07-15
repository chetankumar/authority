import { useState } from "react";

import { ApiError } from "../../api/client";
import { createModel, patchModel, type ModelConfig, type ModelInput, type Provider } from "../../api/settings";
import { Modal } from "../../components/Modal";
import { Button, Field, Input, Select } from "../../components/ui";

const PROVIDERS: { value: Provider; label: string }[] = [
  { value: "anthropic", label: "Anthropic" },
  { value: "openai", label: "OpenAI" },
  { value: "gemini", label: "Gemini" },
  { value: "openai-compatible", label: "OpenAI-compatible (LM Studio, etc.)" },
  { value: "ollama", label: "Ollama" },
];

const BASE_URL_PLACEHOLDER: Partial<Record<Provider, string>> = {
  "openai-compatible": "http://localhost:1234/v1",
  ollama: "http://localhost:11434",
};

const DEFAULT_ENV: Partial<Record<Provider, string>> = {
  anthropic: "ANTHROPIC_API_KEY",
  openai: "OPENAI_API_KEY",
  gemini: "GOOGLE_API_KEY",
};

// Field keys that render their own inline error slot in the form.
const VISIBLE_FIELDS = new Set(["label", "modelName", "apiKey", "baseUrl", "_form"]);

function needsKey(p: Provider) {
  return p === "anthropic" || p === "openai" || p === "gemini";
}
function needsBaseUrl(p: Provider) {
  return p === "openai-compatible" || p === "ollama";
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
  // Blank means: use the provider's default env var (or, in edit mode, keep the
  // stored key). Authors can also paste a literal key or a ${ENV_VAR} reference.
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState(existing?.baseUrl ?? "");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

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
      // Edit: omit apiKey when untouched to keep the stored secret.
      if (apiKey.trim()) body.apiKey = apiKey.trim();

      const saved = existing
        ? await patchModel(existing.id, body)
        : await createModel(body as ModelInput);
      onSaved(saved);
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        const next = { ...err.fields };
        // Surface any field errors that have no visible input (e.g. provider),
        // so a failed save can never be silent.
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
          <Select value={provider} onChange={(e) => setProvider(e.target.value as Provider)}>
            {PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Model name" error={fields.modelName}>
          <Input
            value={modelName}
            onChange={(e) => setModelName(e.target.value)}
            placeholder="claude-sonnet-4-6"
          />
        </Field>

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
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder={BASE_URL_PLACEHOLDER[provider]}
            />
          </Field>
        )}
      </div>
    </Modal>
  );
}
