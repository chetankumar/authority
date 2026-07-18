import { useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import type {
  Character,
  CharacterInput,
  CharacterRelationship,
  CharacterRelationshipCategory,
} from "../../api/characters";
import { suggestVoice } from "../../api/audio";
import { ApiError } from "../../api/client";
import {
  useCharacters,
  useCreateCharacter,
  useUpdateCharacter,
  useDeleteCharacter,
  useCharacterRelationships,
  useCreateCharacterRelationship,
  useUpdateCharacterRelationship,
  useDeleteCharacterRelationship,
} from "../../queries/characters";
import { useElevenLabsVoices } from "../../queries/audio";
import { BlockedDeletionDialog, type BlockedRef } from "../../components/BlockedDeletionDialog";
import { SearchableSelect } from "../../components/SearchableSelect";
import { useToast } from "../../components/Toast";
import { Button, Field, Input, Select } from "../../components/ui";

const CATEGORY_LABELS: Record<CharacterRelationshipCategory, string> = {
  family: "Family",
  romantic: "Romantic",
  friendship: "Friendship",
  rivalry: "Rivalry",
  professional: "Professional",
  mentorship: "Mentorship",
  other: "Other",
};

const CATEGORIES = Object.keys(CATEGORY_LABELS) as CharacterRelationshipCategory[];

const EMPTY_FORM: CharacterInput = {
  name: "",
  aliases: [],
  age: "",
  gender: "",
  nationality: "",
  ethnicity: "",
  occupation: "",
  want: "",
  need: "",
  flaw: "",
  arc: "",
  personality: "",
  history: "",
  notes: "",
  voiceId: "",
  voiceName: "",
};

function toForm(c: Character): CharacterInput {
  return {
    name: c.name,
    aliases: c.aliases,
    age: c.age,
    gender: c.gender,
    nationality: c.nationality,
    ethnicity: c.ethnicity,
    occupation: c.occupation,
    want: c.want,
    need: c.need,
    flaw: c.flaw,
    arc: c.arc,
    personality: c.personality,
    history: c.history,
    notes: c.notes,
    voiceId: c.voiceId,
    voiceName: c.voiceName,
  };
}

function parseBlockedRefs(detail: Record<string, unknown>): BlockedRef[] {
  const blocked = detail.blockedBy;
  if (!blocked || typeof blocked !== "object") return [];
  const map = blocked as Record<string, unknown>;
  const labels: Record<string, string> = { scenes: "Scene", relationships: "Relationship" };
  const refs: BlockedRef[] = [];
  for (const [key, items] of Object.entries(map)) {
    if (!Array.isArray(items)) continue;
    const prefix = labels[key] || key;
    for (const item of items) {
      if (item && typeof item === "object" && "title" in item) {
        refs.push({ label: `${prefix}: ${(item as { title: string }).title}` });
      }
    }
  }
  return refs;
}

/* ------------------------------------------------------------------ */
/*  Aliases tag-input                                                  */
/* ------------------------------------------------------------------ */

function AliasesInput({
  value,
  onChange,
}: {
  value: string[];
  onChange: (v: string[]) => void;
}) {
  const [draft, setDraft] = useState("");

  function commit() {
    const v = draft.trim();
    if (v && !value.includes(v)) onChange([...value, v]);
    setDraft("");
  }

  return (
    <div>
      {value.length > 0 && (
        <div className="mb-1 flex flex-wrap gap-1">
          {value.map((a) => (
            <span
              key={a}
              className="inline-flex items-center gap-1 rounded-full bg-accent-wash px-2 py-0.5 text-[0.75rem] text-accent"
            >
              {a}
              <button
                type="button"
                onClick={() => onChange(value.filter((x) => x !== a))}
                className="hover:text-danger"
              >
                ✕
              </button>
            </span>
          ))}
        </div>
      )}
      <Input
        placeholder="Add an alias and press Enter — 'the Widow', 'Marlow'"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === ",") {
            e.preventDefault();
            commit();
          }
        }}
        onBlur={commit}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Relationships (within an expanded character row)                   */
/* ------------------------------------------------------------------ */

