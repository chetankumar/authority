// Tasks page (doc 06 §13) — one ledger of everything owed, book-wide.
// Book-level todos (chapter/part/book-parented) by default; a persistent
// toggle (ui.json) also pulls in every scene's todos.
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { AgGridReact } from "ag-grid-react";
import { AllCommunityModule, ModuleRegistry, themeQuartz, type ColDef } from "ag-grid-community";

import { createConversation } from "../../api/conversations";
import { getBookUi, patchBookUi } from "../../api/books";
import { ApiError } from "../../api/client";
import type { ParentType, Todo } from "../../api/todos";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { SearchableSelect } from "../../components/SearchableSelect";
import { useToast } from "../../components/Toast";
import { Button } from "../../components/ui";
import { keys } from "../../queries/keys";
import { useChapters, useParts } from "../../queries/structure";
import { useBookTodos, useCreateTodo, useDeleteTodo, useUpdateTodo } from "../../queries/todos";
import { ConversationModal } from "../conversation/ConversationModal";

ModuleRegistry.registerModules([AllCommunityModule]);

const authorityTheme = themeQuartz.withParams({
  accentColor: "var(--accent)",
  borderColor: "var(--line)",
  fontFamily: "Inter, system-ui, sans-serif",
  headerBackgroundColor: "var(--surface)",
  backgroundColor: "var(--surface)",
  foregroundColor: "var(--ink)",
  chromeBackgroundColor: "var(--paper)",
  rowHoverColor: "var(--accent-wash)",
  selectedRowBackgroundColor: "var(--accent-wash)",
  rowHeight: 34,
  headerHeight: 36,
});

const ORIGIN_ICON: Record<Todo["origin"], string> = { user: "👤", dependency: "⛓", ai: "✦" };
const ORIGIN_LABEL: Record<Todo["origin"], string> = { user: "Added by you", dependency: "Dependency changed", ai: "Suggested by AI" };

type Filter = "open" | "all";
type NewParentType = Exclude<ParentType, "scene">;

