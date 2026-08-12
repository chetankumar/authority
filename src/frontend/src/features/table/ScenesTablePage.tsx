// Scene Table — `/book/{id}/table` (doc 06 §7)
//
// The "working ledger": a sortable, filterable AG Grid listing every scene in the
// book. Authors use it to scan metadata, spot unplaced scenes, and jump into the
// editor. Same GET /scenes payload as the Scene Graph; filtering and column
// layout are client-side only.
//
// Key interactions:
//   • Row click        → scene editor
//   • ✎ (actions col)  → Scene Modal (metadata, not prose)
//   • Archive / Delete → PATCH or DELETE on the scene
//   • Columns ▾        → show/hide optional columns; persisted to db/ui.json
//   • All/Placed/Floating toolbar → filter by where the scene sits in the story structure
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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

// AG Grid v33+ requires explicit module registration (Community edition here).
ModuleRegistry.registerModules([AllCommunityModule]);

// Maps AG Grid's built-in theme to our CSS variables so the grid matches light/dark
// mode automatically. See src/styles/tokens.css — components must not use raw hex.
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

// ---------------------------------------------------------------------------
// Toolbar filter: All / Placed / Floating
// ---------------------------------------------------------------------------
//
// Each scene carries a computed `placement` field (never stored on disk — ChainService
// derives it from the hard-chain prev/next links). It tells you how the scene relates
// to the main story spine:
//
//   trunk       — on the hard chain between Start and The End (normal story order)
//   unanchored  — has prev/next links but sits beside the trunk (soft-linked satellite)
//   floating    — no chain links at all; author hasn't placed it yet
//   orphan      — linked but disconnected from Start→End path (planning mistake)
//   archived    — set aside; hidden unless the Archived checkbox is on
//
// The toolbar shows three mutually exclusive buttons (a "segmented control"). We call
// the active choice a Segment — it controls which placements appear in the grid:
//
//   "all"      — every active scene regardless of placement
//   "placed"   — trunk + unanchored (scenes that have *some* position in the structure)
//   "floating" — floating + orphan (scenes that still need structural attention)
//
// Filtering is client-side over the cached scenes list; no extra API call.
type Segment = "all" | "placed" | "floating";

// Placement values included when the author clicks "Placed" in the toolbar.
const PLACED: Placement[] = ["trunk", "unanchored"];

// Placement values included when the author clicks "Floating" in the toolbar.
const FLOATING: Placement[] = ["floating", "orphan"];

// Small text badges shown next to the title for scenes that aren't plain trunk rows.
// Trunk scenes get no badge — they're the default, unremarkable case. Archived scenes
// use strikethrough styling instead of a placement chip (status !== placement).
const CHIP: Partial<Record<Placement, string>> = {
  unanchored: "unanchored",
  floating: "floating",
  orphan: "orphan",
  archived: "archived",
};

