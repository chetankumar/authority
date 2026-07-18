import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import {
  deleteConversation,
  getConversation,
  patchConversation,
  sendMessageStream,
  type Conversation,
  type Message,
  type Proposal,
} from "../../api/conversations";
import { acceptProposal, rejectProposal } from "../../api/proposals";
import { listModels, type ModelConfig } from "../../api/settings";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { Modal } from "../../components/Modal";
import { Button } from "../../components/ui";
import { useToast } from "../../components/Toast";
import { keys } from "../../queries/keys";

export function ConversationModal({
  bookId,
  conversationId,
  sceneId,
  initialContext,
  onClose,
}: {
  bookId: string;
  conversationId: string;
  sceneId?: string;
  initialContext?: { sceneId: string; excerpt: string } | null;
  onClose: () => void;
}) {
  const toast = useToast();
  const qc = useQueryClient();
  const [conv, setConv] = useState<Conversation | null>(null);
  const [titleDraft, setTitleDraft] = useState("");
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPrompt, setShowPrompt] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const pendingContext = useRef(initialContext ?? null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<(() => void) | null>(null);
  const titleFocused = useRef(false);

  useEffect(() => {
    void getConversation(bookId, conversationId).then((c) => {
      setConv(c);
      setTitleDraft(c.title);
      // A fresh AI-Job run arrives at `open` with its prompt already inside
      // and nothing sent. Prefill "start" so approving it is just hitting
      // Send — edit the box first if you'd rather add instructions.
      if (c.kind === "ai-job" && c.status === "open" && !c.messages.some((m) => m.author === "user")) {
        setDraft("start");
      }
    });
    void listModels().then(setModels);
    return () => abortRef.current?.();
  }, [bookId, conversationId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conv?.messages, streaming]);

  // A bookkeeping run is driven by the background worker, not by this modal —
  // so if the author opens it mid-run, nothing here would notice it finishing.
  // (The `conversation` SSE event refreshes the pane's list, but the modal
  // reads its own copy.) Poll only while it's actually in flight; the terminal
  // statuses need no watching.
  useEffect(() => {
    if (!conv || busy) return;
    const inFlight = conv.status === "queued" || conv.status === "running";
    if (!inFlight) return;
    const t = setTimeout(() => void refresh(), 2000);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conv, busy]);

  function applyTitle(title: string) {
    if (titleFocused.current) return;
    setTitleDraft(title);
    setConv((c) => (c ? { ...c, title } : c));
  }

  async function refresh() {
    const c = await getConversation(bookId, conversationId);
    setConv(c);
    if (!titleFocused.current) setTitleDraft(c.title);
    if (sceneId) void qc.invalidateQueries({ queryKey: keys.conversations(bookId, sceneId) });
  }

  async function onTitleBlur() {
    titleFocused.current = false;
    if (!conv) return;
    const title = titleDraft.trim() || conv.title;
    setTitleDraft(title);
    if (title === conv.title) return;
    const updated = await patchConversation(bookId, conversationId, { title });
    setConv(updated);
    setTitleDraft(updated.title);
  }

  async function toggleAi(enabled: boolean) {
    if (!conv) return;
    try {
      const modelId = conv.aiParticipant.modelId ?? models[0]?.id ?? null;
      if (enabled && !modelId) {
        setError("Pick a model to bring the AI in.");
        return;
      }
      const updated = await patchConversation(bookId, conversationId, {
        aiParticipant: { enabled, modelId },
      });
      setConv(updated);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't update AI participant.");
    }
  }

  async function setModel(modelId: string) {
    if (!conv) return;
    const updated = await patchConversation(bookId, conversationId, {
      aiParticipant: { enabled: conv.aiParticipant.enabled, modelId },
    });
    setConv(updated);
  }

  function send() {
    const content = draft.trim();
    if (!content || busy || !conv) return;
    setBusy(true);
    setError(null);
    setStreaming("");
    setDraft("");
    const context = pendingContext.current ? [pendingContext.current] : undefined;
    pendingContext.current = null;

    abortRef.current = sendMessageStream(
      bookId,
      conversationId,
      { content, context },
      {
        onToken: (t) => setStreaming((s) => s + t),
        onTitle: (title) => applyTitle(title),
        onMessage: (msg) => {
          if (msg.author === "user") {
            setConv((c) => (c ? { ...c, messages: [...c.messages, msg] } : c));
          } else {
            setStreaming("");
            setConv((c) => (c ? { ...c, messages: [...c.messages, msg] } : c));
          }
        },
        onError: (e) => {
          setError(e);
          setBusy(false);
        },
        onDone: () => {
          setBusy(false);
          setStreaming("");
          void refresh();
        },
      },
    );
  }

  async function onDelete() {
    setDeleting(true);
    try {
      await deleteConversation(bookId, conversationId);
      if (sceneId) void qc.invalidateQueries({ queryKey: keys.conversations(bookId, sceneId) });
      onClose();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Couldn't delete conversation.");
      setConfirmDelete(false);
      setDeleting(false);
    }
  }

  async function onAccept(p: Proposal) {
    try {
      const res = await acceptProposal(bookId, p.id);
      if (res.proposal.status === "not-found") {
        toast.error("This text is no longer in the scene.");
      } else {
        toast.success("Proposal applied");
      }
      await refresh();
      if (sceneId) void qc.invalidateQueries({ queryKey: keys.scene(bookId, sceneId) });
      void qc.invalidateQueries({ queryKey: keys.scenes(bookId) });
      void qc.invalidateQueries({ queryKey: keys.resources(bookId) });
      if (p.type === "audio-script-create" && sceneId) {
        void qc.invalidateQueries({ queryKey: keys.audio(bookId, sceneId) });
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Couldn't accept.");
    }
  }

  async function onReject(p: Proposal) {
    await rejectProposal(bookId, p.id);
    await refresh();
  }

  async function acceptAll(pending: Proposal[]) {
    for (const p of pending) {
      const res = await acceptProposal(bookId, p.id);
      if (res.proposal.status === "not-found") {
        toast.error("A proposal's text is no longer in the scene.");
        break;
      }
    }
    await refresh();
    if (sceneId) void qc.invalidateQueries({ queryKey: keys.scene(bookId, sceneId) });
    void qc.invalidateQueries({ queryKey: keys.resources(bookId) });
    if (sceneId && pending.some((p) => p.type === "audio-script-create")) {
      void qc.invalidateQueries({ queryKey: keys.audio(bookId, sceneId) });
    }
  }

  if (!conv) {
    return (
      <Modal title="Conversation" width={800} onClose={onClose}>
        <p className="text-[0.875rem] text-ink-soft">Loading…</p>
      </Modal>
    );
  }

  // On a run, the first system message is the resolved prompt — collapse just
  // that one behind "Job prompt · show". Every other system message (an
  // escalation question, an error) is content the author needs to read, so it
  // renders plainly.
  const isRun = conv.kind === "ai-job" || conv.kind === "bookkeeping";
  const promptMessageId = isRun
    ? conv.messages.find((m) => m.author === "system")?.id
    : undefined;

  return (
    <>
      <Modal
        title=""
        width={800}
        onClose={onClose}
        footer={
          <div className="flex w-full flex-col gap-2">
            {error && <p className="text-[0.8125rem] text-danger">{error}</p>}
            <div className="flex gap-2">
              <textarea
                value={draft}
                rows={2}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    send();
                  }
                }}
                placeholder="Write a note or ask the AI…"
                className="min-h-[2.5rem] flex-1 rounded-control border border-line bg-surface px-3 py-2 text-[0.875rem] text-ink outline-none focus:border-accent"
                disabled={busy}
              />
              <Button variant="primary" onClick={send} disabled={busy || !draft.trim()}>
                {busy ? "…" : "Send"}
              </Button>
            </div>
          </div>
        }
      >
        <div className="flex max-h-[60vh] flex-col">
          <div className="mb-3 flex flex-wrap items-center gap-3 border-b border-line pb-3">
            <input
              value={titleDraft}
              title={titleDraft}
              onFocus={() => {
                titleFocused.current = true;
              }}
              onChange={(e) => setTitleDraft(e.target.value)}
              onBlur={() => void onTitleBlur()}
              className="min-w-0 flex-1 truncate bg-transparent text-[1rem] font-semibold text-ink outline-none focus:overflow-visible focus:text-clip"
            />
            <label className="flex items-center gap-2 text-[0.8125rem] text-ink-soft">
              <input
                type="checkbox"
                checked={conv.aiParticipant.enabled}
                onChange={(e) => void toggleAi(e.target.checked)}
              />
              AI
            </label>
            <select
              value={conv.aiParticipant.modelId ?? ""}
              onChange={(e) => void setModel(e.target.value)}
              className="rounded-control border border-line bg-surface px-2 py-1 text-[0.8125rem]"
            >
              <option value="">Model…</option>
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </select>
            <Button variant="ghost" onClick={() => setConfirmDelete(true)} disabled={busy || deleting}>
              Delete
            </Button>
          </div>

          <div className="min-h-0 flex-1 space-y-3 overflow-auto pr-1">
            {conv.messages.map((m) => (
              <MessageBubble
                key={m.id}
                message={m}
                isPrompt={m.id === promptMessageId}
                showPrompt={showPrompt}
                onTogglePrompt={() => setShowPrompt((s) => !s)}
                onAccept={onAccept}
                onReject={onReject}
                onAcceptAll={acceptAll}
              />
            ))}
            {streaming && (
              <div className="rounded-control bg-paper px-3 py-2 text-[0.875rem] text-ink">
                {streaming}
                <span className="ml-0.5 inline-block h-3 w-1 animate-pulse bg-accent" />
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        </div>
      </Modal>

      {confirmDelete && (
        <ConfirmDialog
          title="Delete this conversation?"
          message="This can't be undone. The thread and any pending proposals will be removed."
          confirmLabel={deleting ? "Deleting…" : "Delete"}
          onConfirm={() => void onDelete()}
          onCancel={() => !deleting && setConfirmDelete(false)}
        />
      )}
    </>
  );
}