export default function TasksPage() {
  const { bookId = "" } = useParams();
  const navigate = useNavigate();
  const toast = useToast();

  const [filter, setFilter] = useState<Filter>("open");
  const [includeScenes, setIncludeScenes] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [newAction, setNewAction] = useState("");
  const [newParentType, setNewParentType] = useState<NewParentType>("book");
  const [newParentId, setNewParentId] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<Todo | null>(null);
  const [activeConversation, setActiveConversation] = useState<{ id: string; sceneId?: string } | null>(null);

  const uiQ = useQuery({ queryKey: keys.bookUi(bookId), queryFn: () => getBookUi(bookId), enabled: !!bookId });
  const parts = useParts(bookId);
  const chapters = useChapters(bookId);

  // Hydrate the persistent "also show scene todos" preference from ui.json once.
  useEffect(() => {
    const saved = (uiQ.data as { tasksShowSceneTodos?: boolean } | undefined)?.tasksShowSceneTodos;
    if (typeof saved === "boolean") setIncludeScenes(saved);
  }, [uiQ.data]);

  const todosQ = useBookTodos(bookId, includeScenes);
  const createTodo = useCreateTodo(bookId);
  const updateTodo = useUpdateTodo(bookId);
  const deleteTodo = useDeleteTodo(bookId);

  const rows = useMemo(() => {
    const all = todosQ.data ?? [];
    return filter === "open" ? all.filter((t) => t.status === "open") : all;
  }, [todosQ.data, filter]);

  const toggleIncludeScenes = () => {
    setIncludeScenes((v) => {
      const next = !v;
      void patchBookUi(bookId, { tasksShowSceneTodos: next });
      return next;
    });
  };

  const navigateToParent = (t: Todo) => {
    if (t.parentType === "scene") navigate(`/book/${bookId}/scene/${t.parentId}`);
    else navigate(`/book/${bookId}/metadata`);
  };

  const openConversation = async (t: Todo) => {
    if (t.conversationId) {
      setActiveConversation({ id: t.conversationId, sceneId: t.parentType === "scene" ? t.parentId : undefined });
      return;
    }
    try {
      const conv = await createConversation(bookId, { kind: "task-discussion", parentType: t.parentType, parentId: t.parentId });
      await updateTodo.mutateAsync({ todoId: t.id, body: { conversationId: conv.id } });
      setActiveConversation({ id: conv.id, sceneId: t.parentType === "scene" ? t.parentId : undefined });
    } catch {
      toast.error("Couldn't start a conversation.");
    }
  };

  const columnDefs = useMemo<ColDef<Todo>[]>(
    () => [
      {
        colId: "status",
        headerName: "",
        width: 44,
        sortable: false,
        filter: false,
        cellRenderer: (p: { data?: Todo }) => {
          const t = p.data;
          if (!t) return null;
          return (
            <input
              type="checkbox"
              className="accent-accent"
              checked={t.status === "done"}
              title={t.status === "done" ? "Mark open" : "Mark done"}
              onChange={(e) => updateTodo.mutate({ todoId: t.id, body: { status: e.target.checked ? "done" : "open" } })}
            />
          );
        },
      },
      {
        field: "action",
        headerName: "Action",
        flex: 2,
        minWidth: 220,
        cellRenderer: (p: { data?: Todo }) => {
          const t = p.data;
          if (!t) return null;
          return <span className={t.status !== "open" ? "text-ink-faint line-through" : "text-ink"}>{t.action}</span>;
        },
      },
      {
        colId: "parent",
        headerName: "Parent",
        width: 180,
        valueGetter: (p) => p.data?.parentTitle || p.data?.parentType || "",
        cellRenderer: (p: { data?: Todo }) => {
          const t = p.data;
          if (!t) return null;
          return (
            <button
              className="max-w-full truncate rounded-control px-1.5 py-0.5 text-[0.8125rem] text-accent hover:bg-accent-wash"
              onClick={(e) => {
                e.stopPropagation();
                navigateToParent(t);
              }}
            >
              {t.parentTitle || `(${t.parentType})`}
            </button>
          );
        },
      },
      {
        colId: "origin",
        headerName: "",
        width: 50,
        sortable: false,
        filter: false,
        cellRenderer: (p: { data?: Todo }) =>
          p.data ? <span title={ORIGIN_LABEL[p.data.origin]}>{ORIGIN_ICON[p.data.origin]}</span> : null,
      },
      { field: "createdAt", headerName: "Created", width: 170 },
      { field: "updatedAt", headerName: "Updated", width: 170 },
      {
        colId: "actions",
        headerName: "",
        width: 96,
        sortable: false,
        filter: false,
        suppressMovable: true,
        cellRenderer: (p: { data?: Todo }) => {
          const t = p.data;
          if (!t) return null;
          return (
            <div className="flex h-full items-center gap-1">
              <button
                title="Open conversation"
                onClick={(e) => {
                  e.stopPropagation();
                  void openConversation(t);
                }}
                className="rounded px-1 text-ink-soft hover:bg-accent-wash"
              >
                💬
              </button>
              {t.status === "open" && (
                <button
                  title="Close (not applicable)"
                  onClick={(e) => {
                    e.stopPropagation();
                    updateTodo.mutate({ todoId: t.id, body: { status: "closed" } });
                  }}
                  className="rounded px-1 text-ink-soft hover:bg-accent-wash"
                >
                  ✕
                </button>
              )}
              <button
                title="Delete"
                onClick={(e) => {
                  e.stopPropagation();
                  setConfirmDelete(t);
                }}
                className="rounded px-1 text-danger hover:bg-danger-wash"
              >
                🗑
              </button>
            </div>
          );
        },
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [updateTodo],
  );

  const parentOptions = useMemo(() => {
    if (newParentType === "chapter") return (chapters.data ?? []).map((c) => ({ value: c.id, label: c.title || "Untitled chapter" }));
    if (newParentType === "part") return (parts.data ?? []).map((p) => ({ value: p.id, label: p.title || "Untitled part" }));
    return [];
  }, [newParentType, chapters.data, parts.data]);

  const canSubmitAdd = newAction.trim().length > 0 && (newParentType === "book" || !!newParentId);

  const submitAdd = async () => {
    const action = newAction.trim();
    if (!action || !canSubmitAdd) return;
    try {
      await createTodo.mutateAsync({
        parentType: newParentType,
        parentId: newParentType === "book" ? bookId : newParentId,
        action,
      });
      setNewAction("");
      setAddOpen(false);
      toast.success("Task added");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Couldn't add that task.");
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-2">
        <div className="flex items-center gap-3">
          <div className="inline-flex overflow-hidden rounded-control border border-line text-[0.8125rem]">
            {(["open", "all"] as Filter[]).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1 capitalize ${filter === f ? "bg-accent-wash text-accent" : "text-ink-soft hover:bg-accent-wash/60"}`}
              >
                {f}
              </button>
            ))}
          </div>
          <label className="flex items-center gap-1.5 text-[0.8125rem] text-ink-soft">
            <input type="checkbox" className="accent-accent" checked={includeScenes} onChange={toggleIncludeScenes} />
            Also show scene todos
          </label>
        </div>
        <Button variant="primary" onClick={() => setAddOpen((o) => !o)}>
          ＋ Add task
        </Button>
      </div>

      {addOpen && (
        <div className="flex flex-wrap items-center gap-2 border-b border-line bg-surface px-4 py-2">
          <input
            autoFocus
            value={newAction}
            onChange={(e) => setNewAction(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void submitAdd();
            }}
            placeholder="What needs to happen?"
            className="h-8 min-w-[220px] flex-1 rounded-control border border-line bg-paper px-2 text-[0.875rem] text-ink outline-none focus:border-accent"
          />
          <div className="w-32">
            <SearchableSelect
              options={[
                { value: "book", label: "Book" },
                { value: "chapter", label: "Chapter" },
                { value: "part", label: "Part" },
              ]}
              value={newParentType}
              onChange={(v) => {
                setNewParentType((v as NewParentType) ?? "book");
                setNewParentId("");
              }}
            />
          </div>
          {newParentType !== "book" && (
            <div className="w-48">
              <SearchableSelect
                options={parentOptions}
                value={newParentId || null}
                onChange={(v) => setNewParentId(v ?? "")}
                placeholder={`Pick a ${newParentType}`}
              />
            </div>
          )}
          <Button variant="primary" onClick={() => void submitAdd()} disabled={!canSubmitAdd}>
            Add
          </Button>
          <Button variant="ghost" onClick={() => setAddOpen(false)}>
            Cancel
          </Button>
        </div>
      )}

      <div className="min-h-0 flex-1">
        {rows.length === 0 ? (
          <div className="flex h-full items-center justify-center text-[0.875rem] text-ink-faint">
            {filter === "open" ? "No open tasks." : "No tasks yet."}
          </div>
        ) : (
          <AgGridReact<Todo>
            theme={authorityTheme}
            rowData={rows}
            columnDefs={columnDefs}
            defaultColDef={{ sortable: true, resizable: true, filter: true }}
          />
        )}
      </div>

      {confirmDelete && (
        <ConfirmDialog
          title="Delete this task?"
          message="This removes the task permanently. If it's just no longer applicable, Close it instead — that keeps a record."
          confirmLabel="Delete task"
          onConfirm={async () => {
            try {
              await deleteTodo.mutateAsync(confirmDelete.id);
            } catch (e) {
              toast.error(e instanceof ApiError ? e.message : "Couldn't delete the task.");
            }
            setConfirmDelete(null);
          }}
          onCancel={() => setConfirmDelete(null)}
        />
      )}

      {activeConversation && (
        <ConversationModal
          bookId={bookId}
          conversationId={activeConversation.id}
          sceneId={activeConversation.sceneId}
          onClose={() => setActiveConversation(null)}
        />
      )}
    </div>
  );
}
