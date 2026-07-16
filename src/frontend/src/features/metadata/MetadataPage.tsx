import { useParams } from "react-router-dom";
import { useState, useEffect } from "react";
import type { Part, Chapter } from "../../api/books";
import type { Plotline } from "../../api/structure";
import { ApiError } from "../../api/client";
import {
  useParts,
  useCreatePart,
  useUpdatePart,
  useReorderParts,
  useDeletePart,
  useChapters,
  useCreateChapter,
  useUpdateChapter,
  useReorderChapters,
  useDeleteChapter,
  usePlotlines,
  useCreatePlotline,
  useUpdatePlotline,
  useDeletePlotline,
  usePatchBook,
} from "../../queries/structure";
import { useBook } from "../../queries/books";
import { Modal } from "../../components/Modal";
import {
  BlockedDeletionDialog,
  type BlockedRef,
} from "../../components/BlockedDeletionDialog";
import { Button, Field, Input, Select } from "../../components/ui";

const TABS = [
  { key: "parts", label: "Parts" },
  { key: "chapters", label: "Chapters" },
  { key: "plotlines", label: "Plotlines" },
  { key: "book", label: "Book" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

interface BlockedState {
  name: string;
  refs: BlockedRef[];
}

function parseBlockedRefs(detail: Record<string, unknown>): BlockedRef[] {
  const blocked = detail.blockedBy;
  if (!blocked || typeof blocked !== "object") return [];
  const map = blocked as Record<string, unknown>;
  const refs: BlockedRef[] = [];
  const labels: Record<string, string> = {
    chapters: "Chapter",
    scenes: "Scene",
    parts: "Part",
    plotlines: "Plotline",
  };
  for (const [key, items] of Object.entries(map)) {
    if (!Array.isArray(items)) continue;
    const prefix = labels[key] || key;
    for (const item of items) {
      if (item && typeof item === "object" && "title" in item) {
        refs.push({
          label: `${prefix}: ${(item as { title: string }).title}`,
        });
      }
    }
  }
  return refs;
}

/* ------------------------------------------------------------------ */
/*  Parts Tab                                                          */
/* ------------------------------------------------------------------ */

function PartsTab({ bookId, parts }: { bookId: string; parts: Part[] }) {
  const createPart = useCreatePart(bookId);
  const updatePart = useUpdatePart(bookId);
  const reorderParts = useReorderParts(bookId);
  const deletePart = useDeletePart(bookId);

  const [showAdd, setShowAdd] = useState(false);
  const [addTitle, setAddTitle] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [dragIdx, setDragIdx] = useState<number | null>(null);
  const [blocked, setBlocked] = useState<BlockedState | null>(null);

  function handleAdd() {
    const title = addTitle.trim();
    if (!title) return;
    createPart.mutate(
      { title },
      {
        onSuccess: () => {
          setAddTitle("");
          setShowAdd(false);
        },
      },
    );
  }

  function startEdit(part: Part) {
    setEditingId(part.id);
    setEditValue(part.title);
  }

  function saveEdit(partId: string) {
    const title = editValue.trim();
    if (title && title !== parts.find((p) => p.id === partId)?.title) {
      updatePart.mutate({ partId, body: { title } });
    }
    setEditingId(null);
  }

  async function handleDelete(part: Part) {
    try {
      await deletePart.mutateAsync(part.id);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setBlocked({
          name: part.title,
          refs: parseBlockedRefs(err.detail),
        });
      }
    }
  }

  function handleDrop(targetIdx: number) {
    if (dragIdx === null || dragIdx === targetIdx) return;
    const reordered = [...parts];
    const [moved] = reordered.splice(dragIdx, 1);
    reordered.splice(targetIdx, 0, moved);
    reorderParts.mutate(reordered.map((p) => p.id));
    setDragIdx(null);
  }

  return (
    <div>
      {parts.length === 0 && !showAdd && (
        <div className="flex flex-col items-center py-12 text-ink-faint">
          <p className="mb-4 text-[0.875rem]">No parts yet</p>
          <Button variant="primary" onClick={() => setShowAdd(true)}>
            + Add part
          </Button>
        </div>
      )}

      {parts.length > 0 && (
        <div className="space-y-1">
          {parts.map((part, idx) => (
            <div
              key={part.id}
              draggable
              onDragStart={(e) => {
                setDragIdx(idx);
                e.dataTransfer.effectAllowed = "move";
              }}
              onDragOver={(e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = "move";
              }}
              onDrop={(e) => {
                e.preventDefault();
                handleDrop(idx);
              }}
              onDragEnd={() => setDragIdx(null)}
              className={`flex items-center gap-3 rounded-control border border-line bg-surface px-3 py-2 ${
                dragIdx === idx ? "opacity-50" : ""
              }`}
            >
              <span className="cursor-grab select-none text-ink-faint">≡</span>

              {editingId === part.id ? (
                <Input
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") saveEdit(part.id);
                    if (e.key === "Escape") setEditingId(null);
                  }}
                  onBlur={() => saveEdit(part.id)}
                  autoFocus
                  className="flex-1"
                />
              ) : (
                <button
                  onClick={() => startEdit(part)}
                  className="flex-1 truncate text-left font-prose text-[0.875rem] text-ink hover:text-accent"
                >
                  {part.title}
                </button>
              )}

              {part.description && editingId !== part.id && (
                <span className="max-w-[200px] truncate text-[0.8125rem] text-ink-faint">
                  {part.description}
                </span>
              )}

              <Button
                variant="ghost"
                onClick={() => handleDelete(part)}
                className="shrink-0 !text-danger"
              >
                ✕
              </Button>
            </div>
          ))}
        </div>
      )}

      {showAdd ? (
        <div className="mt-3 flex items-center gap-2">
          <Input
            placeholder="Part title"
            value={addTitle}
            onChange={(e) => setAddTitle(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleAdd();
              if (e.key === "Escape") {
                setShowAdd(false);
                setAddTitle("");
              }
            }}
            autoFocus
            className="flex-1"
          />
          <Button
            variant="primary"
            onClick={handleAdd}
            disabled={!addTitle.trim()}
          >
            Save
          </Button>
          <Button
            variant="ghost"
            onClick={() => {
              setShowAdd(false);
              setAddTitle("");
            }}
          >
            Cancel
          </Button>
        </div>
      ) : parts.length > 0 ? (
        <Button
          variant="primary"
          onClick={() => setShowAdd(true)}
          className="mt-3"
        >
          + Add part
        </Button>
      ) : null}

      {blocked && (
        <BlockedDeletionDialog
          name={blocked.name}
          refs={blocked.refs}
          onClose={() => setBlocked(null)}
        />
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Chapters Tab                                                       */
/* ------------------------------------------------------------------ */

function ChaptersTab({
  bookId,
  chapters,
  parts,
}: {
  bookId: string;
  chapters: Chapter[];
  parts: Part[];
}) {
  const createChapter = useCreateChapter(bookId);
  const updateChapter = useUpdateChapter(bookId);
  const reorderChapters = useReorderChapters(bookId);
  const deleteChapter = useDeleteChapter(bookId);

  const [showAdd, setShowAdd] = useState(false);
  const [addTitle, setAddTitle] = useState("");
  const [addPartId, setAddPartId] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [dragIdx, setDragIdx] = useState<number | null>(null);
  const [blocked, setBlocked] = useState<BlockedState | null>(null);

  const groups: {
    partId: string | null;
    title: string;
    items: Chapter[];
  }[] = [];
  const byPart = new Map<string | null, Chapter[]>();
  for (const ch of chapters) {
    if (!byPart.has(ch.partId)) byPart.set(ch.partId, []);
    byPart.get(ch.partId)!.push(ch);
  }
  for (const part of parts) {
    if (byPart.has(part.id)) {
      groups.push({
        partId: part.id,
        title: part.title,
        items: byPart.get(part.id)!,
      });
    }
  }
  const unassigned = byPart.get(null);
  if (unassigned) {
    groups.push({ partId: null, title: "Unassigned", items: unassigned });
  }

  const chapterGlobalIdx = new Map(chapters.map((ch, i) => [ch.id, i]));

  function handleAdd() {
    const title = addTitle.trim();
    if (!title) return;
    createChapter.mutate(
      { title, partId: addPartId || null },
      {
        onSuccess: () => {
          setAddTitle("");
          setAddPartId("");
          setShowAdd(false);
        },
      },
    );
  }

  function startEdit(ch: Chapter) {
    setEditingId(ch.id);
    setEditValue(ch.title);
  }

  function saveEdit(chpId: string) {
    const title = editValue.trim();
    if (title && title !== chapters.find((c) => c.id === chpId)?.title) {
      updateChapter.mutate({ chpId, body: { title } });
    }
    setEditingId(null);
  }

  function handlePartChange(chpId: string, newPartId: string) {
    updateChapter.mutate({ chpId, body: { partId: newPartId || null } });
  }

  async function handleDelete(ch: Chapter) {
    try {
      await deleteChapter.mutateAsync(ch.id);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setBlocked({
          name: ch.title,
          refs: parseBlockedRefs(err.detail),
        });
      }
    }
  }

  function handleDrop(targetGlobalIdx: number) {
    if (dragIdx === null || dragIdx === targetGlobalIdx) return;
    const reordered = [...chapters];
    const [moved] = reordered.splice(dragIdx, 1);
    reordered.splice(targetGlobalIdx, 0, moved);
    reorderChapters.mutate(reordered.map((c) => c.id));
    setDragIdx(null);
  }

  return (
    <div>
      {chapters.length === 0 && !showAdd && (
        <div className="flex flex-col items-center py-12 text-ink-faint">
          <p className="mb-4 text-[0.875rem]">No chapters yet</p>
          <Button variant="primary" onClick={() => setShowAdd(true)}>
            + Add chapter
          </Button>
        </div>
      )}

      {groups.map((group) => (
        <div key={group.partId ?? "_unassigned"} className="mb-4">
          <h3 className="mb-2 font-ui text-[0.75rem] uppercase tracking-wider text-ink-soft">
            {group.title}
          </h3>
          <div className="space-y-1">
            {group.items.map((ch) => {
              const gIdx = chapterGlobalIdx.get(ch.id)!;
              return (
                <div
                  key={ch.id}
                  draggable
                  onDragStart={(e) => {
                    setDragIdx(gIdx);
                    e.dataTransfer.effectAllowed = "move";
                  }}
                  onDragOver={(e) => {
                    e.preventDefault();
                    e.dataTransfer.dropEffect = "move";
                  }}
                  onDrop={(e) => {
                    e.preventDefault();
                    handleDrop(gIdx);
                  }}
                  onDragEnd={() => setDragIdx(null)}
                  className={`flex items-center gap-3 rounded-control border border-line bg-surface px-3 py-2 ${
                    dragIdx === gIdx ? "opacity-50" : ""
                  }`}
                >
                  <span className="cursor-grab select-none text-ink-faint">
                    ≡
                  </span>

                  {editingId === ch.id ? (
                    <Input
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") saveEdit(ch.id);
                        if (e.key === "Escape") setEditingId(null);
                      }}
                      onBlur={() => saveEdit(ch.id)}
                      autoFocus
                      className="flex-1"
                    />
                  ) : (
                    <button
                      onClick={() => startEdit(ch)}
                      className="flex-1 truncate text-left font-prose text-[0.875rem] text-ink hover:text-accent"
                    >
                      {ch.title}
                    </button>
                  )}

                  <Select
                    value={ch.partId ?? ""}
                    onChange={(e) => handlePartChange(ch.id, e.target.value)}
                    style={{ width: "9rem", flex: "none" }}
                  >
                    <option value="">Unassigned</option>
                    {parts.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.title}
                      </option>
                    ))}
                  </Select>

                  {ch.description && editingId !== ch.id && (
                    <span className="max-w-[120px] truncate text-[0.8125rem] text-ink-faint">
                      {ch.description}
                    </span>
                  )}

                  <Button
                    variant="ghost"
                    onClick={() => handleDelete(ch)}
                    className="shrink-0 !text-danger"
                  >
                    ✕
                  </Button>
                </div>
              );
            })}
          </div>
        </div>
      ))}

      {showAdd ? (
        <div className="mt-3 flex items-center gap-2">
          <Input
            placeholder="Chapter title"
            value={addTitle}
            onChange={(e) => setAddTitle(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleAdd();
              if (e.key === "Escape") {
                setShowAdd(false);
                setAddTitle("");
                setAddPartId("");
              }
            }}
            autoFocus
            className="flex-1"
          />
          <Select
            value={addPartId}
            onChange={(e) => setAddPartId(e.target.value)}
            style={{ width: "9rem", flex: "none" }}
          >
            <option value="">Unassigned</option>
            {parts.map((p) => (
              <option key={p.id} value={p.id}>
                {p.title}
              </option>
            ))}
          </Select>
          <Button
            variant="primary"
            onClick={handleAdd}
            disabled={!addTitle.trim()}
          >
            Save
          </Button>
          <Button
            variant="ghost"
            onClick={() => {
              setShowAdd(false);
              setAddTitle("");
              setAddPartId("");
            }}
          >
            Cancel
          </Button>
        </div>
      ) : chapters.length > 0 ? (
        <Button
          variant="primary"
          onClick={() => setShowAdd(true)}
          className="mt-3"
        >
          + Add chapter
        </Button>
      ) : null}

      {blocked && (
        <BlockedDeletionDialog
          name={blocked.name}
          refs={blocked.refs}
          onClose={() => setBlocked(null)}
        />
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Plotlines Tab                                                       */
/* ------------------------------------------------------------------ */

function PlotlinesTab({
  bookId,
  plotlines,
}: {
  bookId: string;
  plotlines: Plotline[];
}) {
  const createPlotline = useCreatePlotline(bookId);
  const updatePlotline = useUpdatePlotline(bookId);
  const deletePlotline = useDeletePlotline(bookId);

  const [modal, setModal] = useState<
    { mode: "create" } | { mode: "edit"; plotline: Plotline } | null
  >(null);
  const [modalTitle, setModalTitle] = useState("");
  const [modalDesc, setModalDesc] = useState("");
  const [blocked, setBlocked] = useState<BlockedState | null>(null);

  function openCreate() {
    setModalTitle("");
    setModalDesc("");
    setModal({ mode: "create" });
  }

  function openEdit(pl: Plotline) {
    setModalTitle(pl.title);
    setModalDesc(pl.description);
    setModal({ mode: "edit", plotline: pl });
  }

  function handleSave() {
    const title = modalTitle.trim();
    if (!title) return;
    if (modal?.mode === "create") {
      createPlotline.mutate(
        { title, description: modalDesc.trim() || undefined },
        { onSuccess: () => setModal(null) },
      );
    } else if (modal?.mode === "edit") {
      updatePlotline.mutate(
        {
          pltId: modal.plotline.id,
          body: { title, description: modalDesc.trim() },
        },
        { onSuccess: () => setModal(null) },
      );
    }
  }

  async function handleDelete(pl: Plotline) {
    try {
      await deletePlotline.mutateAsync(pl.id);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setBlocked({
          name: pl.title,
          refs: parseBlockedRefs(err.detail),
        });
      }
    }
  }

  return (
    <div>
      {plotlines.length === 0 && !modal && (
        <div className="flex flex-col items-center py-12 text-ink-faint">
          <p className="mb-4 text-[0.875rem]">No plotlines yet</p>
          <Button variant="primary" onClick={openCreate}>
            + Add plotline
          </Button>
        </div>
      )}

      {plotlines.length > 0 && (
        <div className="space-y-1">
          {plotlines.map((pl) => (
            <div
              key={pl.id}
              className="flex items-center gap-3 rounded-control border border-line bg-surface px-3 py-2"
            >
              <button
                onClick={() => openEdit(pl)}
                className="flex-1 truncate text-left font-prose text-[0.875rem] text-ink hover:text-accent"
              >
                {pl.title}
              </button>

              {pl.description && (
                <span className="max-w-[200px] truncate text-[0.8125rem] text-ink-faint">
                  {pl.description}
                </span>
              )}

              <span className="rounded-full bg-accent-wash px-2 py-0.5 text-[0.75rem] font-ui text-accent">
                {pl.sceneCount}
              </span>

              <Button
                variant="ghost"
                onClick={() => handleDelete(pl)}
                className="shrink-0 !text-danger"
              >
                ✕
              </Button>
            </div>
          ))}
        </div>
      )}

      {plotlines.length > 0 && (
        <Button variant="primary" onClick={openCreate} className="mt-3">
          + Add plotline
        </Button>
      )}

      {modal && (
        <Modal
          title={modal.mode === "create" ? "New plotline" : "Edit plotline"}
          onClose={() => setModal(null)}
          footer={
            <>
              <Button variant="ghost" onClick={() => setModal(null)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={handleSave}
                disabled={!modalTitle.trim()}
              >
                Save
              </Button>
            </>
          }
        >
          <div className="space-y-4">
            <Field label="Title">
              <Input
                value={modalTitle}
                onChange={(e) => setModalTitle(e.target.value)}
                autoFocus
              />
            </Field>
            <Field label="Description">
              <textarea
                className="w-full rounded-control border border-line bg-surface px-2 py-2 text-[0.875rem] text-ink outline-none focus:border-accent"
                rows={3}
                value={modalDesc}
                onChange={(e) => setModalDesc(e.target.value)}
              />
            </Field>
          </div>
        </Modal>
      )}

      {blocked && (
        <BlockedDeletionDialog
          name={blocked.name}
          refs={blocked.refs}
          onClose={() => setBlocked(null)}
        />
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Book Tab                                                           */
/* ------------------------------------------------------------------ */

function BookTab({ bookId }: { bookId: string }) {
  const { data: book } = useBook(bookId);
  const patchBook = usePatchBook(bookId);

  const [storySummary, setStorySummary] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [summaryOnSave, setSummaryOnSave] = useState(false);
  const [charactersOnSave, setCharactersOnSave] = useState(false);

  useEffect(() => {
    if (!book) return;
    setStorySummary(book.storySummary);
    setSystemPrompt(book.systemPrompt);
    setSummaryOnSave(book.bookkeeping.summaryOnSave);
    setCharactersOnSave(book.bookkeeping.charactersOnSave);
  }, [book]);

  if (!book) return null;

  const isDirty =
    storySummary !== book.storySummary ||
    systemPrompt !== book.systemPrompt ||
    summaryOnSave !== book.bookkeeping.summaryOnSave ||
    charactersOnSave !== book.bookkeeping.charactersOnSave;

  function handleSave() {
    patchBook.mutate({
      storySummary,
      systemPrompt,
      bookkeeping: { summaryOnSave, charactersOnSave },
    });
  }

  return (
    <div className="space-y-5">
      <Field label="Story summary">
        <textarea
          className="w-full rounded-control border border-line bg-surface px-2 py-2 text-[0.875rem] text-ink outline-none focus:border-accent"
          rows={4}
          value={storySummary}
          onChange={(e) => setStorySummary(e.target.value)}
        />
      </Field>

      <Field
        label="System prompt"
        hint="Prepended to every AI request for this book"
      >
        <textarea
          className="w-full rounded-control border border-line bg-surface px-2 py-2 text-[0.875rem] text-ink outline-none focus:border-accent"
          rows={6}
          value={systemPrompt}
          onChange={(e) => setSystemPrompt(e.target.value)}
        />
      </Field>

      <div className="space-y-2">
        <label className="flex items-center gap-2 font-ui text-[0.875rem] text-ink">
          <input
            type="checkbox"
            checked={summaryOnSave}
            onChange={(e) => setSummaryOnSave(e.target.checked)}
          />
          Update summary when leaving scene
        </label>
        <label className="flex items-center gap-2 font-ui text-[0.875rem] text-ink">
          <input
            type="checkbox"
            checked={charactersOnSave}
            onChange={(e) => setCharactersOnSave(e.target.checked)}
          />
          Update character involvement when leaving scene
        </label>
      </div>

      <Button variant="primary" onClick={handleSave} disabled={!isDirty}>
        Save
      </Button>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Page                                                          */
/* ------------------------------------------------------------------ */

export default function MetadataPage() {
  const { bookId } = useParams<{ bookId: string }>();
  const [tab, setTab] = useState<TabKey>("parts");

  const book = useBook(bookId!);
  const parts = useParts(bookId!);
  const chapters = useChapters(bookId!);
  const plotlines = usePlotlines(bookId!);

  if (
    book.isLoading ||
    parts.isLoading ||
    chapters.isLoading ||
    plotlines.isLoading
  ) {
    return (
      <div className="mx-auto max-w-[720px] px-6 py-6 text-[0.875rem] text-ink-soft">
        Loading…
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[720px] px-6 py-6">
      <h1 className="mb-4 text-[20px] font-semibold text-ink">Metadata</h1>

      <div className="mb-6 flex gap-1 border-b border-line">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={[
              "-mb-px border-b-2 px-3 py-2 font-ui text-[0.875rem]",
              tab === t.key
                ? "border-accent text-accent"
                : "border-transparent text-ink-soft hover:text-ink",
            ].join(" ")}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "parts" && (
        <PartsTab bookId={bookId!} parts={parts.data ?? []} />
      )}
      {tab === "chapters" && (
        <ChaptersTab
          bookId={bookId!}
          chapters={chapters.data ?? []}
          parts={parts.data ?? []}
        />
      )}
      {tab === "plotlines" && (
        <PlotlinesTab bookId={bookId!} plotlines={plotlines.data ?? []} />
      )}
      {tab === "book" && <BookTab bookId={bookId!} />}
    </div>
  );
}
