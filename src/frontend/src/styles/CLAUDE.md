# styles — tokens & Tailwind mapping

The design-system foundation. Components never use raw hex — everything routes through CSS variables and the Tailwind mapping.

Parent: [src](../CLAUDE.md). Spec: [doc 06 §1.2–1.4](../../../../docs/claude-tech-specs/06-frontend-pages.md).

## Files to create here

- `tokens.css` — the CSS variables (the §1.2 palette below) + typography + spacing scale.
- Tailwind config mapping (in `frontend/tailwind.config.*`) that maps utility classes to these variables.

## Color tokens & theming (doc 06 §1.2)

**Every color and elevation is a semantic token with a light and a dark value.** Light values on `:root`; dark values on `:root[data-theme="dark"]`. A controller sets `data-theme` on `<html>` from the resolved theme (`light | dark | system`, default `system`, app-level in `app.json`). Flipping the attribute recolors the whole app — Tailwind classes, the graph SVG (`var(--…)`), the editor, and the AG Grid theme all resolve the same variables.

**Hard rule — no raw color, ever.** Components (Tailwind classes, inline SVG, AG Grid params, any CSS) reference **only tokens**, never a hex/rgb literal. A component that needs to differ between themes gets a **new token**, not a second stylesheet. There are no per-component light/dark rules.

Palette (light / dark): `--paper #FAFAF8 / #14171A` · `--surface #FFFFFF / #1D2125` · `--ink #1F2328 / #E6E8EB` · `--ink-soft #5C6470 / #A2A9B4` · `--ink-faint #9AA1AB / #6C7480` · `--line #E4E4DF / #2C3237` · `--accent #2F5A78 / #5E9BC2` · `--accent-wash #EBF1F5 / #1F2E38` · `--on-accent #FFFFFF / #0E1417` (text on accent+danger fills) · `--attn #B7791F / #E0A94A` · `--attn-wash #FBF3E4 / #2C2513` · `--ok #2F7D4F / #4FB07C` · `--ok-wash #EAF4EE / #16281E` · `--danger #A3382C / #D9695C` · `--danger-wash #F9ECEA / #2E1A17` · `--edge-soft #5C6470 / #8A929E` (graph soft/dotted edges — stronger than `--ink-faint`) · `--scrim rgb(31 35 40 / 0.4) / rgb(0 0 0 / 0.6)` (overlay backdrop) · `--shadow-overlay` (theme-aware; weaker in dark, elevation leans on `--line`).

## Typography

- **Prose** (editor + rendered markdown): **Literata** (bundled; fallback Georgia). 1.05rem/1.75; editor measure capped **68ch**; paragraphs spaced, not indented.
- **UI**: **Inter** (fallback system-ui). 0.875rem base; labels 0.75rem `--ink-soft` +0.02em; sentence case (no all-caps except 2-letter badges).
- **Data/mono**: ui-monospace stack, 0.8125rem (hashes, diffs, ids, word counts).
- Type scale: 12 / 13 / 14 / 16 / 20 / 24 / 30px. Page titles 20/semibold; modal titles 16/semibold.

## Space, shape, elevation

4px spacing scale; page gutters 24px; card padding 16px; control height 32px; dense grid rows 28px. Radii: 6px controls, 10px cards/modals, 999px pills. Borders over shadows; one soft shadow reserved for overlays: `0 8px 24px rgb(0 0 0 / 0.10)`.
