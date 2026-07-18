import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { deleteJob, type AIJobDefinition } from "../../api/settings";
import { Button } from "../../components/ui";
import { useToast } from "../../components/Toast";
import { keys } from "../../queries/keys";
import { useJobs, useModels, usePlaceholders } from "../../queries/settings";
import { JobModal } from "./JobModal";

const OUTPUT_LABEL: Record<string, string> = {
  chat: "Chat",
  "edit-proposals": "Edit proposals",
  "metadata-proposals": "Metadata proposals",
  "audio-script": "Audio script",
};

export default function AIJobsPage() {
  const jobs = useJobs();
  const models = useModels();
  const placeholders = usePlaceholders();
  const qc = useQueryClient();
  const toast = useToast();

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<AIJobDefinition | null>(null);

  const list = jobs.data ?? [];
  const modelList = models.data ?? [];
  const modelLabel = (id: string) => modelList.find((m) => m.id === id)?.label ?? "—";

  function openAdd() {
    setEditing(null);
    setModalOpen(true);
  }
  function openEdit(j: AIJobDefinition) {
    setEditing(j);
    setModalOpen(true);
  }
  function onSaved() {
    setModalOpen(false);
    qc.invalidateQueries({ queryKey: keys.settings("ai-jobs") });
    toast.success("Job saved");
  }

  async function onDelete(j: AIJobDefinition) {
    if (!window.confirm(`Delete the AI-Job "${j.name}"?`)) return;
    try {
      await deleteJob(j.id);
      qc.invalidateQueries({ queryKey: keys.settings("ai-jobs") });
      toast.success("Job deleted");
    } catch {
      toast.error("Couldn't delete the job.");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-[0.875rem] font-semibold text-ink">AI-Jobs</h2>
        <Button variant="primary" onClick={openAdd}>
          Add AI-Job
        </Button>
      </div>

      {list.length === 0 ? (
        <p className="text-[0.875rem] text-ink-soft">
          No jobs yet. Define reusable prompts (with @placeholders) to run against scenes.
        </p>
      ) : (
        <table className="w-full border-collapse text-[0.8125rem]">
          <thead>
            <tr className="border-b border-line text-left text-ink-soft">
              <th className="py-2 font-medium">Name</th>
              <th className="py-2 font-medium">Default model</th>
              <th className="py-2 font-medium">Output type</th>
              <th className="py-2" />
            </tr>
          </thead>
          <tbody>
            {list.map((j) => (
              <tr key={j.id} className="border-b border-line">
                <td className="py-2 text-ink">{j.name}</td>
                <td className="py-2 text-ink-soft">{modelLabel(j.defaultModelId)}</td>
                <td className="py-2 text-ink-soft">{OUTPUT_LABEL[j.outputType] ?? j.outputType}</td>
                <td className="py-2 text-right">
                  <Button variant="ghost" onClick={() => openEdit(j)} aria-label="Edit job">
                    ✎
                  </Button>
                  <Button variant="ghost" onClick={() => onDelete(j)} aria-label="Delete job">
                    🗑
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {modalOpen && (
        <JobModal
          existing={editing}
          models={modelList}
          placeholders={placeholders.data ?? []}
          onClose={() => setModalOpen(false)}
          onSaved={onSaved}
        />
      )}
    </div>
  );
}
