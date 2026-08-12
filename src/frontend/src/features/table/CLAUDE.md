# features/table — `/book/{id}/table` (Scene Table)

The working ledger: sort, filter, scan, bulk-see. Toolbar above a full-height AG Grid (Community). Parent: [features](../CLAUDE.md). Spec: [doc 06 §7](../../../../../docs/claude-tech-specs/06-frontend-pages.md).

## Toolbar

Left — segmented filter **All / Placed / Floating** + **Archived** toggle. Right — [Columns ▾] popover (checkbox list) + [＋ Add scene] (primary).

**Placement filter:** each scene's `placement` is computed server-side (ChainService) — never stored. **All** shows every active scene; **Placed** = `trunk` + `unanchored`; **Floating** = `floating` + `orphan`. Client-side filter over the cached `GET /scenes` list.

## Grid

Default columns: Seq · Title · Description · Characters · Chapter · Part · Mood. Available also: Location, Date/Time, Emotional Arc, Summary, Words, Updated. Seq ascending default; non-trunk rows carry a placement chip (`unanchored ~`, `floating`, `orphan`); archived rows `--ink-faint` + strikethrough title (only with the toggle). Column state changes → debounced `PATCH /books/{id}/ui` as `tableColumnState`; restored on load.

**Part column:** displays `scene.partId` when the scene is assigned directly to a part. When the scene is in a chapter (`chapterId` set, `partId` null per API XOR rule), the Part cell shows that chapter's `partId` title — display-only inference in the frontend valueGetter, not stored on the scene.

## Controls

- Row click → editor. Row action ✎ → Scene Modal. Row menu → Archive/Unarchive → `PATCH /scenes/{id} {status}` → toast.
- Filter segments = client-side placement filter. Seq header click = restore story order.

### Column chooser (Columns ▾)

Custom inline panel (not the shared Popover component). Closes on outside-click and Esc.

- **Checkbox list** built from `columnDefs` (which columns exist + colId strings).
- **Checked state** read from AG Grid `getColumnState()` (`!col.hide`) — not from React state or `columnDefs`.
- **Toggle** clones the full column-state array, flips one column's `hide` flag, calls `applyColumnState({ state })` — never `setColumnsVisible` on a single column alone.
- **Optional columns** use `initialHide: true` in ColDef, **not** `hide: true`. AG Grid treats `hide` as stateful and re-applies it when the React wrapper re-renders, which undid author toggles (columns flickered off after ~1 frame). `initialHide` applies only at column creation; after that visibility is owned by `applyColumnState` and `ui.json` restore.
- **`columnDefs`** is `useMemo(..., [])` with stable refs for chapter/part lookups and action-cell callbacks — a new array reference would also reset column state.
- **Persist:** debounced ~1s `PATCH /books/{id}/ui { tableColumnState }` on column move/resize/visible/sort.
- **Restore:** `applyColumnState` from `ui.json` once per visit (`onGridReady` + effect when ui loads); blocked after first apply or after the author toggles a column (`userModifiedColumnsRef`).

## APIs

`GET /books/{b}/scenes`, `PATCH /scenes/{id}`, `GET/PATCH /books/{id}/ui`.

Implementation: [`ScenesTablePage.tsx`](ScenesTablePage.tsx).
