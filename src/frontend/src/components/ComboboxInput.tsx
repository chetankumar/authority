import { useEffect, useId, useRef, useState } from "react";

import { Input } from "./ui";

export interface ComboboxOption {
  value: string;
  label: string;
}

/** Free-text input with optional filtered suggestions. Arbitrary values always allowed. */
export function ComboboxInput({
  value,
  onChange,
  options,
  placeholder,
  disabled,
}: {
  value: string;
  onChange: (value: string) => void;
  options: ComboboxOption[];
  placeholder?: string;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const listId = useId();

  const q = value.trim().toLowerCase();
  const filtered = q
    ? options.filter((o) => {
        const hay = `${o.label} ${o.value}`.toLowerCase();
        return hay.includes(q);
      })
    : options;
  const shown = filtered.slice(0, 80);

  useEffect(() => {
    setHighlight(0);
  }, [value, options]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  function pick(next: string) {
    onChange(next);
    setOpen(false);
  }

  return (
    <div ref={rootRef} className="relative">
      <Input
        value={value}
        disabled={disabled}
        placeholder={placeholder}
        autoComplete="off"
        role="combobox"
        aria-expanded={open && shown.length > 0}
        aria-controls={listId}
        aria-autocomplete="list"
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (!open && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
            setOpen(true);
            return;
          }
          if (!open || shown.length === 0) return;
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setHighlight((h) => Math.min(h + 1, shown.length - 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setHighlight((h) => Math.max(h - 1, 0));
          } else if (e.key === "Enter" && shown[highlight]) {
            e.preventDefault();
            pick(shown[highlight].value);
          } else if (e.key === "Escape") {
            setOpen(false);
          }
        }}
      />
      {open && shown.length > 0 && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-20 mt-1 max-h-56 w-full overflow-auto rounded-control border border-line bg-surface py-1 shadow-overlay"
        >
          {shown.map((o, i) => (
            <li key={o.value} role="option" aria-selected={i === highlight}>
              <button
                type="button"
                className={[
                  "flex w-full flex-col items-start px-2 py-1.5 text-left text-[0.8125rem]",
                  i === highlight ? "bg-accent-wash text-ink" : "text-ink hover:bg-accent-wash",
                ].join(" ")}
                onMouseEnter={() => setHighlight(i)}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => pick(o.value)}
              >
                <span className="font-mono text-ink">{o.value}</span>
                {o.label !== o.value && (
                  <span className="text-[0.75rem] text-ink-soft">{o.label}</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
