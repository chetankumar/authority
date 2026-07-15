// Scene Table (doc 06 §7) — the working ledger. AG Grid over the same GET /scenes
// payload the graph uses. Placement filter (All/Placed/Floating) + Archived toggle;
// column visibility/order/width persist to db/ui.json; row click → editor; ✎ → Scene
// Modal; row Archive/Unarchive.
import { useCallback, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { AgGridReact } from "ag-grid-react";
import {
  AllCommunityModule,
  ModuleRegistry,
  themeQuartz,
  type ColDef,
  type GridApi,
  type GridReadyEvent,
} from "ag-grid-community";

import { getBookUi, patchBookUi } from "../../api/books";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { Button } from "../../components/ui";
import { keys } from "../../queries/keys";
import type { Placement, Scene } from "../../api/scenes";
import { ApiError } from "../../api/client";
import { useBook } from "../../queries/books";
import { useScenes, useUpdateScene, useDeleteScene } from "../../queries/scenes";
import { SceneModal } from "../sceneModal/SceneModal";

ModuleRegistry.registerModules([AllCommunityModule]);

// Params reference the design tokens so the grid follows the app theme with no
// JS — var() resolves live against :root[data-theme] (doc 06 §1.2, no raw hex).
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

type Segment = "all" | "placed" | "floating";
const PLACED: Placement[] = ["trunk", "unanchored"];
const FLOATING: Placement[] = ["floating", "orphan"];

const CHIP: Partial<Record<Placement, string>> = {
  unanchored: "unanchored",
  floating: "floating",
  orphan: "orphan",
  archived: "archived",
};

export default function ScenesTablePage() {
  const { bookId = "" } = useParams();
  const navigate = useNavigate();
  const { data } = useScenes(bookId);
  const book = useBook(bookId);
  const updateScene = useUpdateScene(bookId);
  const deleteSceneMut = useDeleteScene(bookId);
  const uiQ = useQuery({ queryKey: keys.bookUi(bookId), queryFn: () => getBookUi(bookId), enabled: !!bookId });

  const [segment, setSegment] = useState<Segment>("all");
  const [showArchived, setShowArchived] = useState(false);
  const [columnsOpen, setColumnsOpen] = useState(false);
  const [modal, setModal] = useState<{ sceneId: string | null } | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<Scene | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const apiRef = useRef<GridApi<Scene> | null>(null);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const chapterName = useMemo(
    () => new Map((book.data?.chapters ?? []).map((c) => [c.id, c.title || "Untitled chapter"])),
    [book.data],
  );
  const partName = useMemo(
    () => new Map((book.data?.parts ?? []).map((p) => [p.id, p.title || "Untitled part"])),
    [book.data],
  );

  const rows = useMemo(() => {
    let scenes = data?.scenes ?? [];
    scenes = scenes.filter((s) => (showArchived ? true : s.status === "active"));
    if (segment === "placed") scenes = scenes.filter((s) => PLACED.includes(s.placement));
    if (segment === "floating") scenes = scenes.filter((s) => FLOATING.includes(s.placement));
    return [...scenes].sort((a, b) => (a.seq ?? 999) - (b.seq ?? 999));
  }, [data, segment, showArchived]);

  const columnDefs = useMemo<ColDef<Scene>[]>(
    () => [
      { field: "seq", headerName: "Seq", width: 80, sort: "asc", valueGetter: (p) => p.data?.seq ?? null },
      {
        field: "title",
        headerName: "Title",
        flex: 2,
        minWidth: 180,
        cellRenderer: (p: { data?: Scene }) => {
          const s = p.data;
          if (!s) return null;
          const chip = CHIP[s.placement];
          const archived = s.status === "archived";
          return (
            <span className={archived ? "text-ink-faint line-through" : ""}>
              {s.title}
              {chip && (
                <span className="ml-2 rounded-full bg-accent-wash px-1.5 py-0.5 text-[0.625rem] text-ink-soft">
                  {chip}
                </span>
              )}
            </span>
          );
        },
      },
      { field: "description", headerName: "Description", flex: 3, minWidth: 220 },
      {
        colId: "characters",
        headerName: "Characters",
        width: 120,
        valueGetter: (p) => (p.data?.characterIds.length ? `${p.data.characterIds.length}` : ""),
      },
      { colId: "chapter", headerName: "Chapter", width: 140, valueGetter: (p) => (p.data?.chapterId ? chapterName.get(p.data.chapterId) ?? "" : "") },
      { colId: "part", headerName: "Part", width: 140, valueGetter: (p) => (p.data?.partId ? partName.get(p.data.partId) ?? "" : "") },
      { field: "mood", headerName: "Mood", width: 120 },
      { field: "location", headerName: "Location", width: 140, hide: true },
      { field: "dateTime", headerName: "Date / Time", width: 140, hide: true },
      { field: "emotionalArc", headerName: "Emotional arc", width: 160, hide: true },
      { field: "summary", headerName: "Summary", flex: 2, minWidth: 200, hide: true },
      { field: "wordCount", headerName: "Words", width: 100, hide: true },
      { field: "updatedAt", headerName: "Updated", width: 170, hide: true },
      {
        colId: "actions",
        headerName: "",
        width: 120,
        sortable: false,
        filter: false,
        suppressMovable: true,
        cellRenderer: (p: { data?: Scene }) => {
          const s = p.data;
          if (!s) return null;
          const archived = s.status === "archived";
          return (
            <div className="flex h-full items-center gap-1">
              <button
                title="Edit metadata"
                onClick={(e) => {
                  e.stopPropagation();
                  setModal({ sceneId: s.id });
                }}
                className="rounded px-1 text-ink-soft hover:bg-accent-wash"
              >
                ✎
              </button>
              <button
                title={archived ? "Unarchive" : "Archive"}
                onClick={(e) => {
                  e.stopPropagation();
                  updateScene.mutate({ sceneId: s.id, body: { status: archived ? "active" : "archived" } });
                }}
                className="rounded px-1 text-ink-soft hover:bg-accent-wash"
              >
                {archived ? "⤴" : "⌫"}
              </button>
              {archived && (
                <button
                  title="Delete scene"
                  onClick={(e) => {
                    e.stopPropagation();
                    setConfirmDelete(s);
                  }}
                  className="rounded px-1 text-danger hover:bg-danger-wash"
                >
                  ✕
                </button>
              )}
            </div>
          );
        },
      },
    ],
    [chapterName, partName, updateScene],
  );

  const persist = useCallback(() => {
    if (!apiRef.current) return;
    if (saveTimer.current) clearTimeout(saveTimer.current);
    const state = apiRef.current.getColumnState();
    saveTimer.current = setTimeout(() => {
      void patchBookUi(bookId, { tableColumnState: state });
    }, 1000);
  }, [bookId]);

  const onGridReady = (e: GridReadyEvent<Scene>) => {
    apiRef.current = e.api;
    const saved = (uiQ.data as { tableColumnState?: unknown })?.tableColumnState;
    if (Array.isArray(saved)) e.api.applyColumnState({ state: saved as never, applyOrder: true });
  };

  const columnList = columnDefs.filter((c) => c.colId !== "actions" && c.headerName);

  return (
    <div className="flex h-full flex-col">
      {/* toolbar */}
      <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-2">
        <div className="flex items-center gap-3">
          <div className="inline-flex overflow-hidden rounded-control border border-line text-[0.8125rem]">
            {(["all", "placed", "floating"] as Segment[]).map((s) => (
              <button
                key={s}
                onClick={() => setSegment(s)}
                className={`px-3 py-1 capitalize ${segment === s ? "bg-accent-wash text-accent" : "text-ink-soft hover:bg-accent-wash/60"}`}
              >
                {s}
              </button>
            ))}
          </div>
          <label className="flex items-center gap-1.5 text-[0.8125rem] text-ink-soft">
            <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
            Archived
          </label>
        </div>
        <div className="relative flex items-center gap-2">
          <Button variant="secondary" onClick={() => setColumnsOpen((o) => !o)}>
            Columns ▾
          </Button>
          {columnsOpen && (
            <div className="absolute right-24 top-9 z-30 w-52 rounded-card border border-line bg-surface p-2 shadow-overlay">
              {columnList.map((c) => {
                const id = (c.colId ?? c.field) as string;
                const visible = !apiRef.current?.getColumn(id)?.isVisible?.() === false;
                return (
                  <label key={id} className="flex items-center gap-2 px-1 py-1 text-[0.8125rem] text-ink">
                    <input
                      type="checkbox"
                      defaultChecked={visible}
                      onChange={(e) => {
                        apiRef.current?.setColumnsVisible([id], e.target.checked);
                        persist();
                      }}
                    />
                    {c.headerName}
                  </label>
                );
              })}
            </div>
          )}
          <Button variant="primary" onClick={() => setModal({ sceneId: null })}>
            ＋ Add scene
          </Button>
        </div>
      </div>

      {/* grid */}
      <div className="min-h-0 flex-1">
        <AgGridReact<Scene>
          theme={authorityTheme}
          rowData={rows}
          columnDefs={columnDefs}
          defaultColDef={{ sortable: true, resizable: true, filter: true }}
          onGridReady={onGridReady}
          onColumnMoved={persist}
          onColumnResized={persist}
          onColumnVisible={persist}
          onSortChanged={persist}
          onRowClicked={(e) => e.data && navigate(`/book/${bookId}/scene/${e.data.id}`)}
          rowStyle={{ cursor: "pointer" }}
        />
      </div>

      {modal && <SceneModal bookId={bookId} sceneId={modal.sceneId} onClose={() => setModal(null)} />}

      {confirmDelete && (
        <ConfirmDialog
          title={`Delete "${confirmDelete.title}"?`}
          message="This scene's prose file will be moved to the book's .trash folder. The scene record will be permanently removed from the book."
          confirmLabel="Delete scene"
          onConfirm={async () => {
            try {
              await deleteSceneMut.mutateAsync(confirmDelete.id);
              setConfirmDelete(null);
              setDeleteError(null);
            } catch (e) {
              setConfirmDelete(null);
              setDeleteError(e instanceof ApiError ? e.message : "Couldn't delete the scene.");
            }
          }}
          onCancel={() => setConfirmDelete(null)}
        />
      )}

      {deleteError && (
        <div className="fixed bottom-4 right-4 z-50 rounded-card border border-danger bg-danger-wash px-4 py-3 text-[0.875rem] text-danger shadow-overlay">
          {deleteError}
          <button onClick={() => setDeleteError(null)} className="ml-3 font-medium underline">Dismiss</button>
        </div>
      )}
    </div>
  );
}
