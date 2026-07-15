import { useEffect, useRef, useState } from "react";

export interface Option {
  value: string;
  label: string;
  /** Optional right-aligned hint (e.g. a seq number or placement). */
  hint?: string;
}

interface Props {
  options: Option[];
  value: string | null;
  onChange: (value: string | null) => void;
  placeholder?: string;
  /** Show a "— none —" clear entry at the top. */
  clearable?: boolean;
  clearLabel?: string;
  disabled?: boolean;
}

// Filterable single-select (doc 06 §1.5 / §8). Used for scene sequence pickers
// (sentinels pinned by the caller via option order) and structure selects.
export function SearchableSelect({
  options,
  value,
  onChange,
  placeholder = "Select…",
  clearable = false,
  clearLabel = "— none —",
  disabled = false,
}: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const selected = options.find((o) => o.value === value);
  const filtered = query
    ? options.filter((o) => o.label.toLowerCase().includes(query.toLowerCase()))
    : options;

  const pick = (v: string | null) => {
    onChange(v);
    setOpen(false);
    setQuery("");
  };

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
        className="flex h-8 w-full items-center justify-between rounded-control border border-line bg-surface px-2 text-left text-[0.875rem] text-ink outline-none focus:border-accent disabled:opacity-40"
      >
        <span className={selected ? "truncate text-ink" : "truncate text-ink-faint"}>
          {selected ? selected.label : placeholder}
        </span>
        <span className="ml-1 shrink-0 text-ink-faint">▾</span>
      </button>

      {open && (
        <div className="absolute z-50 mt-1 max-h-64 w-full overflow-auto rounded-control border border-line bg-surface py-1 shadow-overlay">
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type to filter…"
            className="mb-1 h-7 w-[calc(100%-8px)] mx-1 rounded-control border border-line bg-paper px-2 text-[0.8125rem] outline-none focus:border-accent"
          />
          {clearable && (
            <button
              type="button"
              onClick={() => pick(null)}
              className="block w-full px-3 py-1.5 text-left text-[0.8125rem] text-ink-soft hover:bg-accent-wash"
            >
              {clearLabel}
            </button>
          )}
          {filtered.length === 0 ? (
            <div className="px-3 py-2 text-[0.8125rem] text-ink-faint">No matches</div>
          ) : (
            filtered.map((o) => (
              <button
                key={o.value}
                type="button"
                onClick={() => pick(o.value)}
                className={`flex w-full items-center justify-between px-3 py-1.5 text-left text-[0.8125rem] hover:bg-accent-wash ${
                  o.value === value ? "bg-accent-wash text-accent" : "text-ink"
                }`}
              >
                <span className="truncate">{o.label}</span>
                {o.hint && <span className="ml-2 shrink-0 text-ink-faint">{o.hint}</span>}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
