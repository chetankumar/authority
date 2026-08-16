import { ConversationModal } from "./ConversationModal";
import {
  streamDockStatus,
  useConversationSessions,
} from "./ConversationSessionContext";

const CHIP_STACK_PX = 72;

/** Dock chips + the one focused conversation modal. Lives in the book shell so
 *  streams survive scene and page changes. */
export function ConversationHost() {
  const { bookId, sessions, focusedId, streams, focus, close, minimize } = useConversationSessions();
  if (!bookId || sessions.length === 0) return null;

  const focused = sessions.find((s) => s.id === focusedId);
  const chips = sessions.filter((s) => s.id !== focusedId);

  return (
    <>
      {focused && (
        <ConversationModal
          key={focused.id}
          bookId={bookId}
          conversationId={focused.id}
          sceneId={focused.sceneId}
          onClose={() => close(focused.id)}
          onMinimize={minimize}
        />
      )}
      {chips.map((s, i) => {
        const stream = streams[s.id];
        const busy = !!stream?.busy;
        return (
          <button
            key={s.id}
            type="button"
            onClick={() => focus(s.id)}
            style={{ bottom: 24 + i * CHIP_STACK_PX }}
            className={[
              "fixed right-6 z-50 flex max-w-sm flex-col gap-0.5 rounded-card border px-4 py-3 text-left shadow-overlay",
              "border-line bg-surface hover:bg-accent-wash",
              busy ? "ring-2 ring-attn" : "",
            ].join(" ")}
            title="Restore conversation"
          >
            <span className="truncate text-[0.875rem] font-semibold text-ink">{s.title}</span>
            <span className={`truncate text-[0.8125rem] ${busy ? "text-attn" : "text-ink-soft"}`}>
              {streamDockStatus(stream)}
              {busy && (
                <span className="ml-1 inline-block h-2.5 w-1 animate-pulse bg-attn align-middle" />
              )}
            </span>
          </button>
        );
      })}
    </>
  );
}
