import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../../api/client";
import { deleteModel, patchAI, testModel, type AISettings, type ModelConfig } from "../../api/settings";
import { BlockedDeletionDialog, type BlockedRef } from "../../components/BlockedDeletionDialog";
import { Button, Field, Select } from "../../components/ui";
import { useToast } from "../../components/Toast";
import { keys } from "../../queries/keys";
import { useAI, useModels } from "../../queries/settings";
import { ModelModal } from "./ModelModal";

const MODEL_SLOTS: { key: keyof AISettings; label: string; hint: string }[] = [
  { key: "utilityModelId", label: "Default utility model", hint: "Fallback for any task below that's left unset, plus sundry system tasks (chat-thread titling)" },
  { key: "commitMessageModelId", label: "Commit message model", hint: "Suggests a commit message from the staged diff" },
  { key: "sceneSummaryModelId", label: "Enrichment — scene summarization model", hint: "Writes scene.summary after a save (if the toggle is on)" },
  { key: "characterParsingModelId", label: "Enrichment — character parsing model", hint: "Matches characters mentioned in prose against the character sheet" },
  { key: "chatDefaultModelId", label: "AI chat default model", hint: "Preselected when opening a new chat from the editor" },
];

// Keys match the backend's 409 blockedBy shape (settings_service.delete_model),
// which drops the "Id" suffix from the AISettings field names.
const BLOCKED_SLOT_LABELS: Record<string, string> = {
  utilityModel: "Default utility model (below)",
  commitMessageModel: "Commit message model (below)",
  characterParsingModel: "Character parsing model (below)",
  sceneSummaryModel: "Scene summarization model (below)",
  chatDefaultModel: "AI chat default model (below)",
};

