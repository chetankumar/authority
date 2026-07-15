# styles — tokens & Tailwind mapping

The design-system foundation. Components never use raw hex — everything routes through CSS variables and the Tailwind mapping.

Parent: [src](../CLAUDE.md). Spec: [doc 06 §1.2–1.4](../../../../docs/claude-tech-specs/06-frontend-pages.md).

## Files to create here

- `tokens.css` — the CSS variables (the §1.2 palette below) + typography + spacing scale.
- Tailwind config mapping (in `frontend/tailwind.config.*`) that maps utility classes to these variables.

## Color tokens

`--paper #FAFAF8` (app bg) · `--surface #FFFFFF` (cards/modals/editor sheet) · `--ink #1F2328` (primary text) · `--ink-soft #5C6470` · `--ink-faint #9AA1AB` · `--line #E4E4DF` (borders) · `--accent #2F5A78` (primary/links/active/focus/trunk edges) · `--accent-wash #EBF1F5` · `--attn #B7791F` (amber — the single attention color) · `--attn-wash #FBF3E4` · `--ok #2F7D4F` / wash `#EAF4EE` · `--danger #A3382C` / wash `#F9ECEA`. Dark theme is out of v1 scope but tokens make it a drop-in.

## Typography

- **Prose** (editor + rendered markdown): **Literata** (bundled; fallback Georgia). 1.05rem/1.75; editor measure capped **68ch**; paragraphs spaced, not indented.
- **UI**: **Inter** (fallback system-ui). 0.875rem base; labels 0.75rem `--ink-soft` +0.02em; sentence case (no all-caps except 2-letter badges).
- **Data/mono**: ui-monospace stack, 0.8125rem (hashes, diffs, ids, word counts).
- Type scale: 12 / 13 / 14 / 16 / 20 / 24 / 30px. Page titles 20/semibold; modal titles 16/semibold.

## Space, shape, elevation

4px spacing scale; page gutters 24px; card padding 16px; control height 32px; dense grid rows 28px. Radii: 6px controls, 10px cards/modals, 999px pills. Borders over shadows; one soft shadow reserved for overlays: `0 8px 24px rgb(0 0 0 / 0.10)`.
