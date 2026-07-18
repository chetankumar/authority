import { useState } from "react";

import { ApiError } from "../../api/client";
import {
  createJob,
  patchJob,
  type AIJobDefinition,
  type AIJobInput,
  type ModelConfig,
  type OutputType,
  type Placeholder,
} from "../../api/settings";
import { Modal } from "../../components/Modal";
import { Button, Field, Input, Select } from "../../components/ui";
import { PromptEditor } from "./PromptEditor";

const OUTPUT_TYPES: { value: OutputType; label: string }[] = [
  { value: "chat", label: "Chat — free reply" },
  { value: "edit-proposals", label: "Edit proposals — returns applyable find-and-replace edits" },
  { value: "metadata-proposals", label: "Metadata proposals — returns applyable field updates" },
  { value: "audio-script", label: "Audio script — returns a scene audio-drama script proposal" },
];

export function JobModal({
  existing,
  models,
  placeholders,
  onClose,
  onSaved,
}: {
  existing: AIJobDefinition | null;
  models: ModelConfig[];
  placeholders: Placeholder[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(existing?.name ?? "");
  const [prompt, setPrompt] = useState(existing?.prompt ?? "");
  const [defaultModelId, setDefaultModelId] = useState(existing?.defaultModelId ?? models[0]?.id ?? "");
  const [outputType, setOutputType] = useState<OutputType>(existing?.outputType ?? "chat");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [unknown, setUnknown] = useState<string[] | null>(null);
  const [saving, setSaving] = useState(false);

  async function save(force: boolean) {
    setSaving(true);
    setFields({});
    if (force) setUnknown(null);
    const body: AIJobInput = { name: name.trim(), prompt, defaultModelId, outputType, force };
    try {
      if (existing) await patchJob(existing.id, body);
      else await createJob(body);
      onSaved();
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        const tokens = err.detail.unknownPlaceholders as string[] | undefined;
        if (tokens?.length) setUnknown(tokens);
        else setFields(err.fields);
      } else {
        setFields({ _form: "Couldn't save the job." });
      }
    } finally {
      setSaving(false);
    }
  }

  const noModels = models.length === 0;

  return (
    <Modal
      title={existing ? "Edit AI-Job" : "Add AI-Job"}
      width={640}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" onClick={() => save(false)} disabled={saving || noModels}>
            {saving ? "Saving…" : "Save job"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {noModels && (
          <p className="text-[0.8125rem] text-danger">Add a model first — a job needs a default model.</p>
        )}
        {fields._form && <p className="text-[0.8125rem] text-danger">{fields._form}</p>}

        <Field label="Name" error={fields.name}>
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Editorial Review" />
        </Field>

        <Field label="Prompt" hint="Type @ to insert a placeholder">
          <PromptEditor value={prompt} onChange={setPrompt} placeholders={placeholders} />
        </Field>

        {unknown && (
          <div className="rounded-control border border-attn bg-attn-wash p-3 text-[0.8125rem] text-ink">
            <p className="mb-2">
              These placeholders aren't in the registry and will pass through literally:{" "}
              <span className="font-mono">{unknown.join(", ")}</span>
            </p>
            <Button variant="secondary" onClick={() => save(true)} disabled={saving}>
              Save anyway
            </Button>
          </div>
        )}

        <Field label="Output type">
          <Select value={outputType} onChange={(e) => setOutputType(e.target.value as OutputType)}>
            {OUTPUT_TYPES.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Default model" error={fields.defaultModelId}>
          <Select value={defaultModelId} onChange={(e) => setDefaultModelId(e.target.value)}>
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </Select>
        </Field>
      </div>
    </Modal>
  );
}
