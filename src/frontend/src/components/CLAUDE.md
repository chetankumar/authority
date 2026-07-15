# components — shared UI primitives

Reusable, page-agnostic components used across features. Feature-specific UI lives in [features](../features/CLAUDE.md).

Parent: [src](../CLAUDE.md). Spec: [doc 06 §1.5](../../../../docs/claude-tech-specs/06-frontend-pages.md).

## Components to build

- **Modal** — centered; 560px (forms) / 720px (Scene Modal) / 800px (Conversation); scrim `rgb(31 35 40 / 0.4)`; Esc closes unless streaming/unsaved (then confirm); title left, × right, actions bottom-right (primary rightmost); traps focus.
- **Popover** — anchored, 280px, close on outside-click/Esc (Bookkeeping, column chooser).
- **Toast** — bottom-right, 4s, one-line past-tense confirmation; errors persist until dismissed.
- **Badge** — count pills; amber (`--attn`) = pending decision, `--ink-faint` = neutral count.
- **BlockedDeletionDialog** — shared for parts/chapters/plotlines/characters; driven by any 409 `blockedBy`; danger-tinted "Can't delete {name} yet"; lists each referencing item as a link to its fix location; single "Close".
- **SearchableSelect** — used for scene/character pickers (sentinels pinned top/bottom where relevant).
- **Button** variants — Primary (accent, one per view max) / Secondary / Ghost / Danger (only inside confirm dialogs); icon-buttons get 600ms-delay tooltips.
- **ConfirmDialog** — only for destructive/irreversible acts (delete, remove cover); never for archiving or proposals.
- **EmptyState** — icon + one sentence + one action button.

## Conventions

Buttons in sentence case, active voice; an action keeps its name through the flow. Focus: 2px `--accent` ring on all interactive elements; full keyboard reachability. Motion: 150ms hover/fade, 200ms modal enter; `prefers-reduced-motion` disables non-essential transitions.
