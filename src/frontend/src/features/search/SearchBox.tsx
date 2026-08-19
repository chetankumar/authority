import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../../api/client";
import type { SearchAskResponse } from "../../api/search";
import { useAskSearch } from "../../queries/search";

export function SearchBox({ bookId }: { bookId: string }) {
  const navigate = useNavigate();
  const ask = useAskSearch(bookId);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [result, setResult] = useState<SearchAskResponse | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  async function submit() {
    const question = q.trim();
    if (!question || ask.isPending) return;
    setOpen(true);
    try {
      const data = await ask.mutateAsync(question);
      setResult(data);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Search failed.";
      setResult({ answer: message, hits: [], indexedSceneCount: 0 });
    }
  }

  return (
    <div ref={wrapRef} className="relative mx-4 min-w-0 max-w-xl flex-1">
      <input
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => {
          if (result) setOpen(true);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            void submit();
          }
          if (e.key === "Escape") setOpen(false);
        }}
        placeholder="Ask this book…"
        aria-label="Ask this book"
        className="h-8 w-full rounded-control border border-line bg-paper px-3 text-[0.875rem] text-ink outline-none placeholder:text-ink-faint focus:border-accent"
      />
      {open && (
        <div className="absolute left-0 right-0 top-full z-30 mt-1 max-h-[min(70vh,28rem)] overflow-auto rounded-[10px] border border-line bg-surface p-3 shadow-overlay">
          {ask.isPending && (
            <p className="text-[0.8125rem] text-ink-soft">Looking through the index…</p>
          )}
          {!ask.isPending && result && (
            <>
              <p className="whitespace-pre-wrap text-[0.875rem] leading-relaxed text-ink">{result.answer}</p>
              {result.hits.length > 0 && (
                <ul className="mt-3 border-t border-line pt-2">
                  {result.hits.map((hit) => (
                    <li key={`${hit.sceneId}:${hit.chunkIndex}:${hit.kind}`}>
                      <button
                        type="button"
                        className="block w-full rounded-control px-2 py-1.5 text-left hover:bg-accent-wash"
                        onClick={() => {
                          setOpen(false);
                          navigate(`/book/${bookId}/scene/${hit.sceneId}`);
                        }}
                      >
                        <span className="block text-[0.8125rem] text-ink">
                          {hit.seq != null ? `${hit.seq}. ` : ""}
                          {hit.title}
                          {hit.stale && (
                            <span className="ml-2 text-[0.6875rem] text-attn">stale</span>
                          )}
                        </span>
                        <span className="block text-[0.75rem] text-ink-soft">{hit.snippet}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
