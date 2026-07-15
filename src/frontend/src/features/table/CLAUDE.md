# features/table — `/book/{id}/table` (Scene Table)

The working ledger: sort, filter, scan, bulk-see. Toolbar above a full-height AG Grid (Community). Parent: [features](../CLAUDE.md). Spec: [doc 06 §7](../../../../../docs/claude-tech-specs/06-frontend-pages.md).

## Toolbar

Left — segmented filter **All / Placed / Floating** + **Archived** toggle. Right — [Columns ▾] popover (checkbox list) + [＋ Add scene] (primary).

## Grid

Default columns: Seq · Title · Description · Characters · Chapter · Part · Mood. Available also: Location, Date/Time, Emotional Arc, Summary, Words, Updated. Seq ascending default; non-trunk rows carry a placement chip (`unanchored ~`, `floating`, `orphan`); archived rows `--ink-faint` + strikethrough title (only with the toggle). Column state changes → debounced `PATCH /books/{id}/ui`; restored on load.

## Controls

- Row click → editor. Row action ✎ → Scene Modal. Row menu → Archive/Unarchive → `PATCH /scenes/{id} {status}` → toast.
- Filter segments = client-side placement filter. Column chooser = AG Grid column API + ui.json persistence. Seq header click = restore story order.

## APIs

`GET /books/{b}/scenes`, `PATCH /scenes/{id}`, `GET/PATCH /books/{id}/ui`.
