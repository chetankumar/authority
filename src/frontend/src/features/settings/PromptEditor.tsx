import { useRef, useState } from "react";

import type { Placeholder } from "../../api/settings";

// Prompt textarea with @-autocomplete (doc 06 §5.3). Typing `@` opens a menu fed
// by the placeholder registry; it filters as you type; Enter/Tab inserts.
export function PromptEditor({
  value,
  onChange,
  placeholders,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholders: Placeholder[];
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);

  // The @token immediately left of the caret, if any.
  function tokenAtCaret(text: string, caret: number): { start: number; partial: string } | null {
    const upToCaret = text.slice(0, caret);
    const match = /@([a-z0-9_]*)$/.exec(upToCaret);
    if (!match) return null;
    return { start: caret - match[0].length, partial: match[1] };
  }

  const matches = open
    ? placeholders.filter((p) => p.name.slice(1).toLowerCase().startsWith(query.toLowerCase()))
    : [];

  function refresh(text: string, caret: number) {
    const token = tokenAtCaret(text, caret);
    if (token) {
      setOpen(true);
      setQuery(token.partial);
      setActive(0);
    } else {
      setOpen(false);
    }
  }

  function insert(name: string) {
    const el = ref.current;
    if (!el) return;
    const caret = el.selectionStart ?? value.length;
    const token = tokenAtCaret(value, caret);
    if (!token) return;
    const next = value.slice(0, token.start) + name + " " + value.slice(caret);
    onChange(next);
    setOpen(false);
    // Restore caret just after the inserted placeholder.
    const pos = token.start + name.length + 1;
    requestAnimationFrame(() => {
      el.focus();
      el.setSelectionRange(pos, pos);
    });
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (!open || matches.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => (a + 1) % matches.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => (a - 1 + matches.length) % matches.length);
    } else if (e.key === "Enter" || e.key === "Tab") {
      e.preventDefault();
      insert(matches[active].name);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div className="relative">
      <textarea
        ref={ref}
        value={value}
        rows={8}
        onChange={(e) => {
          onChange(e.target.value);
          refresh(e.target.value, e.target.selectionStart ?? 0);
        }}
        onKeyUp={(e) => {
          const el = e.currentTarget;
          if (!["ArrowDown", "ArrowUp", "Enter", "Tab"].includes(e.key))
            refresh(el.value, el.selectionStart ?? 0);
        }}
        onKeyDown={onKeyDown}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        placeholder="You are reviewing @current_scene. Preserve the author's voice…"
        className="w-full rounded-control border border-line bg-surface p-2 font-mono text-[0.8125rem] leading-relaxed text-ink outline-none focus:border-accent"
      />
      {open && matches.length > 0 && (
        <ul className="absolute left-0 right-0 z-10 mt-1 max-h-56 overflow-auto rounded-control border border-line bg-surface shadow-overlay">
          {matches.map((p, i) => (
            <li key={p.name}>
              <button
                type="button"
                onMouseDown={(e) => {
                  e.preventDefault();
                  insert(p.name);
                }}
                onMouseEnter={() => setActive(i)}
                className={[
                  "block w-full px-3 py-1.5 text-left",
                  i === active ? "bg-accent-wash" : "",
                ].join(" ")}
              >
                <span className="font-mono text-[0.8125rem] text-accent">{p.name}</span>
                <span className="ml-2 text-[0.75rem] text-ink-faint">{p.description}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
