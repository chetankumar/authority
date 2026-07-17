// Resources page (doc 06 §Resources) — the material around the book: research,
// references, worldbuilding notes. Plus the book-level chat, which is an
// ordinary conversation whose parent is the book rather than a scene, so the
// AI answers about the whole manuscript with no scene in context.
import { useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { createConversation } from "../../api/conversations";
import { resourceContentUrl, type ResourceFile } from "../../api/resources";
import { getAI, listModels } from "../../api/settings";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { useToast } from "../../components/Toast";
import { Button } from "../../components/ui";
import { useBookConversations } from "../../queries/conversations";
import { useDeleteResource, useResources, useUploadResource } from "../../queries/resources";
import { ConversationModal } from "../conversation/ConversationModal";

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatWhen(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export default function ResourcesPage() {
  const { bookId = "" } = useParams();
  const toast = useToast();

  const resources = useResources(bookId);
  const threads = useBookConversations(bookId);
  const upload = useUploadResource(bookId);
  const remove = useDeleteResource(bookId);

  const fileInput = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<ResourceFile | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);

  const uploadFiles = (files: FileList | null) => {
    if (!files?.length) return;
    for (const file of Array.from(files)) {
      upload.mutate(file, {
        // The server suffixes on collision rather than overwriting, so say what
        // actually landed — the author needs to know it didn't replace.
        onSuccess: (saved) =>
          toast.success(
            saved.filename === file.name
              ? `Added ${saved.filename}`
              : `Added ${saved.filename} — ${file.name} was already here`,
          ),
        onError: (err) =>
          toast.error(
            err instanceof ApiError
              ? (err.detail.fields as Record<string, string> | undefined)?.file ?? `Couldn't add ${file.name}.`
              : `Couldn't add ${file.name}.`,
          ),
      });
    }
  };

  const startChat = async () => {
    try {
      const [ai, models] = await Promise.all([getAI(), listModels()]);
      const modelId = ai.chatDefaultModelId ?? ai.utilityModelId ?? models[0]?.id ?? null;
      if (!modelId) {
        toast.error("Add a model in Settings before chatting.");
        return;
      }
      const conv = await createConversation(bookId, {
        kind: "chat",
        parentType: "book",
        parentId: bookId,
        aiParticipant: { enabled: true, modelId },
      });
      setConversationId(conv.id);
    } catch {
      toast.error("Couldn't start a chat.");
    }
  };

  const files = resources.data ?? [];
  const conversations = threads.data ?? [];

  return (
    <div className="mx-auto max-w-[720px] px-6 py-6">
      <div className="mb-4 flex items-center justify-between rounded-card border border-line bg-surface px-4 py-3">
        <div>
          <h1 className="text-[20px] font-semibold text-ink">Resources</h1>
          <p className="mt-0.5 text-[0.75rem] text-ink-faint">
            Research, references and notes that live beside the book.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => void startChat()}>
            Chat
          </Button>
          <Button variant="primary" onClick={() => fileInput.current?.click()}>
            Upload file
          </Button>
        </div>
      </div>

      <input
        ref={fileInput}
        type="file"
        multiple
        className="hidden"
        onChange={(e) => {
          uploadFiles(e.target.files);
          e.target.value = "";
        }}
      />

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          uploadFiles(e.dataTransfer.files);
        }}
        className={`rounded-card border border-dashed px-4 py-6 text-center transition-colors ${
          dragging ? "border-accent bg-accent-wash" : "border-line bg-surface"
        }`}
      >
        <p className="text-[0.8125rem] text-ink-soft">
          {upload.isPending ? "Adding…" : "Drop files here, or use Upload file. Anything up to 25 MB."}
        </p>
      </div>

      {files.length === 0 ? (
        <div className="flex flex-col items-center gap-1 py-12 text-center">
          <p className="text-[0.875rem] text-ink-soft">Nothing here yet</p>
          <p className="text-[0.8125rem] text-ink-faint">
            Add the maps, timelines and research your book leans on — then ask the AI about them.
          </p>
        </div>
      ) : (
        <ul className="mt-4 space-y-1">
          {files.map((f) => (
            <li
              key={f.filename}
              className="flex items-center gap-3 rounded-control border border-line bg-surface px-3 py-2"
            >
              <a
                href={resourceContentUrl(bookId, f.filename)}
                className="min-w-0 flex-1 truncate text-[0.875rem] text-ink hover:text-accent"
                title={`Download ${f.filename}`}
              >
                {f.filename}
              </a>
              <span className="shrink-0 font-mono text-[0.75rem] text-ink-faint">{formatSize(f.sizeBytes)}</span>
              <span className="shrink-0 text-[0.75rem] text-ink-faint">{formatWhen(f.updatedAt)}</span>
              <button
                type="button"
                className="shrink-0 rounded-control px-1.5 py-0.5 text-[0.8125rem] text-ink-faint hover:bg-accent-wash hover:text-danger"
                title={`Delete ${f.filename}`}
                onClick={() => setPendingDelete(f)}
              >
                🗑
              </button>
            </li>
          ))}
        </ul>
      )}

      <section className="mt-8">
        <h2 className="mb-2 text-[0.75rem] uppercase tracking-[0.04em] text-ink-soft">Chats</h2>
        {conversations.length === 0 ? (
          <p className="text-[0.8125rem] text-ink-faint">
            No chats yet. Chat opens a conversation about the whole book, not one scene.
          </p>
        ) : (
          <ul className="space-y-1">
            {conversations.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  className="flex w-full items-center gap-2 rounded-control border border-line bg-surface px-3 py-2 text-left text-[0.875rem] hover:bg-accent-wash"
                  title={c.title}
                  onClick={() => setConversationId(c.id)}
                >
                  <span className="min-w-0 flex-1 truncate text-ink">{c.title}</span>
                  {c.pendingProposals > 0 && (
                    <span className="shrink-0 text-[0.75rem] text-attn">{c.pendingProposals}</span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {pendingDelete && (
        <ConfirmDialog
          title={`Delete ${pendingDelete.filename}?`}
          message="It moves to the book's .trash folder, so you can still recover it from there or from git."
          onConfirm={() => {
            const name = pendingDelete.filename;
            setPendingDelete(null);
            remove.mutate(name, {
              onSuccess: () => toast.success(`Deleted ${name}`),
              onError: () => toast.error(`Couldn't delete ${name}.`),
            });
          }}
          onCancel={() => setPendingDelete(null)}
        />
      )}

      {conversationId && (
        // No sceneId: this thread has no scene, and the modal's every scene-keyed
        // branch is already guarded on that being absent.
        <ConversationModal
          bookId={bookId}
          conversationId={conversationId}
          onClose={() => {
            setConversationId(null);
            void threads.refetch();
          }}
        />
      )}
    </div>
  );
}