export default function ScenesTablePage() {
  // -------------------------------------------------------------------------
  // Server data (TanStack Query — see src/queries/)
  // -------------------------------------------------------------------------

  const { bookId = "" } = useParams();
  const navigate = useNavigate();

  // All scenes + soft relationships. `placement` and `seq` are computed server-side.
  const { data } = useScenes(bookId);

  // Parts and chapters — needed because the grid shows human titles, not raw ids.
  // Also used to infer Part from Chapter (a scene in a chapter inherits the chapter's part).
  const book = useBook(bookId);

  const updateScene = useUpdateScene(bookId);
  const deleteSceneMut = useDeleteScene(bookId);

  // Per-book UI preferences stored in the book folder at db/ui.json (not in the repo).
  // We read `tableColumnState` on load and write it back when columns move/resize/show/hide.
  const uiQ = useQuery({
    queryKey: keys.bookUi(bookId),
    queryFn: () => getBookUi(bookId),
    enabled: !!bookId,
  });

  // -------------------------------------------------------------------------
  // Local UI state
  // -------------------------------------------------------------------------

  // Which toolbar segment is active: "all" | "placed" | "floating" (see type above).
  const [segment, setSegment] = useState<Segment>("all");

  // When false (default), archived scenes are excluded from the grid entirely.
  // When true, they appear with strikethrough titles — the table is their home (doc 06 §7).
  const [showArchived, setShowArchived] = useState(false);

  // Whether the "Columns ▾" checkbox panel is open.
  const [columnsOpen, setColumnsOpen] = useState(false);

  // Checkbox panel reads visibility from AG Grid, not React state. AG Grid does not
  // trigger a React re-render when a column is shown/hidden, so we bump this counter
  // after each toggle to force the checkboxes to re-read the grid's column state.
  const [columnTick, setColumnTick] = useState(0);

  // When set, Scene Modal is open. sceneId=null → create flow; string → edit that scene.
  const [modal, setModal] = useState<{ sceneId: string | null } | null>(null);

  // When set, ConfirmDialog is asking the author to confirm hard delete (archived only).
  const [confirmDelete, setConfirmDelete] = useState<Scene | null>(null);

  // Error message from a failed delete (e.g. scene still referenced) — shown as toast.
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // -------------------------------------------------------------------------
  // Refs — imperative handles and guards
  // -------------------------------------------------------------------------

  // Set in onGridReady; used for column show/hide, persist, and cell refresh.
  const apiRef = useRef<GridApi<Scene> | null>(null);

  // Debounce timer for PATCH /books/:id/ui — resets on each column change so we
  // write once ~1s after the author stops dragging/resizing/toggling.
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // DOM node wrapping the Columns button + dropdown; used to detect outside clicks.
  const columnsRef = useRef<HTMLDivElement>(null);

  // False until onGridReady runs; applySavedColumnState waits for both this and uiQ.
  const gridReadyRef = useRef(false);

  // Prevents applying ui.json column state more than once per visit (would reset user edits).
  const columnStateAppliedRef = useRef(false);

  // Set true the first time the author toggles a column in the chooser. While true,
  // we skip applySavedColumnState so a slow ui.json fetch cannot overwrite in-progress edits.
  const userModifiedColumnsRef = useRef(false);

  // -------------------------------------------------------------------------
  // Chapter / Part display lookups
  // -------------------------------------------------------------------------
  // Scenes store chapterId OR partId (never both — enforced by the API). The grid
  // shows titles. These maps translate ids → readable names from the book context.

  const chapterName = useMemo(
    () => new Map((book.data?.chapters ?? []).map((c) => [c.id, c.title || "Untitled chapter"])),
    [book.data],
  );
  const partName = useMemo(
    () => new Map((book.data?.parts ?? []).map((p) => [p.id, p.title || "Untitled part"])),
    [book.data],
  );
  // Scenes assigned to a chapter do not store partId on the scene record. The chapter
  // carries partId instead, so we map chapterId → partId to fill the Part column.
  const chapterPartId = useMemo(
    () => new Map((book.data?.chapters ?? []).map((c) => [c.id, c.partId])),
    [book.data],
  );

  // columnDefs is memoized with an empty dependency array (see below) so AG Grid
  // never gets a new columnDefs reference on re-render — that can reset column state.
  // These refs hold the latest maps so valueGetters inside columnDefs always see
  // current chapter/part titles without recreating the array.
  const chapterNameRef = useRef(chapterName);
  const partNameRef = useRef(partName);
  const chapterPartIdRef = useRef(chapterPartId);
  chapterNameRef.current = chapterName;
  partNameRef.current = partName;
  chapterPartIdRef.current = chapterPartId;

  // Same pattern for action-column handlers (edit, archive, delete). cellRenderer
  // closures in columnDefs would go stale if we closed over setModal/updateScene directly
  // while keeping columnDefs memoized with [].
  const updateSceneRef = useRef(updateScene);
  updateSceneRef.current = updateScene;
  const setModalRef = useRef(setModal);
  setModalRef.current = setModal;
  const setConfirmDeleteRef = useRef(setConfirmDelete);
  setConfirmDeleteRef.current = setConfirmDelete;

  // book.data often loads after the grid first renders. When titles arrive, repaint
  // only the Chapter and Part cells (valueGetters read from the refs above).
  useEffect(() => {
    apiRef.current?.refreshCells({ columns: ["chapter", "part"], force: true });
  }, [chapterName, partName, chapterPartId]);

  // Switching books — reset guards so the new book's ui.json can be applied fresh.
  useEffect(() => {
    gridReadyRef.current = false;
    columnStateAppliedRef.current = false;
    userModifiedColumnsRef.current = false;
  }, [bookId]);

  // Restore column order, width, and visibility from ui.json.tableColumnState.
  // Called from onGridReady and from the effect below (ui.json may load after the grid).
  const applySavedColumnState = useCallback(() => {
    if (!apiRef.current || columnStateAppliedRef.current || userModifiedColumnsRef.current) return;
    const saved = (uiQ.data as { tableColumnState?: unknown })?.tableColumnState;
    if (Array.isArray(saved)) {
      apiRef.current.applyColumnState({ state: saved as never, applyOrder: true });
      columnStateAppliedRef.current = true;
    }
  }, [uiQ.data]);

  // Retry restore when uiQ resolves (common race: grid ready before GET /books/:id/ui).
  useEffect(() => {
    if (!gridReadyRef.current) return;
    applySavedColumnState();
  }, [applySavedColumnState]);

  // Doc 06 §1.5: popovers close on outside click and Esc.
  useEffect(() => {
    if (!columnsOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (columnsRef.current && !columnsRef.current.contains(e.target as Node)) {
        setColumnsOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setColumnsOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [columnsOpen]);

  // -------------------------------------------------------------------------
  // Rows fed to AG Grid (filtered + sorted client-side)
  // -------------------------------------------------------------------------

  const rows = useMemo(() => {
    let scenes = data?.scenes ?? [];

    // Archived filter: by default only active scenes; checkbox adds archived ones back.
    scenes = scenes.filter((s) => (showArchived ? true : s.status === "active"));

    // Toolbar segment filter — see Segment type and PLACED/FLOATING constants above.
    if (segment === "placed") scenes = scenes.filter((s) => PLACED.includes(s.placement));
    if (segment === "floating") scenes = scenes.filter((s) => FLOATING.includes(s.placement));

    // Default sort: story order (seq ascending). Scenes without seq (e.g. archived off-chain) sort last.
    return [...scenes].sort((a, b) => (a.seq ?? 999) - (b.seq ?? 999));
  }, [data, segment, showArchived]);

  // -------------------------------------------------------------------------
  // AG Grid column definitions
  // -------------------------------------------------------------------------
  // useMemo(..., []) — empty deps intentional. A new columnDefs reference on every
  // render makes AG Grid re-process definitions and can reset column state.
  //
  // Optional columns use initialHide (not hide). AG Grid treats hide as STATEFUL:
  // it is re-applied whenever defs are reconciled, which undoes applyColumnState
  // from the Columns ▾ chooser on the next React re-render. initialHide applies
  // only when the column is first created; after that, visibility is controlled
  // by applyColumnState (author toggles) or ui.json restore.
  //
  // Dynamic cell data goes through refs so columnDefs stays stable; see chapterNameRef.

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
        valueGetter: (p) => (p.data?.characters?.length ? `${p.data.characters.length}` : ""),
      },
      {
        colId: "chapter",
        headerName: "Chapter",
        width: 140,
        valueGetter: (p) =>
          p.data?.chapterId ? chapterNameRef.current.get(p.data.chapterId) ?? "" : "",
      },
      {
        colId: "part",
        headerName: "Part",
        width: 140,
        valueGetter: (p) => {
          const s = p.data;
          if (!s) return "";
          // scene.partId if assigned directly to a part; else look up the chapter's part.
          const pid = s.partId ?? (s.chapterId ? chapterPartIdRef.current.get(s.chapterId) : null);
          return pid ? partNameRef.current.get(pid) ?? "" : "";
        },
      },
      { field: "mood", headerName: "Mood", width: 120 },
      // Optional columns — initialHide hides on first mount; Columns ▾ toggles via applyColumnState.
      { field: "location", headerName: "Location", width: 140, initialHide: true },
      { field: "dateTime", headerName: "Date / Time", width: 140, initialHide: true },
      { field: "emotionalArc", headerName: "Emotional arc", width: 160, initialHide: true },
      { field: "summary", headerName: "Summary", flex: 2, minWidth: 200, initialHide: true },
      { field: "wordCount", headerName: "Words", width: 100, initialHide: true },
      { field: "updatedAt", headerName: "Updated", width: 170, initialHide: true },
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
                  setModalRef.current({ sceneId: s.id });
                }}
                className="rounded px-1 text-ink-soft hover:bg-accent-wash"
              >
                ✎
              </button>
              <button
                title={archived ? "Unarchive" : "Archive"}
                onClick={(e) => {
                  e.stopPropagation();
                  updateSceneRef.current.mutate({ sceneId: s.id, body: { status: archived ? "active" : "archived" } });
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
                    setConfirmDeleteRef.current(s);
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
    [],
  );

  // -------------------------------------------------------------------------
  // Column chooser + ui.json persistence
  // -------------------------------------------------------------------------

  // Snapshot AG Grid's full column state and debounce-write to ui.json.
  // Also hooked to onColumnMoved / onColumnResized / onColumnVisible / onSortChanged.
  const persist = useCallback(() => {
    if (!apiRef.current) return;
    if (saveTimer.current) clearTimeout(saveTimer.current);
    const state = apiRef.current.getColumnState();
    saveTimer.current = setTimeout(() => {
      void patchBookUi(bookId, { tableColumnState: state });
    }, 1000);
  }, [bookId]);

  // Build a map of colId → visible for the checkbox panel. Uses getColumnState()
  // (hide: false means visible) rather than getColumn().isVisible() per column.
  const columnVisibility = useCallback((): Map<string, boolean> => {
    if (!apiRef.current) return new Map();
    return new Map(
      apiRef.current.getColumnState().map((col) => [col.colId as string, !col.hide]),
    );
  }, []);

  // Show or hide a single column. We clone the full column state array and flip
  // only the matching colId's hide flag, then apply the whole array — this keeps
  // other columns' visibility intact (setColumnsVisible on one col alone was buggy).
  const toggleColumnVisibility = useCallback(
    (colId: string, visible: boolean) => {
      const api = apiRef.current;
      if (!api) return;
      userModifiedColumnsRef.current = true;
      const state = api.getColumnState().map((col) =>
        col.colId === colId ? { ...col, hide: !visible } : col,
      );
      api.applyColumnState({ state });
      persist();
      setColumnTick((t) => t + 1);
    },
    [persist],
  );

  const onGridReady = (e: GridReadyEvent<Scene>) => {
    apiRef.current = e.api;
    gridReadyRef.current = true;
    applySavedColumnState();
  };

  const columnList = columnDefs.filter((c) => c.colId !== "actions" && c.headerName);

  // Tie render to columnTick so checkboxes refresh after toggleColumnVisibility.
  void columnTick;
  const visibilityByColId = columnVisibility();

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-2">
        <div className="flex items-center gap-3">
          {/* All / Placed / Floating — filters rows by scene.placement (see Segment type) */}
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
          <div ref={columnsRef} className="relative">
            <Button variant="secondary" onClick={() => setColumnsOpen((o) => !o)}>
              Columns ▾
            </Button>
            {columnsOpen && (
              <div className="absolute right-0 top-full z-30 mt-1 w-52 rounded-card border border-line bg-surface p-2 shadow-overlay">
                {columnList.map((c) => {
                  const id = (c.colId ?? c.field) as string;
                  const visible = visibilityByColId.get(id) ?? false;
                  return (
                    <label key={id} className="flex items-center gap-2 px-1 py-1 text-[0.8125rem] text-ink">
                      <input
                        type="checkbox"
                        checked={visible}
                        onChange={(e) => toggleColumnVisibility(id, e.target.checked)}
                      />
                      {c.headerName}
                    </label>
                  );
                })}
              </div>
            )}
          </div>
          <Button variant="primary" onClick={() => setModal({ sceneId: null })}>
            ＋ Add scene
          </Button>
        </div>
      </div>

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
          onRowClicked={(e) => {
            const target = e.event?.target as HTMLElement | null;
            if (target?.closest('[col-id="actions"]')) return;
            if (e.data) navigate(`/book/${bookId}/scene/${e.data.id}`);
          }}
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
              const msg = e instanceof ApiError ? (e.blockedByMessage || e.message) : "Couldn't delete the scene.";
              setDeleteError(msg);
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
