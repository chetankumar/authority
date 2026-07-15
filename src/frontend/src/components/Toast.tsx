import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

type ToastKind = "ok" | "error";

interface Toast {
  id: number;
  message: string;
  kind: ToastKind;
}

interface ToastApi {
  // Past-tense confirmations (doc 06 §1.5). Errors persist until dismissed.
  success: (message: string) => void;
  error: (message: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  const remove = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (message: string, kind: ToastKind) => {
      const id = nextId.current++;
      setToasts((prev) => [...prev, { id, message, kind }]);
      if (kind === "ok") setTimeout(() => remove(id), 4000);
    },
    [remove],
  );

  const api = useMemo<ToastApi>(
    () => ({ success: (m) => push(m, "ok"), error: (m) => push(m, "error") }),
    [push],
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((t) => (
          <button
            key={t.id}
            onClick={() => remove(t.id)}
            style={{
              animation: "toast-in 200ms ease-out",
              borderLeftColor: t.kind === "ok" ? "var(--ok)" : "var(--danger)",
            }}
            className={[
              "pointer-events-auto flex max-w-sm items-start gap-2 rounded-control border border-l-4 bg-surface px-3 py-2.5 text-left text-[0.8125rem] shadow-overlay",
              t.kind === "ok" ? "border-line text-ink" : "border-danger bg-danger-wash text-danger",
            ].join(" ")}
          >
            <span
              className={[
                "mt-px inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[0.6875rem] font-semibold text-white",
                t.kind === "ok" ? "bg-ok" : "bg-danger",
              ].join(" ")}
            >
              {t.kind === "ok" ? "✓" : "!"}
            </span>
            <span>{t.message}</span>
          </button>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