function MessageBubble({
  message,
  isPrompt,
  showPrompt,
  onTogglePrompt,
  onAccept,
  onReject,
  onAcceptAll,
}: {
  message: Message;
  isPrompt: boolean;
  showPrompt: boolean;
  onTogglePrompt: () => void;
  onAccept: (p: Proposal) => void;
  onReject: (p: Proposal) => void;
  onAcceptAll: (ps: Proposal[]) => void;
}) {
  if (message.author === "system") {
    // The run's resolved prompt is long and boring — collapse it.
    if (isPrompt) {
      return (
        <div className="text-[0.8125rem] text-ink-faint">
          <button type="button" onClick={onTogglePrompt} className="underline">
            Job prompt · {showPrompt ? "hide" : "show"}
          </button>
          {showPrompt && (
            <pre className="mt-2 whitespace-pre-wrap rounded-control border border-line bg-paper p-2 font-mono text-[0.75rem] text-ink-soft">
              {message.content}
            </pre>
          )}
        </div>
      );
    }
    // An escalation question or an error the AI (or the system) put in the
    // thread — the author needs to actually see this one.
    return (
      <div className="rounded-control border border-line bg-paper px-3 py-2 text-[0.8125rem] text-ink-soft">
        <div className="whitespace-pre-wrap">{message.content}</div>
      </div>
    );
  }

  const isUser = message.author === "user";
  const pending = message.proposals.filter((p) => p.status === "pending");

  return (
    <div className={isUser ? "ml-8" : "mr-8"}>
      {!isUser && message.modelId && (
        <div className="mb-1 text-[0.6875rem] text-ink-faint">{message.modelId}</div>
      )}
      <div
        className={[
          "rounded-control px-3 py-2 text-[0.875rem]",
          isUser ? "bg-accent-wash text-ink" : "bg-paper text-ink",
        ].join(" ")}
      >
        {message.context.map((c, i) => (
          <blockquote
            key={i}
            className="mb-2 border-l-2 border-line pl-2 text-[0.8125rem] text-ink-soft"
          >
            From {c.sceneId}: {c.excerpt}
          </blockquote>
        ))}
        <div className="whitespace-pre-wrap">{message.content}</div>
      </div>
      {message.proposals.length > 0 && (
        <div className="mt-2 space-y-2">
          {message.proposals.map((p) => (
            <ProposalCard key={p.id} proposal={p} onAccept={onAccept} onReject={onReject} />
          ))}
          {pending.length > 1 && (
            <Button variant="secondary" onClick={() => onAcceptAll(pending)}>
              Accept all ({pending.length})
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

function ProposalCard({
  proposal,
  onAccept,
  onReject,
}: {
  proposal: Proposal;
  onAccept: (p: Proposal) => void;
  onReject: (p: Proposal) => void;
}) {
  const p = proposal.payload;
  const pending = proposal.status === "pending";
  const wash =
    proposal.status === "applied"
      ? "border-ok bg-ok-wash"
      : proposal.status === "not-found"
        ? "border-attn bg-attn-wash"
        : proposal.status === "rejected"
          ? "border-line opacity-60"
          : "border-attn bg-attn-wash";

  return (
    <div className={`rounded-control border p-3 text-[0.8125rem] ${wash}`}>
      {proposal.type === "edit" && (
        <div>
          <span className="line-through text-ink-soft">{String(p.find ?? "")}</span>
          <span className="mx-2">→</span>
          <span className="font-medium">{String(p.replace ?? "")}</span>
          {p.rationale ? <p className="mt-1 text-ink-faint">{String(p.rationale)}</p> : null}
        </div>
      )}
      {proposal.type === "metadata-update" && (
        <div>
          <span className="font-mono">{String(p.field)}</span>:{" "}
          <span className="line-through text-ink-soft">{String(p.oldValue ?? "…")}</span>
          <span className="mx-1">→</span>
          <strong>{String(p.newValue ?? "")}</strong>
        </div>
      )}
      {proposal.type === "todo-create" && <div>☐ {String(p.action ?? "")}</div>}
      {proposal.type === "character-create" && (
        <div>
          Add character <strong>{String(p.name ?? "")}</strong>
          {p.rationale ? <p className="mt-1 text-ink-faint">{String(p.rationale)}</p> : null}
        </div>
      )}
      {proposal.type === "resource-create" && (
        <div>
          <div>
            New resource file <span className="font-mono font-medium">{String(p.filename ?? "")}</span>
          </div>
          {/* The whole file, scrollable: nothing is written until Accept, so this
              preview is the author's only look at it before it lands. */}
          <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-control border border-line bg-surface p-2 font-mono text-[0.75rem] text-ink-soft">
            {String(p.content ?? "")}
          </pre>
          {p.rationale ? <p className="mt-1 text-ink-faint">{String(p.rationale)}</p> : null}
        </div>
      )}
      {proposal.type === "audio-script-create" && <AudioScriptProposalBody payload={p} />}
      {proposal.status === "not-found" && (
        <p className="mt-1 text-attn">This text is no longer in the scene.</p>
      )}
      {proposal.status === "applied" && <p className="mt-1 text-ok">✓ Applied</p>}
      {pending && (
        <div className="mt-2 flex gap-2">
          <Button variant="ghost" onClick={() => onReject(proposal)}>
            Reject
          </Button>
          <Button variant="primary" onClick={() => onAccept(proposal)}>
            Accept
          </Button>
        </div>
      )}
    </div>
  );
}

const AUDIO_STATUS_BADGE: Record<string, string> = {
  new: "bg-attn-wash text-attn",
  regenerate: "bg-attn-wash text-attn",
  unchanged: "bg-ok-wash text-ok",
};

function AudioScriptProposalBody({ payload }: { payload: Record<string, unknown> }) {
  const manifest = payload.manifest as
    | { title?: string; sequence?: Array<Record<string, unknown>> }
    | undefined;
  const sequence = Array.isArray(manifest?.sequence) ? manifest.sequence : [];
  const title = typeof manifest?.title === "string" ? manifest.title : "Audio script";

  return (
    <div>
      <div className="font-medium">{title}</div>
      <p className="mt-0.5 text-ink-faint">
        {sequence.length} line{sequence.length === 1 ? "" : "s"} — Accept merges into the scene
        manifest (unchanged lines keep existing audio).
      </p>
      {payload.rationale ? <p className="mt-1 text-ink-faint">{String(payload.rationale)}</p> : null}
      {sequence.length > 0 && (
        <div className="mt-2 max-h-72 overflow-auto rounded-control border border-line">
          <table className="w-full text-left text-[0.75rem]">
            <thead className="sticky top-0 bg-surface text-ink-faint">
              <tr>
                <th className="px-2 py-1 font-medium">#</th>
                <th className="px-2 py-1 font-medium">Speaker</th>
                <th className="px-2 py-1 font-medium">Type</th>
                <th className="px-2 py-1 font-medium">Status</th>
                <th className="px-2 py-1 font-medium">Text</th>
              </tr>
            </thead>
            <tbody>
              {sequence.map((item, i) => {
                const status = String(item.generation_status ?? "new");
                const badge = AUDIO_STATUS_BADGE[status] ?? "bg-surface-2 text-ink-soft";
                return (
                  <tr key={String(item.id ?? i)} className="border-t border-line align-top">
                    <td className="px-2 py-1 text-ink-faint">{i + 1}</td>
                    <td className="px-2 py-1">{String(item.speaker ?? item.speaker_id ?? "—")}</td>
                    <td className="px-2 py-1">{String(item.type ?? "")}</td>
                    <td className="px-2 py-1">
                      <span className={`inline-block rounded px-1.5 py-0.5 ${badge}`}>{status}</span>
                    </td>
                    <td className="max-w-[20rem] px-2 py-1 whitespace-pre-wrap text-ink-soft">
                      {String(item.text ?? "")}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
