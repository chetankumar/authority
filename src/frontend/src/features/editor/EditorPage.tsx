// Scene Editor (doc 06 §9) — the room where the book gets written; everything else
// recedes. TipTap + tiptap-markdown on a 68ch Literata sheet; autosave (2s debounce +
// blur + route-leave, Ctrl/Cmd+S immediate); inline title; live word count; Prev/Next.
// Tool-panel AI buttons and the right-pane lists arrive with phases 6–7 (shown "soon").
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { EditorContent, useEditor, type Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Markdown } from "tiptap-markdown";

import { getBookUi, patchBookUi } from "../../api/books";
import { END_ID, START_ID } from "../../api/scenes";
import { Button } from "../../components/ui";
import { useScene, useUpdateScene } from "../../queries/scenes";
import { saveContent } from "../../api/scenes";
import { SceneModal } from "../sceneModal/SceneModal";

type SaveState = { kind: "idle" } | { kind: "saving" } | { kind: "saved"; at: string } | { kind: "error" };

// tiptap-markdown augments editor.storage at runtime but ships no types for it.
const getMarkdown = (editor: Editor): string =>
  (editor.storage as unknown as { markdown: { getMarkdown(): string } }).markdown.getMarkdown();

export default function EditorPage() {
  const { bookId = "", sceneId = "" } = useParams();
  const navigate = useNavigate();
  const sceneQ = useScene(bookId, sceneId);
  const updateScene = useUpdateScene(bookId);

  const [words, setWords] = useState(0);
  const [save, setSave] = useState<SaveState>({ kind: "idle" });
  const [paneOpen, setPaneOpen] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [createNext, setCreateNext] = useState(false);
  const [title, setTitle] = useState("");

  const loadedScene = useRef<string | null>(null);
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dirty = useRef(false);

  const doSave = useCallback(
    async (markdown: string) => {
      dirty.current = false;
      setSave({ kind: "saving" });
      try {
        const res = await saveContent(bookId, sceneId, markdown);
        setWords(res.wordCount);
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
  useEffect(() => {
    if (editor && sceneQ.data && loadedScene.current !== sceneId) {
      loadedScene.current = sceneId;
      editor.commands.setContent(sceneQ.data.content || "");
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

  // Ctrl/Cmd+S = save now. Save on unmount (route-leave).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        if (editor) void doSave(getMarkdown(editor));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      if (editor && dirty.current) void doSave(getMarkdown(editor));
    };
  }, [editor, doSave]);

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

  const goPrev = () => {
    if (editor && dirty.current) void doSave(getMarkdown(editor));
    if (hasPrev) navigate(`/book/${bookId}/scene/${scene!.previousSceneId}`);
  };
  const goNext = () => {
    if (editor && dirty.current) void doSave(getMarkdown(editor));
    if (hasNext) navigate(`/book/${bookId}/scene/${scene!.nextSceneId}`);
    else setCreateNext(true); // create-with-previous flow
  };

  if (sceneQ.isLoading) return <div className="px-6 py-6 text-[0.875rem] text-ink-soft">Opening the scene…</div>;
  if (sceneQ.isError || !scene)
    return <div className="px-6 py-6 text-[0.875rem] text-danger">Couldn't open this scene.</div>;

  return (
    <div className="flex h-full min-h-0">
      {/* center column */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* tool panel */}
        <div className="flex items-center gap-2 border-b border-line px-4 py-2">
          <ToolButton disabled label="AI-Jobs ▾" soon />
          <ToolButton label="Metadata" onClick={() => setModalOpen(true)} />
          <ToolButton disabled label="Bookkeeping" soon />
          <ToolButton disabled label="Chat" soon />
          <div className="ml-auto">
            <ToolButton label="◫" onClick={togglePane} title="Toggle side pane" />
          </div>
        </div>

        {/* TipTap toolbar */}
        {editor && (
          <div className="flex items-center gap-1 border-b border-line px-4 py-1.5 text-[0.8125rem]">
            <MarkButton editor={editor} label="B" cmd={() => editor.chain().focus().toggleBold().run()} active={editor.isActive("bold")} />
            <MarkButton editor={editor} label="I" cmd={() => editor.chain().focus().toggleItalic().run()} active={editor.isActive("italic")} />
            <MarkButton editor={editor} label="H₁" cmd={() => editor.chain().focus().toggleHeading({ level: 1 }).run()} active={editor.isActive("heading", { level: 1 })} />
            <MarkButton editor={editor} label="H₂" cmd={() => editor.chain().focus().toggleHeading({ level: 2 }).run()} active={editor.isActive("heading", { level: 2 })} />
            <MarkButton editor={editor} label="❝" cmd={() => editor.chain().focus().toggleBlockquote().run()} active={editor.isActive("blockquote")} />
            <MarkButton editor={editor} label="•" cmd={() => editor.chain().focus().toggleBulletList().run()} active={editor.isActive("bulletList")} />
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
            <EditorContent editor={editor} />
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
          <PaneSection title="Notes" />
          <PaneSection title="To-dos" />
          <PaneSection title="AI Jobs" />
          <p className="mt-4 text-[0.75rem] text-ink-faint">
            Notes, to-dos and AI jobs light up with the AI and structure phases.
          </p>
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

function PaneSection({ title }: { title: string }) {
  return (
    <div className="mb-2 border-b border-line pb-2">
      <div className="flex items-center justify-between py-1 text-[0.8125rem] text-ink-soft">
        <span>{title}</span>
        <span className="text-[0.625rem] text-ink-faint">soon</span>
      </div>
    </div>
  );
}
