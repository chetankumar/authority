import { useEffect, type ReactNode } from "react";

interface ModalProps {
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  width?: number;
  /** When set, shows a Minimize control left of ×. */
  onMinimize?: () => void;
  /** Scrim click. Defaults to onClose. */
  onBackdropClose?: () => void;
  /** When false, Escape does not call onClose (default true). */
  closeOnEsc?: boolean;
}

// Centered modal (doc 06 §1.5): scrim, title left + × right, actions bottom-right.
export function Modal({
  title,
  onClose,
  children,
  footer,
  width = 560,
  onMinimize,
  onBackdropClose,
  closeOnEsc = true,
}: ModalProps) {
  const backdrop = onBackdropClose ?? onClose;

  useEffect(() => {
    if (!closeOnEsc) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose, closeOnEsc]);

  return (
    <div
      className="fixed inset-0 z-40 flex items-start justify-center overflow-auto bg-scrim p-6"
      onMouseDown={backdrop}
    >
      <div
        className="mt-16 w-full rounded-card border border-line bg-surface shadow-overlay"
        style={{ maxWidth: width }}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <h2 className="text-[16px] font-semibold text-ink">{title}</h2>
          <div className="flex items-center gap-1">
            {onMinimize && (
              <button
                type="button"
                onClick={onMinimize}
                aria-label="Minimize"
                title="Minimize"
                className="rounded-control px-2 text-ink-soft hover:bg-accent-wash"
              >
                –
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="rounded-control px-2 text-ink-soft hover:bg-accent-wash"
            >
              ×
            </button>
          </div>
        </div>
        <div className="px-4 py-4">{children}</div>
        {footer && (
          <div className="flex justify-end gap-2 border-t border-line px-4 py-3">{footer}</div>
        )}
      </div>
    </div>
  );
}