export default function AISettingsPage() {
  const models = useModels();
  const ai = useAI();
  const qc = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<ModelConfig | null>(null);
  const [blocked, setBlocked] = useState<{ name: string; refs: BlockedRef[] } | null>(null);
  const [testing, setTesting] = useState<Set<string>>(new Set());
  const [results, setResults] = useState<Record<string, { ok: boolean; text: string }>>({});

  const list = models.data ?? [];

  function openAdd() {
    setEditing(null);
    setModalOpen(true);
  }
  function openEdit(m: ModelConfig) {
    setEditing(m);
    setModalOpen(true);
  }

  function onSaved() {
    setModalOpen(false);
    qc.invalidateQueries({ queryKey: keys.settings("models") });
    toast.success("Model saved");
  }

  async function onDelete(m: ModelConfig) {
    if (!window.confirm(`Delete the model "${m.label}"? This can't be undone.`)) return;
    try {
      await deleteModel(m.id);
      qc.invalidateQueries({ queryKey: keys.settings("models") });
      toast.success("Model deleted");
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        const by = (err.detail.blockedBy ?? {}) as {
          aiJobs?: { id: string; name: string }[];
          [slot: string]: unknown;
        };
        const refs: BlockedRef[] = [];
        for (const job of by.aiJobs ?? [])
          refs.push({ label: `AI-Job: ${job.name}`, onNavigate: () => navigate("/settings/ai-jobs") });
        for (const [slot, label] of Object.entries(BLOCKED_SLOT_LABELS)) {
          if (by[slot]) refs.push({ label });
        }
        setBlocked({ name: m.label, refs });
      } else if (err instanceof ApiError && err.status === 404) {
        qc.invalidateQueries({ queryKey: keys.settings("models") });
        toast.error("That model was already gone — refreshed the list.");
      } else {
        toast.error("Couldn't delete the model.");
      }
    }
  }

  async function onTest(m: ModelConfig) {
    setTesting((prev) => new Set(prev).add(m.id));
    setResults((prev) => {
      const next = { ...prev };
      delete next[m.id];
      return next;
    });
    try {
      const res = await testModel(m.id);
      if (res.ok) {
        setResults((prev) => ({ ...prev, [m.id]: { ok: true, text: `OK · ${res.latencyMs ?? 0}ms` } }));
        toast.success(`${m.label} replied${res.message ? `: ${res.message}` : ""}`);
      } else {
        setResults((prev) => ({ ...prev, [m.id]: { ok: false, text: res.error ?? "Failed" } }));
        toast.error(`${m.label}: ${res.error ?? "Test failed"}`);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        qc.invalidateQueries({ queryKey: keys.settings("models") });
        toast.error("That model no longer exists — refreshed the list.");
      } else {
        setResults((prev) => ({ ...prev, [m.id]: { ok: false, text: "Failed" } }));
        toast.error(`Couldn't test ${m.label}.`);
      }
    } finally {
      setTesting((prev) => {
        const next = new Set(prev);
        next.delete(m.id);
        return next;
      });
    }
  }

  async function onSlotChange(key: keyof AISettings, id: string, label: string) {
    try {
      const updated = await patchAI({ [key]: id || null });
      qc.setQueryData(keys.settings("ai"), updated);
      toast.success(`${label} updated`);
    } catch {
      toast.error(`Couldn't update ${label.toLowerCase()}.`);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-[0.875rem] font-semibold text-ink">Models</h2>
        <Button variant="primary" onClick={openAdd}>
          Add model
        </Button>
      </div>

      {list.length === 0 ? (
        <p className="text-[0.875rem] text-ink-soft">
          No models yet. Add one to enable chat, AI-Jobs, and enrichment.
        </p>
      ) : (
        <table className="w-full border-collapse text-[0.8125rem]">
          <thead>
            <tr className="border-b border-line text-left text-ink-soft">
              <th className="py-2 font-medium">Label</th>
              <th className="py-2 font-medium">Provider</th>
              <th className="py-2 font-medium">Model name</th>
              <th className="py-2 font-medium">Key</th>
              <th className="py-2 font-medium">Base URL</th>
              <th className="py-2" />
            </tr>
          </thead>
          <tbody>
            {list.map((m) => (
              <tr key={m.id} className="border-b border-line">
                <td className="py-2 text-ink">{m.label}</td>
                <td className="py-2 text-ink-soft">{m.provider}</td>
                <td className="py-2 font-mono text-ink-soft">{m.modelName}</td>
                <td className="py-2 font-mono text-ink-faint">{m.apiKeyMasked ?? "—"}</td>
                <td className="py-2 font-mono text-ink-faint">{m.baseUrl ?? "—"}</td>
                <td className="py-2">
                  <div className="flex items-center justify-end gap-2">
                    {results[m.id] && (
                      <span
                        title={results[m.id].text}
                        className={[
                          "max-w-[10rem] truncate rounded-full px-2 py-0.5 text-[0.6875rem]",
                          results[m.id].ok ? "bg-ok-wash text-ok" : "bg-danger-wash text-danger",
                        ].join(" ")}
                      >
                        {results[m.id].ok ? results[m.id].text : "Failed"}
                      </span>
                    )}
                    <Button
                      variant="ghost"
                      onClick={() => onTest(m)}
                      disabled={testing.has(m.id)}
                      aria-label="Test model"
                    >
                      {testing.has(m.id) ? "Testing…" : "Test"}
                    </Button>
                    <Button variant="ghost" onClick={() => openEdit(m)} aria-label="Edit model">
                      ✎
                    </Button>
                    <Button variant="ghost" onClick={() => onDelete(m)} aria-label="Delete model">
                      🗑
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="max-w-xs space-y-4 border-t border-line pt-5">
        <h2 className="text-[0.875rem] font-semibold text-ink">AI task models</h2>
        {MODEL_SLOTS.map((slot) => (
          <Field key={slot.key} label={slot.label} hint={slot.hint}>
            <Select
              value={ai.data?.[slot.key] ?? ""}
              onChange={(e) => onSlotChange(slot.key, e.target.value, slot.label)}
            >
              <option value="">None</option>
              {list.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </Select>
          </Field>
        ))}
      </div>

      {modalOpen && <ModelModal existing={editing} onClose={() => setModalOpen(false)} onSaved={onSaved} />}
      {blocked && (
        <BlockedDeletionDialog name={blocked.name} refs={blocked.refs} onClose={() => setBlocked(null)} />
      )}
    </div>
  );
}
