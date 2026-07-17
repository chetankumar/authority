// Scene Editor (doc 06 §9) — the room where the book gets written; everything else
// recedes. TipTap + tiptap-markdown on a 68ch Literata sheet; autosave (2s debounce +
// blur + route-leave, Ctrl/Cmd+S immediate); inline title; live word count; Prev/Next.
// Tool-panel AI buttons and the right-pane lists arrive with phases 6–7 (shown "soon").
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { EditorContent, useEditor, type Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Markdown } from "tiptap-markdown";

import { getBookUi, patchBookUi } from "../../api/books";
import { enrichSceneAuto, END_ID, START_ID, saveContent } from "../../api/scenes";
import { createConversation, runAiJob } from "../../api/conversations";
import { getAI, listModels } from "../../api/settings";
import type { Todo } from "../../api/todos";
import { ApiError } from "../../api/client";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { Button } from "../../components/ui";
import { useToast } from "../../components/Toast";
import { useBook } from "../../queries/books";
import { useScene, useUpdateScene } from "../../queries/scenes";
import { useSceneConversations } from "../../queries/conversations";
import { useJobs as useAiJobDefinitions } from "../../queries/settings";
import { usePatchBook } from "../../queries/structure";
import { useCreateSceneTodo, useDeleteTodo, useSceneTodos, useUpdateTodo } from "../../queries/todos";
import { SceneModal } from "../sceneModal/SceneModal";
import { ConversationModal } from "../conversation/ConversationModal";

type SaveState = { kind: "idle" } | { kind: "saving" } | { kind: "saved"; at: string } | { kind: "error" };

// tiptap-markdown augments editor.storage at runtime but ships no types for it.
const getMarkdown = (editor: Editor): string =>
  (editor.storage as unknown as { markdown: { getMarkdown(): string } }).markdown.getMarkdown();

