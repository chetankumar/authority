// Scene Modal (doc 06 §8) — everything about a scene that isn't its prose.
// Create shows Basics only; edit shows all tabs (Characters/Summary/Dependencies
// arrive with later phases and render disabled for now). Basics is fully built:
// Title/Description/free-text fields + Sequence (splice) + Soft placement + Structure.
import { useMemo, useState } from "react";

import { ConfirmDialog } from "../../components/ConfirmDialog";
import { Modal } from "../../components/Modal";
import { SearchableSelect, type Option } from "../../components/SearchableSelect";
import { Button, Field, Input } from "../../components/ui";
import { ApiError } from "../../api/client";
import { END_ID, START_ID, type RelationshipType, type Scene } from "../../api/scenes";
import { useBook } from "../../queries/books";
import {
  useCreateRelationship,
  useCreateScene,
  useDeleteRelationship,
  useDeleteScene,
  useScenes,
  useUpdateScene,
} from "../../queries/scenes";

interface Props {
  bookId: string;
  /** null → create mode. */
  sceneId: string | null;
  /** Prefill Previous in create mode (editor "Next with no neighbor" flow). */
  initialPrevious?: string | null;
  onClose: () => void;
  onSaved?: (scene: Scene) => void;
}

interface SoftRow {
  type: RelationshipType;
  sceneId: string;
  existingRelId?: string;
}

const TABS = ["Basics", "Characters", "Summary", "Dependencies"] as const;
const SOFT_LABEL: Record<RelationshipType, string> = {
  before: "definitely before",
  after: "definitely after",
  around: "around",
};

