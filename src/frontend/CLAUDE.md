# Frontend — React + TypeScript + Vite SPA

The writing studio's UI. A Vite-built SPA served statically by the backend in production (same-origin, no CORS). Node is required only at install/build time, never at runtime. **The frontend never touches disk — the API is the single writer.**

Parent: [project root](../../CLAUDE.md). Spec: [06 Frontend](../../docs/claude-tech-specs/06-frontend-pages.md).

## Tech stack (locked)

React + TypeScript + Vite · TipTap (`@tiptap/react` + `tiptap-markdown`) for the editor · D3 for the scene graph · **AG Grid Community** (MIT, free — no license key) for tables · TanStack Query for server state · Tailwind CSS.

## Files to create here

- `package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, `tailwind.config.*`.
- `src/` — application source. See [src/CLAUDE.md](src/CLAUDE.md).
- `dist/` — build output, served by the backend (gitignored).

## Design philosophy (doc 06 §1)

1. **The prose is the hero.** The editor page is the center of gravity; every other page gets out of its way. Management surfaces are quiet, low-contrast; the writing surface is generous and typographically serious.
2. **Calm by default, loud only when the author must act.** Exactly one attention color (amber, `--attn`) meaning "something awaits your decision" — pending git changes, pending proposals, dependency todos.
3. **Copy is design material.** Buttons say exactly what happens, sentence case, active voice. Errors state what went wrong and how to fix it. Empty states are invitations to act.

## Design tokens (doc 06 §1.2)

CSS variables in [`src/styles/`](src/styles/CLAUDE.md); Tailwind maps to them — components never use raw hex. Palette: `--paper #FAFAF8`, `--surface #FFFFFF`, `--ink #1F2328`, `--ink-soft`, `--ink-faint`, `--line #E4E4DF`, `--accent #2F5A78` (+ `--accent-wash`), `--attn #B7791F` (+ `--attn-wash`), `--ok`, `--danger`. Prose = **Literata**; UI = **Inter**; data = mono.

## Architecture (doc 06 §2)

See [src/CLAUDE.md](src/CLAUDE.md) for the src map, query keys, SSE integration, autosave, and routing.