export default function EditorPage() {
  const { bookId = "", sceneId = "" } = useParams();
  const navigate = useNavigate();
  const sceneQ = useScene(bookId, sceneId);
  const bookQ = useBook(bookId);
  const patchBook = usePatchBook(bookId);
  const updateScene = useUpdateScene(bookId);
  const toast = useToast();
  const aiJobs = useAiJobDefinitions();
  const notes = useSceneConversations(bookId, sceneId);
  const sceneTodos = useSceneTodos(bookId, sceneId);
  const createSceneTodo = useCreateSceneTodo(bookId, sceneId);
  const updateTodo = useUpdateTodo(bookId);
  const deleteTodo = useDeleteTodo(bookId);

  const [words, setWords] = useState(0);
  const [save, setSave] = useState<SaveState>({ kind: "idle" });
  const [paneOpen, setPaneOpen] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [createNext, setCreateNext] = useState(false);
  const [title, setTitle] = useState("");
  const [sourceMode, setSourceMode] = useState(false);
  const [sourceText, setSourceText] = useState("");
  const [jobsMenuOpen, setJobsMenuOpen] = useState(false);
  const [bookkeepingOpen, setBookkeepingOpen] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [chatContext, setChatContext] = useState<{ sceneId: string; excerpt: string } | null>(null);
  const [newTodoText, setNewTodoText] = useState("");
  const [confirmDeleteTodo, setConfirmDeleteTodo] = useState<Todo | null>(null);
  const sourceRef = useRef<HTMLTextAreaElement>(null);

  const loadedScene = useRef<string | null>(null);
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dirty = useRef(false);
  const sourceModeRef = useRef(false);
  const sourceTextRef = useRef("");
  const entryHash = useRef<string>("");
  const contentChangedThisVisit = useRef(false);
  const bookkeepingRef = useRef<HTMLDivElement>(null);

  const doSave = useCallback(
    async (markdown: string) => {
      dirty.current = false;
      setSave({ kind: "saving" });
      try {
        const res = await saveContent(bookId, sceneId, markdown);
        setWords(res.wordCount);
        if (res.contentHash !== entryHash.current) {
          contentChangedThisVisit.current = true;
        }
        setSave({ kind: "saved", at: new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) });
      } catch {
        setSave({ kind: "error" });
        // Back off and retry the current document.
        setTimeout(() => {
          if (editor) void doSave(getMarkdown(editor));
        }, 4000);
      }
    },
    [bookId, sceneId],
  );

  const editor = useEditor(
    {
      extensions: [StarterKit, Markdown.configure({ html: false, transformPastedText: true })],
      editorProps: { attributes: { class: "prose-sheet focus:outline-none" } },
      onUpdate: ({ editor }) => {
        setWords(editor.getText().trim() ? editor.getText().trim().split(/\s+/).length : 0);
        dirty.current = true;
        if (debounce.current) clearTimeout(debounce.current);
        debounce.current = setTimeout(() => void doSave(getMarkdown(editor)), 2000);
      },
      onBlur: ({ editor }) => {
        if (dirty.current) void doSave(getMarkdown(editor));
      },
    },
    [sceneId],
  );

  // Load content into the editor once per scene.
  // emitUpdate: false — TipTap's default setContent fires onUpdate, which would
  // mark dirty and autosave identical prose, bumping bookkeeping.updatedAt.
  useEffect(() => {
    if (editor && sceneQ.data && loadedScene.current !== sceneId) {
      loadedScene.current = sceneId;
      entryHash.current = sceneQ.data.contentHash;
      contentChangedThisVisit.current = false;
      dirty.current = false;
      if (debounce.current) clearTimeout(debounce.current);
      editor.commands.setContent(sceneQ.data.content || "", { emitUpdate: false });
      setTitle(sceneQ.data.title);
      setWords(sceneQ.data.wordCount);
      setSave({ kind: "idle" });
    }
  }, [editor, sceneQ.data, sceneId]);

  // Hydrate the right-pane preference from ui.json.
  useEffect(() => {
    void getBookUi(bookId).then((ui) => {
      if (typeof (ui as { editorPaneOpen?: boolean }).editorPaneOpen === "boolean") {
        setPaneOpen((ui as { editorPaneOpen: boolean }).editorPaneOpen);
      }
    });
  }, [bookId]);

  const leaveEnrich = useCallback(
    (opts?: { keepalive?: boolean }) => {
      if (!contentChangedThisVisit.current) return;
      contentChangedThisVisit.current = false;
      void enrichSceneAuto(bookId, sceneId, opts).catch(() => {
        /* leave-path: don't block navigation on enrich failure */
      });
    },
    [bookId, sceneId],
  );

  // Ctrl/Cmd+S = save now. Save + leave-enrich on unmount (route-leave).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        const md = sourceModeRef.current ? sourceTextRef.current : editor ? getMarkdown(editor) : null;
        if (md != null) void doSave(md);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      if (dirty.current) {
        contentChangedThisVisit.current = true;
        const md = sourceModeRef.current ? sourceTextRef.current : editor ? getMarkdown(editor) : null;
        if (md != null) void doSave(md);
      }
      leaveEnrich({ keepalive: true });
    };
  }, [editor, doSave, leaveEnrich]);

  // Close bookkeeping popover on outside click.
  useEffect(() => {
    if (!bookkeepingOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (bookkeepingRef.current && !bookkeepingRef.current.contains(e.target as Node)) {
        setBookkeepingOpen(false);
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [bookkeepingOpen]);

  sourceModeRef.current = sourceMode;
  sourceTextRef.current = sourceText;

  const toggleSource = () => {
    if (!editor) return;
    if (!sourceMode) {
      if (dirty.current) void doSave(getMarkdown(editor));
      setSourceText(getMarkdown(editor));
      setSourceMode(true);
      setTimeout(() => sourceRef.current?.focus(), 0);
    } else {
      editor.commands.setContent(sourceText);
      setSourceMode(false);
      dirty.current = true;
      if (debounce.current) clearTimeout(debounce.current);
      debounce.current = setTimeout(() => void doSave(sourceText), 2000);
    }
  };

  const onSourceChange = (value: string) => {
    setSourceText(value);
    const wc = value.trim() ? value.trim().split(/\s+/).length : 0;
    setWords(wc);
    dirty.current = true;
    if (debounce.current) clearTimeout(debounce.current);
    debounce.current = setTimeout(() => void doSave(value), 2000);
  };

  const togglePane = () => {
    setPaneOpen((o) => {
      const next = !o;
      void patchBookUi(bookId, { editorPaneOpen: next });
      return next;
    });
  };

  const commitTitle = () => {
    const t = title.trim();
    if (t && sceneQ.data && t !== sceneQ.data.title) updateScene.mutate({ sceneId, body: { title: t } });
  };

  const scene = sceneQ.data;
  const hasPrev = !!scene?.previousSceneId && scene.previousSceneId !== START_ID;
  const hasNext = !!scene?.nextSceneId && scene.nextSceneId !== END_ID;

  const flushBeforeNav = () => {
    if (dirty.current) {
      contentChangedThisVisit.current = true;
      const md = sourceMode ? sourceText : editor ? getMarkdown(editor) : null;
      if (md != null) void doSave(md);
    }
    leaveEnrich();
  };
  const goPrev = () => {
    flushBeforeNav();
    if (sourceMode) setSourceMode(false);
    if (hasPrev) navigate(`/book/${bookId}/scene/${scene!.previousSceneId}`);
  };
  const goNext = () => {
    flushBeforeNav();
    if (sourceMode) setSourceMode(false);
    if (hasNext) navigate(`/book/${bookId}/scene/${scene!.nextSceneId}`);
    else setCreateNext(true);
  };

  const getSelectionExcerpt = (): string | null => {
    if (sourceMode) {
      const el = sourceRef.current;
      if (!el || el.selectionStart === el.selectionEnd) return null;
      return sourceText.slice(el.selectionStart, el.selectionEnd);
    }
    const sel = window.getSelection()?.toString().trim();
    return sel || null;
  };

  const startChat = async () => {
    try {
      const excerpt = getSelectionExcerpt();
      const [ai, models] = await Promise.all([getAI(), listModels()]);
      const modelId = ai.chatDefaultModelId ?? ai.utilityModelId ?? models[0]?.id ?? null;
      if (!modelId) {
        toast.error("Add a model in Settings before chatting.");
        return;
      }
      const conv = await createConversation(bookId, {
        kind: "chat",
        parentType: "scene",
        parentId: sceneId,
        aiParticipant: { enabled: true, modelId },
      });
      setChatContext(excerpt ? { sceneId, excerpt } : null);
      setConversationId(conv.id);
    } catch {
      toast.error("Couldn't start a chat.");
    }
  };

  const openTodoConversation = async (t: Todo) => {
    if (t.conversationId) {
      setChatContext(null);
      setConversationId(t.conversationId);
      return;
    }
    try {
      const conv = await createConversation(bookId, { kind: "task-discussion", parentType: "scene", parentId: sceneId });
      await updateTodo.mutateAsync({ todoId: t.id, body: { conversationId: conv.id } });
      setChatContext(null);
      setConversationId(conv.id);
    } catch {
      toast.error("Couldn't start a conversation.");
    }
  };

  const addTodo = async () => {
    const action = newTodoText.trim();
    if (!action) return;
    try {
      await createSceneTodo.mutateAsync(action);
      setNewTodoText("");
    } catch {
      toast.error("Couldn't add that task.");
    }
  };

  const runJob = async (aiJobId: string) => {
    setJobsMenuOpen(false);
    try {
      const excerpt = getSelectionExcerpt();
      const res = await runAiJob(bookId, {
        aiJobId,
        sceneId,
        scope: excerpt ? "selection" : "full",
        selectionText: excerpt ?? undefined,
      });
      setChatContext(null);
      setConversationId(res.conversationId);
    } catch {
      toast.error("Couldn't run that job.");
    }
  };

  if (sceneQ.isLoading) return <div className="px-6 py-6 text-[0.875rem] text-ink-soft">Opening the scene…</div>;
  if (sceneQ.isError || !scene)
    return <div className="px-6 py-6 text-[0.875rem] text-danger">Couldn't open this scene.</div>;

  const jobDefs = aiJobs.data ?? [];
  // One conversation list, two panes. Notes = the author's own threads;
  // AI Jobs = the AI runs (an AI-Job's conversation, or a bookkeeping run).
  const allConvos = notes.data ?? [];
  const visibleNotes = allConvos.filter((n) => n.kind === "note" || n.kind === "chat");
  const runRows = allConvos.filter((n) => n.kind === "ai-job" || n.kind === "bookkeeping");
  const todoRows = sceneTodos.data ?? [];

  return (
    <div className="flex h-full min-h-0">
      {/* center column */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* tool panel */}
        <div className="relative flex items-center gap-2 border-b border-line px-4 py-2">
          <div className="relative">
            <ToolButton
              label="AI-Jobs ▾"
              onClick={() => setJobsMenuOpen((o) => !o)}
              disabled={jobDefs.length === 0}
              title={jobDefs.length === 0 ? "Define AI-Jobs in Settings first" : undefined}
            />
            {jobsMenuOpen && (
              <ul className="absolute left-0 top-full z-20 mt-1 min-w-[12rem] rounded-control border border-line bg-surface py-1 shadow-overlay">
                {jobDefs.map((j) => (
                  <li key={j.id}>
                    <button
                      type="button"
                      className="block w-full px-3 py-1.5 text-left text-[0.8125rem] hover:bg-accent-wash"
                      onClick={() => void runJob(j.id)}
                    >
                      {j.name}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <ToolButton label="Metadata" onClick={() => setModalOpen(true)} />
          <div className="relative" ref={bookkeepingRef}>
            <ToolButton
              label="Bookkeeping"
              onClick={() => setBookkeepingOpen((o) => !o)}
              title="Standing consent for AI summary and character updates"
            />
            {bookkeepingOpen && bookQ.data && (
              <div className="absolute left-0 top-full z-20 mt-1 w-[280px] rounded-control border border-line bg-surface p-3 shadow-overlay">
                <p className="mb-2 text-[0.75rem] font-medium text-ink">When leaving a scene</p>
                <label className="mb-2 flex items-start gap-2 text-[0.8125rem] text-ink">
                  <input
                    type="checkbox"
                    className="mt-0.5 accent-accent"
                    checked={bookQ.data.bookkeeping.summaryOnSave}
                    onChange={(e) => {
                      void patchBook.mutateAsync({
                        bookkeeping: {
                          summaryOnSave: e.target.checked,
                          charactersOnSave: bookQ.data.bookkeeping.charactersOnSave,
                        },
                      });
                    }}
                  />
                  <span>Update summary when leaving scene</span>
                </label>
                <label className="mb-3 flex items-start gap-2 text-[0.8125rem] text-ink">
                  <input
                    type="checkbox"
                    className="mt-0.5 accent-accent"
                    checked={bookQ.data.bookkeeping.charactersOnSave}
                    onChange={(e) => {
                      void patchBook.mutateAsync({
                        bookkeeping: {
                          summaryOnSave: bookQ.data.bookkeeping.summaryOnSave,
                          charactersOnSave: e.target.checked,
                        },
                      });
                    }}
                  />
                  <span>Update character involvement when leaving scene</span>
                </label>
                <p className="text-[0.6875rem] text-ink-faint">Applies to this whole book</p>
              </div>
            )}
          </div>
          <ToolButton label="Chat" onClick={() => void startChat()} />
          <div className="ml-auto">
            <ToolButton label="◫" onClick={togglePane} title="Toggle side pane" />
          </div>
        </div>

        {/* TipTap toolbar */}
        {editor && (
          <div className="flex items-center gap-1 border-b border-line px-4 py-1.5 text-[0.8125rem]">
            {!sourceMode && (
              <>
                <MarkButton editor={editor} label="B" cmd={() => editor.chain().focus().toggleBold().run()} active={editor.isActive("bold")} />
                <MarkButton editor={editor} label="I" cmd={() => editor.chain().focus().toggleItalic().run()} active={editor.isActive("italic")} />
                <MarkButton editor={editor} label="H₁" cmd={() => editor.chain().focus().toggleHeading({ level: 1 }).run()} active={editor.isActive("heading", { level: 1 })} />
                <MarkButton editor={editor} label="H₂" cmd={() => editor.chain().focus().toggleHeading({ level: 2 }).run()} active={editor.isActive("heading", { level: 2 })} />
                <MarkButton editor={editor} label="❝" cmd={() => editor.chain().focus().toggleBlockquote().run()} active={editor.isActive("blockquote")} />
                <MarkButton editor={editor} label="•" cmd={() => editor.chain().focus().toggleBulletList().run()} active={editor.isActive("bulletList")} />
              </>
            )}
            {sourceMode && <span className="text-[0.75rem] text-ink-faint">Markdown source</span>}
            <div className="ml-auto">
              <MarkButton editor={editor} label="&lt;&gt;" cmd={toggleSource} active={sourceMode} />
            </div>
          </div>
        )}

        {/* sheet */}
        <div className="min-h-0 flex-1 overflow-auto bg-paper px-6 py-10">
          <div className="mx-auto w-full" style={{ maxWidth: "68ch" }}>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              onBlur={commitTitle}
              onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
              className="mb-6 w-full bg-transparent font-prose text-[1.75rem] font-semibold text-ink outline-none"
            />
            {sourceMode ? (
              <textarea
                ref={sourceRef}
                value={sourceText}
                onChange={(e) => onSourceChange(e.target.value)}
                onBlur={() => { if (dirty.current) void doSave(sourceText); }}
                className="min-h-[60vh] w-full resize-none bg-transparent font-mono text-[0.875rem] leading-relaxed text-ink outline-none"
                spellCheck={false}
              />
            ) : (
              <EditorContent editor={editor} />
            )}
          </div>
        </div>

        {/* status bar */}
        <div className="flex items-center justify-between border-t border-line px-6 py-2 text-[0.8125rem] text-ink-soft">
          <span className="font-mono">
            {words.toLocaleString()} words
            <span className="ml-3">{saveLabel(save)}</span>
          </span>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={goPrev} disabled={!hasPrev} title={hasPrev ? undefined : "This is the first scene"}>
              ← Previous
            </Button>
            <Button variant="secondary" onClick={goNext}>
              {hasNext ? "Next →" : "New next scene →"}
            </Button>
          </div>
        </div>
      </div>

      {/* right pane */}
      {paneOpen && (
        <aside className="w-80 shrink-0 overflow-auto border-l border-line bg-surface p-4">
          <PaneSection title="Notes" count={visibleNotes.length}>
            {visibleNotes.length === 0 ? (
              <p className="text-[0.75rem] text-ink-faint">No notes yet.</p>
            ) : (
              <ul className="space-y-1">
                {visibleNotes.map((n) => (
                  <li key={n.id}>
                    <button
                      type="button"
                      className="flex w-full items-center gap-2 rounded-control px-2 py-1 text-left text-[0.8125rem] text-ink-soft hover:bg-accent-wash"
                      title={n.title}
                      onClick={() => {
                        setChatContext(null);
                        setConversationId(n.id);
                      }}
                    >
                      <span className="min-w-0 flex-1 truncate text-ink">{n.title}</span>
                      {n.pendingProposals > 0 && (
                        <span className="shrink-0 text-[0.6875rem] text-attn">{n.pendingProposals}</span>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </PaneSection>
          <PaneSection title="To-dos" count={todoRows.filter((t) => t.status === "open").length}>
            <div className="mb-2 flex items-center gap-1">
              <input
                value={newTodoText}
                onChange={(e) => setNewTodoText(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && void addTodo()}
                placeholder="Add a task for this scene…"
                className="h-7 min-w-0 flex-1 rounded-control border border-line bg-paper px-2 text-[0.75rem] text-ink outline-none focus:border-accent"
              />
              <button
                onClick={() => void addTodo()}
                disabled={!newTodoText.trim()}
                className="h-7 rounded-control px-2 text-[0.75rem] text-ink-soft hover:bg-accent-wash disabled:opacity-40"
              >
                Add
              </button>
            </div>
            {todoRows.length === 0 ? (
              <p className="text-[0.75rem] text-ink-faint">No tasks yet.</p>
            ) : (
              <ul className="space-y-1">
                {todoRows.map((t) => {
                  const dependency = t.origin === "dependency";
                  return (
                    <li
                      key={t.id}
                      className={`flex items-center gap-1.5 rounded-control px-1.5 py-1 text-[0.8125rem] ${dependency ? "bg-attn-wash" : ""}`}
                    >
                      <input
                        type="checkbox"
                        className="accent-accent"
                        checked={t.status === "done"}
                        title={t.status === "done" ? "Mark open" : "Mark done"}
                        onChange={(e) => updateTodo.mutate({ todoId: t.id, body: { status: e.target.checked ? "done" : "open" } })}
                      />
                      {dependency && <span title="From a dependency" className="text-attn">⛓</span>}
                      <span
                        className={`min-w-0 flex-1 truncate ${t.status !== "open" ? "text-ink-faint line-through" : "text-ink"}`}
                        title={t.action}
                      >
                        {t.action}
                      </span>
                      <button title="Open conversation" onClick={() => void openTodoConversation(t)} className="shrink-0 rounded px-1 text-ink-soft hover:bg-accent-wash">
                        💬
                      </button>
                      {t.status === "open" && (
                        <button
                          title="Close (not applicable)"
                          onClick={() => updateTodo.mutate({ todoId: t.id, body: { status: "closed" } })}
                          className="shrink-0 rounded px-1 text-ink-soft hover:bg-accent-wash"
                        >
                          ✕
                        </button>
                      )}
                      <button title="Delete" onClick={() => setConfirmDeleteTodo(t)} className="shrink-0 rounded px-1 text-danger hover:bg-danger-wash">
                        🗑
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </PaneSection>
          <PaneSection
            title="AI Jobs"
            count={runRows.filter((r) => r.status === "queued" || r.status === "running" || r.status === "waiting").length}
          >
            {runRows.length === 0 ? (
              <p className="text-[0.75rem] text-ink-faint">No jobs yet.</p>
            ) : (
              <ul className="space-y-1">
                {runRows.slice(0, 20).map((r) => (
                  <li key={r.id}>
                    <button
                      type="button"
                      className="flex w-full items-center gap-2 rounded-control px-2 py-1 text-left text-[0.8125rem] text-ink-soft hover:bg-accent-wash"
                      title={r.title}
                      onClick={() => {
                        setChatContext(null);
                        setConversationId(r.id);
                      }}
                    >
                      <span className="min-w-0 flex-1 truncate text-ink">{r.title}</span>
                      <span
                        className={`shrink-0 text-[0.6875rem] ${r.status === "waiting" ? "text-attn" : "text-ink-faint"}`}
                      >
                        {r.status === "waiting" ? "needs you" : r.status}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </PaneSection>
        </aside>
      )}

      {modalOpen && <SceneModal bookId={bookId} sceneId={sceneId} onClose={() => setModalOpen(false)} />}
      {createNext && (
        <SceneModal
          bookId={bookId}
          sceneId={null}
          initialPrevious={sceneId}
          onClose={() => setCreateNext(false)}
          onSaved={(s) => navigate(`/book/${bookId}/scene/${s.id}`)}
        />
      )}
      {conversationId && (
        <ConversationModal
          bookId={bookId}
          conversationId={conversationId}
          sceneId={sceneId}
          initialContext={chatContext}
          onClose={() => {
            setConversationId(null);
            setChatContext(null);
            void notes.refetch();
          }}
        />
      )}
      {confirmDeleteTodo && (
        <ConfirmDialog
          title="Delete this task?"
          message="This removes the task permanently. If it's just no longer applicable, Close it instead — that keeps a record."
          confirmLabel="Delete task"
          onConfirm={async () => {
            try {
              await deleteTodo.mutateAsync(confirmDeleteTodo.id);
            } catch (e) {
              toast.error(e instanceof ApiError ? e.message : "Couldn't delete the task.");
            }
            setConfirmDeleteTodo(null);
          }}
          onCancel={() => setConfirmDeleteTodo(null)}
        />
      )}
    </div>
  );
}

function saveLabel(s: SaveState): string {
  if (s.kind === "saving") return "· Saving…";
  if (s.kind === "saved") return `· Saved ${s.at}`;
  if (s.kind === "error") return "· Not saved — retrying";
  return "";
}

function ToolButton({ label, onClick, disabled, soon, title }: { label: string; onClick?: () => void; disabled?: boolean; soon?: boolean; title?: string }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title ?? (soon ? "Arrives in a later phase" : undefined)}
      className={`rounded-control px-2.5 py-1 text-[0.8125rem] ${disabled ? "cursor-not-allowed text-ink-faint" : "text-ink-soft hover:bg-accent-wash"}`}
    >
      {label}
      {soon && <span className="ml-1 text-[0.625rem] text-ink-faint">soon</span>}
    </button>
  );
}

function MarkButton({ label, cmd, active }: { editor: unknown; label: string; cmd: () => void; active: boolean }) {
  return (
    <button
      onMouseDown={(e) => {
        e.preventDefault();
        cmd();
      }}
      className={`h-7 min-w-7 rounded-control px-1.5 ${active ? "bg-accent-wash text-accent" : "text-ink-soft hover:bg-accent-wash"}`}
    >
      {label}
    </button>
  );
}

function PaneSection({
  title,
  count,
  children,
}: {
  title: string;
  count?: number;
  children?: ReactNode;
}) {
  return (
    <div className="mb-4 border-b border-line pb-3">
      <div className="mb-2 flex items-center justify-between py-1 text-[0.8125rem] text-ink-soft">
        <span>{title}</span>
        {typeof count === "number" && count > 0 && (
          <span className="rounded-full bg-attn-wash px-1.5 text-[0.6875rem] text-attn">{count}</span>
        )}
      </div>
      {children}
    </div>
  );
}