export function SceneModal({ bookId, sceneId, initialPrevious = null, onClose, onSaved }: Props) {
  const isEdit = sceneId !== null;
  const scenesQ = useScenes(bookId);
  const bookQ = useBook(bookId);

  const scenes = scenesQ.data?.scenes ?? [];
  const relationships = scenesQ.data?.relationships ?? [];
  const existing = isEdit ? scenes.find((s) => s.id === sceneId) : undefined;

  const [tab, setTab] = useState<(typeof TABS)[number]>("Basics");
  const [title, setTitle] = useState(existing?.title ?? "");
  const [description, setDescription] = useState(existing?.description ?? "");
  const [location, setLocation] = useState(existing?.location ?? "");
  const [dateTime, setDateTime] = useState(existing?.dateTime ?? "");
  const [mood, setMood] = useState(existing?.mood ?? "");
  const [emotionalArc, setEmotionalArc] = useState(existing?.emotionalArc ?? "");
  const [previousSceneId, setPreviousSceneId] = useState<string | null>(
    existing?.previousSceneId ?? initialPrevious,
  );
  const [nextSceneId, setNextSceneId] = useState<string | null>(existing?.nextSceneId ?? null);
  const [chapterId, setChapterId] = useState<string | null>(existing?.chapterId ?? null);
  const [partId, setPartId] = useState<string | null>(existing?.partId ?? null);
  const [softRows, setSoftRows] = useState<SoftRow[]>(
    relationships
      .filter((r) => r.fromSceneId === sceneId)
      .map((r) => ({ type: r.type, sceneId: r.toSceneId, existingRelId: r.id })),
  );
  const [error, setError] = useState<string | null>(null);

  const createScene = useCreateScene(bookId);
  const updateScene = useUpdateScene(bookId);
  const deleteSceneMut = useDeleteScene(bookId);
  const createRel = useCreateRelationship(bookId);
  const deleteRel = useDeleteRelationship(bookId);
  const saving = createScene.isPending || updateScene.isPending;
  const [confirmDelete, setConfirmDelete] = useState(false);
  const isArchived = existing?.status === "archived";

  // Options: active scenes excluding self, in seq order.
  const sceneOptions = useMemo<Option[]>(
    () =>
      scenes
        .filter((s) => s.status === "active" && s.id !== sceneId)
        .sort((a, b) => (a.seq ?? 0) - (b.seq ?? 0))
        .map((s) => ({ value: s.id, label: s.title, hint: s.seq ? `#${s.seq}` : undefined })),
    [scenes, sceneId],
  );
  const previousOptions: Option[] = [{ value: START_ID, label: "Start", hint: "start" }, ...sceneOptions];
  const nextOptions: Option[] = [...sceneOptions, { value: END_ID, label: "The End", hint: "end" }];

  const chapterOptions: Option[] = (bookQ.data?.chapters ?? []).map((c) => ({ value: c.id, label: c.title || "Untitled chapter" }));
  const partOptions: Option[] = (bookQ.data?.parts ?? []).map((p) => ({ value: p.id, label: p.title || "Untitled part" }));

  // Previous & Next are a coupled adjacent slot (previous → [this] → next). Picking
  // one end snaps the other so they always describe a real gap in the chain — every
  // save is a clean splice, never a "jump over" a scene. Both stay editable.
  const successorOf = (prevId: string): string | null => {
    if (prevId === START_ID) {
      const head = scenes.find((s) => s.previousSceneId === START_ID);
      const id = head?.id ?? END_ID;
      return id === sceneId ? existing?.nextSceneId ?? END_ID : id;
    }
    const nxt = scenes.find((s) => s.id === prevId)?.nextSceneId ?? null;
    return nxt === sceneId ? existing?.nextSceneId ?? null : nxt; // skip self when re-placing
  };
  const predecessorOf = (nextId: string): string | null => {
    if (nextId === END_ID) {
      const tail = scenes.find((s) => s.nextSceneId === END_ID);
      const id = tail?.id ?? START_ID;
      return id === sceneId ? existing?.previousSceneId ?? START_ID : id;
    }
    const prv = scenes.find((s) => s.id === nextId)?.previousSceneId ?? null;
    return prv === sceneId ? existing?.previousSceneId ?? null : prv;
  };
  const pickPrevious = (p: string | null) => {
    setPreviousSceneId(p);
    setNextSceneId(p ? successorOf(p) : null); // clearing one clears both → floats
  };
  const pickNext = (n: string | null) => {
    setNextSceneId(n);
    setPreviousSceneId(n ? predecessorOf(n) : null);
  };

  const setSoft = (i: number, patch: Partial<SoftRow>) =>
    setSoftRows((rows) => rows.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));

  async function handleSave() {
    setError(null);
    if (!title.trim()) return setError("Give the scene a title.");
    if (!description.trim()) return setError("A one-line description is required.");
    try {
      if (!isEdit) {
        const result = await createScene.mutateAsync({
          title: title.trim(),
          description: description.trim(),
          previousSceneId,
          nextSceneId,
          chapterId,
          partId,
          location,
          dateTime,
          mood,
          emotionalArc,
          softRelations: softRows
            .filter((r) => r.sceneId)
            .map((r) => ({ type: r.type, sceneId: r.sceneId })),
        });
        onSaved?.(result.scene);
      } else {
        // Send Previous and Next together as one placement — the backend sets
        // both atomically, so changing one never drops the other.
        const body = {
          title: title.trim(),
          description: description.trim(),
          location,
          dateTime,
          mood,
          emotionalArc,
          chapterId,
          partId,
          previousSceneId,
          nextSceneId,
        };
        const result = await updateScene.mutateAsync({ sceneId: sceneId!, body });

        // Diff soft-placement rows → create added, delete removed.
        const originals = relationships.filter((r) => r.fromSceneId === sceneId);
        const keptIds = new Set(softRows.map((r) => r.existingRelId).filter(Boolean));
        for (const o of originals) if (!keptIds.has(o.id)) await deleteRel.mutateAsync(o.id);
        for (const r of softRows)
          if (!r.existingRelId && r.sceneId)
            await createRel.mutateAsync({ fromSceneId: sceneId!, toSceneId: r.sceneId, type: r.type });

        onSaved?.(result.scene);
      }
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't save the scene.");
    }
  }

  async function handleArchiveToggle() {
    if (!isEdit) return;
    const newStatus = isArchived ? "active" : "archived";
    try {
      await updateScene.mutateAsync({ sceneId: sceneId!, body: { status: newStatus } });
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : `Couldn't ${isArchived ? "unarchive" : "archive"} the scene.`);
    }
  }

  async function handleDelete() {
    if (!isEdit) return;
    try {
      await deleteSceneMut.mutateAsync(sceneId!);
      onClose();
    } catch (e) {
      setConfirmDelete(false);
      setError(e instanceof ApiError ? e.message : "Couldn't delete the scene.");
    }
  }

  const footer = (
    <div className="flex w-full items-center justify-between">
      {isEdit ? (
        <div className="flex gap-2">
          <Button variant="ghost" onClick={handleArchiveToggle} className={isArchived ? "text-accent" : "text-danger"}>
            {isArchived ? "Unarchive scene" : "Archive scene"}
          </Button>
          {isArchived && (
            <Button variant="ghost" onClick={() => setConfirmDelete(true)} className="text-danger">
              Delete scene
            </Button>
          )}
        </div>
      ) : (
        <span />
      )}
      <div className="flex gap-2">
        <Button variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <Button variant="primary" onClick={handleSave} disabled={saving}>
          {saving ? "Saving…" : "Save scene"}
        </Button>
      </div>
    </div>
  );

  return (
    <Modal title={isEdit ? "Scene" : "Add scene"} width={720} onClose={onClose} footer={footer}>
      {isEdit && (
        <div className="mb-4 flex gap-1 border-b border-line">
          {TABS.map((t) => {
            const disabled = t !== "Basics";
            return (
              <button
                key={t}
                disabled={disabled}
                onClick={() => setTab(t)}
                title={disabled ? "Arrives in a later phase" : undefined}
                className={`-mb-px border-b-2 px-3 py-1.5 text-[0.8125rem] ${
                  tab === t ? "border-accent text-accent" : "border-transparent text-ink-soft"
                } ${disabled ? "cursor-not-allowed opacity-40" : "hover:text-ink"}`}
              >
                {t}
                {disabled && <span className="ml-1 text-[0.625rem] text-ink-faint">soon</span>}
              </button>
            );
          })}
        </div>
      )}

      <div className="grid grid-cols-2 gap-5">
        {/* Left column — the scene's facts */}
        <div className="space-y-3">
          <Field label="Title">
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Scene title" />
          </Field>
          <Field label="Description" hint="One line — what happens in this scene.">
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full rounded-control border border-line bg-surface px-2 py-1.5 text-[0.875rem] text-ink outline-none focus:border-accent"
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Location">
              <Input value={location} onChange={(e) => setLocation(e.target.value)} />
            </Field>
            <Field label="Date / Time">
              <Input value={dateTime} onChange={(e) => setDateTime(e.target.value)} />
            </Field>
            <Field label="Mood">
              <Input value={mood} onChange={(e) => setMood(e.target.value)} />
            </Field>
            <Field label="Emotional arc">
              <Input value={emotionalArc} onChange={(e) => setEmotionalArc(e.target.value)} />
            </Field>
          </div>
        </div>

        {/* Right column — placement */}
        <div className="space-y-4">
          <fieldset className="space-y-2">
            <legend className="text-[0.75rem] font-medium text-ink-soft">Sequence</legend>
            <Field label="Previous">
              <SearchableSelect
                options={previousOptions}
                value={previousSceneId}
                onChange={pickPrevious}
                clearable
                clearLabel="— unplaced —"
                placeholder="No previous scene"
              />
            </Field>
            <Field label="Next">
              <SearchableSelect
                options={nextOptions}
                value={nextSceneId}
                onChange={pickNext}
                clearable
                clearLabel="— unplaced —"
                placeholder="No next scene"
              />
            </Field>
            <p className="text-[0.6875rem] text-ink-faint">Pick either end — the other fills in to keep the scene in sequence.</p>
          </fieldset>

          <fieldset className="space-y-2">
            <legend className="text-[0.75rem] font-medium text-ink-soft">Soft placement</legend>
            {softRows.map((row, i) => (
              <div key={i} className="flex items-center gap-1.5">
                <select
                  value={row.type}
                  onChange={(e) => setSoft(i, { type: e.target.value as RelationshipType })}
                  className="h-8 shrink-0 rounded-control border border-line bg-surface px-1 text-[0.8125rem] outline-none focus:border-accent"
                >
                  {(["before", "after", "around"] as RelationshipType[]).map((t) => (
                    <option key={t} value={t}>
                      {SOFT_LABEL[t]}
                    </option>
                  ))}
                </select>
                <div className="min-w-0 flex-1">
                  <SearchableSelect
                    options={sceneOptions}
                    value={row.sceneId || null}
                    onChange={(v) => setSoft(i, { sceneId: v ?? "" })}
                    placeholder="scene…"
                  />
                </div>
                <button
                  onClick={() => setSoftRows((rows) => rows.filter((_, idx) => idx !== i))}
                  className="shrink-0 px-1 text-ink-faint hover:text-danger"
                  aria-label="Remove placement"
                >
                  ✕
                </button>
              </div>
            ))}
            <Button
              variant="ghost"
              onClick={() => setSoftRows((rows) => [...rows, { type: "after", sceneId: "" }])}
              className="text-[0.8125rem] text-accent"
            >
              + Add placement
            </Button>
          </fieldset>

          <fieldset className="space-y-2">
            <legend className="text-[0.75rem] font-medium text-ink-soft">Structure</legend>
            <Field label="Chapter">
              <SearchableSelect
                options={chapterOptions}
                value={chapterId}
                onChange={(v) => {
                  setChapterId(v);
                  if (v) setPartId(null);
                }}
                clearable
                disabled={!!partId}
                placeholder={chapterOptions.length ? "Choose a chapter" : "No chapters yet"}
              />
            </Field>
            <Field label="Part">
              <SearchableSelect
                options={partOptions}
                value={partId}
                onChange={(v) => {
                  setPartId(v);
                  if (v) setChapterId(null);
                }}
                clearable
                disabled={!!chapterId}
                placeholder={partOptions.length ? "Choose a part" : "No parts yet"}
              />
            </Field>
            <p className="text-[0.6875rem] text-ink-faint">A scene belongs to a chapter or directly to a part.</p>
          </fieldset>
        </div>
      </div>

      {error && <p className="mt-4 text-[0.8125rem] text-danger">{error}</p>}

      {confirmDelete && (
        <ConfirmDialog
          title={`Delete "${existing?.title}"?`}
          message="This scene's prose file will be moved to the book's .trash folder. The scene record will be permanently removed from the book."
          confirmLabel="Delete scene"
          onConfirm={handleDelete}
          onCancel={() => setConfirmDelete(false)}
        />
      )}
    </Modal>
  );
}