function RelationshipsSection({
  bookId,
  character,
  characters,
  relationships,
}: {
  bookId: string;
  character: Character;
  characters: Character[];
  relationships: CharacterRelationship[];
}) {
  const createRel = useCreateCharacterRelationship(bookId);
  const updateRel = useUpdateCharacterRelationship(bookId);
  const deleteRel = useDeleteCharacterRelationship(bookId);

  const [adding, setAdding] = useState(false);
  const [otherId, setOtherId] = useState<string | null>(null);
  const [category, setCategory] = useState<CharacterRelationshipCategory>("other");
  const [aToB, setAToB] = useState("");
  const [bToA, setBToA] = useState("");
  const [description, setDescription] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const byId = new Map(characters.map((c) => [c.id, c]));
  const mine = relationships.filter(
    (r) => r.characterAId === character.id || r.characterBId === character.id,
  );
  const otherOptions = characters
    .filter((c) => c.id !== character.id)
    .map((c) => ({ value: c.id, label: c.name }));

  function resetAdd() {
    setAdding(false);
    setOtherId(null);
    setCategory("other");
    setAToB("");
    setBToA("");
    setDescription("");
    setError(null);
  }

  function handleAdd() {
    if (!otherId || !aToB.trim() || !bToA.trim()) return;
    createRel.mutate(
      {
        characterAId: character.id,
        characterBId: otherId,
        category,
        aToB: aToB.trim(),
        bToA: bToA.trim(),
        description: description.trim(),
      },
      { onSuccess: () => resetAdd(), onError: (err) => setError(err instanceof Error ? err.message : "Couldn't save.") },
    );
  }

  async function handleDelete(rel: CharacterRelationship) {
    await deleteRel.mutateAsync(rel.id);
  }

  return (
    <div className="mt-4 border-t border-line pt-3">
      <h4 className="mb-2 font-ui text-[0.75rem] uppercase tracking-wider text-ink-soft">
        Relationships
      </h4>

      {mine.length === 0 && !adding && (
        <p className="mb-2 text-[0.8125rem] text-ink-faint">No relationships recorded yet.</p>
      )}

      <div className="space-y-1">
        {mine.map((r) => {
          const isA = r.characterAId === character.id;
          const other = byId.get(isA ? r.characterBId : r.characterAId);
          const label = isA ? r.aToB : r.bToA;
          const editing = editingId === r.id;
          return (
            <div
              key={r.id}
              className="rounded-control border border-line bg-paper px-3 py-2 text-[0.8125rem]"
            >
              {editing ? (
                <div className="space-y-2">
                  <div className="flex gap-2">
                    <Select
                      value={r.category}
                      onChange={(e) =>
                        updateRel.mutate({
                          relId: r.id,
                          body: { category: e.target.value as CharacterRelationshipCategory },
                        })
                      }
                      style={{ width: "9rem", flex: "none" }}
                    >
                      {CATEGORIES.map((c) => (
                        <option key={c} value={c}>
                          {CATEGORY_LABELS[c]}
                        </option>
                      ))}
                    </Select>
                    <Input
                      defaultValue={r.aToB}
                      placeholder="A → B"
                      onBlur={(e) => {
                        if (e.target.value.trim() && e.target.value !== r.aToB)
                          updateRel.mutate({ relId: r.id, body: { aToB: e.target.value.trim() } });
                      }}
                    />
                    <Input
                      defaultValue={r.bToA}
                      placeholder="B → A"
                      onBlur={(e) => {
                        if (e.target.value.trim() && e.target.value !== r.bToA)
                          updateRel.mutate({ relId: r.id, body: { bToA: e.target.value.trim() } });
                      }}
                    />
                  </div>
                  <textarea
                    className="w-full rounded-control border border-line bg-surface px-2 py-1.5 text-[0.8125rem] text-ink outline-none focus:border-accent"
                    rows={2}
                    defaultValue={r.description}
                    placeholder="Dynamic / nuance"
                    onBlur={(e) => {
                      if (e.target.value !== r.description)
                        updateRel.mutate({ relId: r.id, body: { description: e.target.value } });
                    }}
                  />
                  <Button variant="ghost" onClick={() => setEditingId(null)}>
                    Done
                  </Button>
                </div>
              ) : (
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="text-ink">
                      <strong>{character.name}</strong> is <em>{label}</em>{" "}
                      <strong>{other?.name ?? "(unknown)"}</strong>
                    </span>
                    <div className="mt-0.5 text-[0.75rem] text-ink-faint">
                      {CATEGORY_LABELS[r.category]}
                      {r.description ? ` · ${r.description}` : ""}
                    </div>
                  </div>
                  <div className="flex shrink-0 gap-1">
                    <Button variant="ghost" onClick={() => setEditingId(r.id)}>
                      ✎
                    </Button>
                    <Button variant="ghost" className="!text-danger" onClick={() => handleDelete(r)}>
                      ✕
                    </Button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {adding ? (
        <div className="mt-2 space-y-2 rounded-control border border-line bg-paper px-3 py-2">
          <Field label="Related to">
            <SearchableSelect
              options={otherOptions}
              value={otherId}
              onChange={setOtherId}
              placeholder="Choose a character…"
            />
          </Field>
          <Field label="Category">
            <Select
              value={category}
              onChange={(e) => setCategory(e.target.value as CharacterRelationshipCategory)}
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {CATEGORY_LABELS[c]}
                </option>
              ))}
            </Select>
          </Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label={`${character.name} is ___ to them`} hint="e.g. 'mother of'">
              <Input value={aToB} onChange={(e) => setAToB(e.target.value)} />
            </Field>
            <Field label="They are ___ to this character" hint="e.g. 'daughter of'">
              <Input value={bToA} onChange={(e) => setBToA(e.target.value)} />
            </Field>
          </div>
          <Field label="Description" hint="The dynamic — tension, history, nuance">
            <textarea
              className="w-full rounded-control border border-line bg-surface px-2 py-1.5 text-[0.8125rem] text-ink outline-none focus:border-accent"
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </Field>
          {error && <p className="text-[0.75rem] text-danger">{error}</p>}
          <div className="flex gap-2">
            <Button
              variant="primary"
              onClick={handleAdd}
              disabled={!otherId || !aToB.trim() || !bToA.trim()}
            >
              Save relationship
            </Button>
            <Button variant="ghost" onClick={resetAdd}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        otherOptions.length > 0 && (
          <Button variant="ghost" onClick={() => setAdding(true)} className="mt-2">
            + Add relationship
          </Button>
        )
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Character row (collapsed + expanded edit form)                     */
/* ------------------------------------------------------------------ */

function CharacterRow({
  bookId,
  character,
  characters,
  relationships,
  expanded,
  onToggle,
}: {
  bookId: string;
  character: Character;
  characters: Character[];
  relationships: CharacterRelationship[];
  expanded: boolean;
  onToggle: () => void;
}) {
  const updateCharacter = useUpdateCharacter(bookId);
  const deleteCharacter = useDeleteCharacter(bookId);
  const voicesQ = useElevenLabsVoices();
  const toast = useToast();

  const [form, setForm] = useState<CharacterInput>(() => toForm(character));
  const [conflict, setConflict] = useState<string | null>(null);
  const [blocked, setBlocked] = useState<{ name: string; refs: BlockedRef[] } | null>(null);
  const [suggesting, setSuggesting] = useState(false);
  const [suggestRationale, setSuggestRationale] = useState<string | null>(null);

  useEffect(() => {
    if (expanded) setForm(toForm(character));
  }, [expanded, character]);

  function set<K extends keyof CharacterInput>(key: K, value: CharacterInput[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function handleSave() {
    setConflict(null);
    updateCharacter.mutate(
      { chrId: character.id, body: form },
      {
        onSuccess: onToggle,
        onError: (err) => {
          if (err instanceof ApiError && err.status === 422) {
            const c = err.detail.fields as Record<string, unknown> | undefined;
            const conflictVal = c?.conflict as { value?: string; existingCharacter?: { name?: string } } | undefined;
            setConflict(
              conflictVal
                ? `Already used by ${conflictVal.existingCharacter?.name ?? "another character"}.`
                : "Couldn't save.",
            );
          }
        },
      },
    );
  }

  async function handleDelete() {
    try {
      await deleteCharacter.mutateAsync(character.id);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setBlocked({ name: character.name, refs: parseBlockedRefs(err.detail) });
      }
    }
  }

  if (!expanded) {
    return (
      <button
        onClick={onToggle}
        className="flex w-full items-center gap-3 rounded-control border border-line bg-surface px-3 py-2 text-left"
      >
        <span className="flex-1 truncate">
          <span className="font-prose text-[0.9375rem] text-ink">{character.name}</span>
          {character.personality && (
            <span className="ml-2 truncate text-[0.8125rem] text-ink-faint">
              {character.personality}
            </span>
          )}
        </span>
        <span className="shrink-0 rounded-full bg-accent-wash px-2 py-0.5 text-[0.75rem] font-ui text-accent">
          {character.sceneCount}
        </span>
      </button>
    );
  }

  return (
    <div className="rounded-control border border-accent bg-surface px-4 py-4">
      <div className="grid grid-cols-2 gap-3">
        <Field label="Name" error={conflict ?? undefined}>
          <Input value={form.name} onChange={(e) => set("name", e.target.value)} autoFocus />
        </Field>
        <Field label="Aliases" hint="Nicknames and titles the prose uses">
          <AliasesInput value={form.aliases ?? []} onChange={(v) => set("aliases", v)} />
        </Field>
      </div>

      <h4 className="mb-2 mt-4 font-ui text-[0.75rem] uppercase tracking-wider text-ink-soft">
        Identity
      </h4>
      <div className="grid grid-cols-3 gap-3">
        <Field label="Age" hint="e.g. '34' or 'mid-30s'">
          <Input value={form.age} onChange={(e) => set("age", e.target.value)} />
        </Field>
        <Field label="Gender">
          <Input value={form.gender} onChange={(e) => set("gender", e.target.value)} />
        </Field>
        <Field label="Occupation">
          <Input value={form.occupation} onChange={(e) => set("occupation", e.target.value)} />
        </Field>
        <Field label="Nationality">
          <Input value={form.nationality} onChange={(e) => set("nationality", e.target.value)} />
        </Field>
        <Field label="Ethnicity">
          <Input value={form.ethnicity} onChange={(e) => set("ethnicity", e.target.value)} />
        </Field>
      </div>

      <h4 className="mb-2 mt-4 font-ui text-[0.75rem] uppercase tracking-wider text-ink-soft">
        Craft
      </h4>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Want" hint="The external, plot-visible goal">
          <Input value={form.want} onChange={(e) => set("want", e.target.value)} />
        </Field>
        <Field label="Need" hint="The internal truth, often in tension with the want">
          <Input value={form.need} onChange={(e) => set("need", e.target.value)} />
        </Field>
        <Field label="Flaw" hint="What drives the conflict">
          <Input value={form.flaw} onChange={(e) => set("flaw", e.target.value)} />
        </Field>
        <Field label="Arc" hint="How they change over the story">
          <Input value={form.arc} onChange={(e) => set("arc", e.target.value)} />
        </Field>
      </div>
      <div className="mt-3 space-y-3">
        <Field label="Personality">
          <textarea
            className="w-full rounded-control border border-line bg-surface px-2 py-2 text-[0.875rem] text-ink outline-none focus:border-accent"
            rows={2}
            value={form.personality}
            onChange={(e) => set("personality", e.target.value)}
          />
        </Field>
        <Field label="History">
          <textarea
            className="w-full rounded-control border border-line bg-surface px-2 py-2 text-[0.875rem] text-ink outline-none focus:border-accent"
            rows={3}
            value={form.history}
            onChange={(e) => set("history", e.target.value)}
          />
        </Field>
        <Field label="Notes">
          <textarea
            className="w-full rounded-control border border-line bg-surface px-2 py-2 text-[0.875rem] text-ink outline-none focus:border-accent"
            rows={2}
            value={form.notes}
            onChange={(e) => set("notes", e.target.value)}
          />
        </Field>
      </div>

      <h4 className="mb-2 mt-4 font-ui text-[0.75rem] uppercase tracking-wider text-ink-soft">
        Voice
      </h4>
      <div className="space-y-2">
        <Field label="ElevenLabs voice" hint="Used when generating scene audio for this character">
          <div className="flex flex-wrap items-center gap-2">
            <div className="min-w-[14rem] flex-1">
              <SearchableSelect
                options={(voicesQ.data ?? []).map((v) => ({
                  value: v.voiceId,
                  label: `${v.name}${v.gender || v.age || v.accent ? ` (${[v.gender, v.age, v.accent].filter(Boolean).join(", ")})` : ""}`,
                  hint: v.description || undefined,
                }))}
                value={form.voiceId || null}
                onChange={(v) => {
                  const voice = (voicesQ.data ?? []).find((x) => x.voiceId === v);
                  setForm((f) => ({ ...f, voiceId: v ?? "", voiceName: voice?.name ?? "" }));
                }}
                placeholder="Choose a voice…"
                clearable
              />
            </div>
            {form.voiceId && (voicesQ.data ?? []).find((v) => v.voiceId === form.voiceId)?.previewUrl && (
              <audio
                controls
                className="h-8 max-w-[12rem]"
                src={(voicesQ.data ?? []).find((v) => v.voiceId === form.voiceId)?.previewUrl}
              />
            )}
            <Button
              variant="secondary"
              disabled={suggesting}
              onClick={() => {
                setSuggesting(true);
                void suggestVoice(bookId, character.id)
                  .then((res) => {
                    if (res.voiceId) {
                      const voice = (voicesQ.data ?? []).find((x) => x.voiceId === res.voiceId);
                      setForm((f) => ({
                        ...f,
                        voiceId: res.voiceId!,
                        voiceName: voice?.name ?? f.voiceName ?? "",
                      }));
                      setSuggestRationale(res.rationale || null);
                    } else {
                      toast.error(res.rationale || "No suggestion returned");
                    }
                  })
                  .catch((err) =>
                    toast.error(err instanceof ApiError ? err.message : "Suggest failed"),
                  )
                  .finally(() => setSuggesting(false));
              }}
            >
              {suggesting ? "Suggesting…" : "Suggest voice"}
            </Button>
          </div>
          {suggestRationale && (
            <p className="mt-1 text-[0.75rem] text-ink-faint">{suggestRationale}</p>
          )}
        </Field>
      </div>

      <RelationshipsSection
        bookId={bookId}
        character={character}
        characters={characters}
        relationships={relationships}
      />

      <div className="mt-4 flex items-center justify-between border-t border-line pt-3">
        <Button variant="ghost" className="!text-danger" onClick={handleDelete}>
          Delete
        </Button>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={onToggle}>
            Cancel
          </Button>
          <Button variant="primary" onClick={handleSave} disabled={!form.name?.trim()}>
            Save
          </Button>
        </div>
      </div>

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
/*  Add character                                                      */
/* ------------------------------------------------------------------ */

function AddCharacterForm({ bookId, onDone }: { bookId: string; onDone: () => void }) {
  const createCharacter = useCreateCharacter(bookId);
  const [form, setForm] = useState<CharacterInput>({ ...EMPTY_FORM });
  const [conflict, setConflict] = useState<string | null>(null);

  function set<K extends keyof CharacterInput>(key: K, value: CharacterInput[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function handleSave() {
    setConflict(null);
    createCharacter.mutate(form, {
      onSuccess: onDone,
      onError: (err) => {
        if (err instanceof ApiError && err.status === 422) {
          const c = err.detail.fields as Record<string, unknown> | undefined;
          const conflictVal = c?.conflict as { existingCharacter?: { name?: string } } | undefined;
          setConflict(
            conflictVal
              ? `Already used by ${conflictVal.existingCharacter?.name ?? "another character"}.`
              : "Couldn't save.",
          );
        }
      },
    });
  }

  return (
    <div className="rounded-control border border-accent bg-surface px-4 py-4">
      <div className="grid grid-cols-2 gap-3">
        <Field label="Name" error={conflict ?? undefined}>
          <Input value={form.name} onChange={(e) => set("name", e.target.value)} autoFocus />
        </Field>
        <Field label="Aliases">
          <AliasesInput value={form.aliases ?? []} onChange={(v) => set("aliases", v)} />
        </Field>
      </div>
      <p className="mt-3 text-[0.8125rem] text-ink-faint">
        Everything else — demographics, want/need/flaw/arc, relationships — can be filled in
        after saving.
      </p>
      <div className="mt-4 flex justify-end gap-2 border-t border-line pt-3">
        <Button variant="ghost" onClick={onDone}>
          Cancel
        </Button>
        <Button variant="primary" onClick={handleSave} disabled={!form.name?.trim()}>
          Save
        </Button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main page                                                          */
/* ------------------------------------------------------------------ */

export default function CharactersPage() {
  const { bookId } = useParams<{ bookId: string }>();
  const characters = useCharacters(bookId!);
  const relationships = useCharacterRelationships(bookId!);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  if (characters.isLoading || relationships.isLoading) {
    return (
      <div className="mx-auto max-w-[640px] px-6 py-6 text-[0.875rem] text-ink-soft">
        Loading…
      </div>
    );
  }

  const list = characters.data ?? [];
  const rels = relationships.data ?? [];

  return (
    <div className="mx-auto max-w-[640px] px-6 py-6">
      <div className="mb-4 flex items-center justify-between rounded-card border border-line bg-surface px-4 py-3">
        <h1 className="text-[20px] font-semibold text-ink">Character Sheet</h1>
        {!adding && (
          <Button variant="primary" onClick={() => setAdding(true)}>
            + Add character
          </Button>
        )}
      </div>

      {list.length === 0 && !adding && (
        <div className="flex flex-col items-center py-12 text-ink-faint">
          <p className="text-[0.875rem]">No characters yet</p>
        </div>
      )}

      <div className="space-y-2">
        {adding && (
          <AddCharacterForm bookId={bookId!} onDone={() => setAdding(false)} />
        )}
        {list.map((c) => (
          <CharacterRow
            key={c.id}
            bookId={bookId!}
            character={c}
            characters={list}
            relationships={rels}
            expanded={expandedId === c.id}
            onToggle={() => setExpandedId((id) => (id === c.id ? null : c.id))}
          />
        ))}
      </div>
    </div>
  );
}
