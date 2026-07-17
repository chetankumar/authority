import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { subscribeToBookEvents } from "../api/client";
import type { BookEvent } from "../api/client";
import type { GitStatus } from "../api/git";
import { keys } from "../queries/keys";

/**
 * One EventSource per open book (doc 06 §2), translating server events into
 * TanStack Query cache patches.
 *
 * This is the fast path, not the safety net: the channel is stateless and
 * nothing is replayed, so anything rendered from an event must also be
 * recoverable by refetching. `useGitStatus` polls every 10s for exactly that
 * reason (doc 07 §28) — both write identical server truth into the same key, so
 * they can't disagree. Unknown event types (e.g. the server-internal
 * `book-changed`) are ignored.
 */
export function useBookEvents(bookId: string | null): void {
  const qc = useQueryClient();

  useEffect(() => {
    if (!bookId) return;

    return subscribeToBookEvents(bookId, {
      onEvent: (event: BookEvent) => {
        switch (event.type) {
          case "git-status":
            qc.setQueryData(keys.git(bookId), event.data as GitStatus);
            break;
          case "scene-updated": {
            const data = event.data as { id?: string; changed?: string[] };
            void qc.invalidateQueries({ queryKey: keys.scenes(bookId) });
            if (data.id) void qc.invalidateQueries({ queryKey: keys.scene(bookId, data.id) });
            break;
          }
          case "todos-created": {
            void qc.invalidateQueries({ queryKey: ["todos", bookId] });
            void qc.invalidateQueries({ queryKey: ["sceneTodos", bookId] });
            break;
          }
          case "job": {
            const data = event.data as { sceneId?: string };
            if (data.sceneId) {
              void qc.invalidateQueries({ queryKey: keys.jobs(bookId, data.sceneId) });
              void qc.invalidateQueries({ queryKey: keys.conversations(bookId, data.sceneId) });
            } else {
              void qc.invalidateQueries({ queryKey: ["jobs", bookId] });
            }
            break;
          }
          default:
            break;
        }
      },
      onReconnect: () => {
        // Missed events during the gap are gone for good — re-read the truth.
        qc.invalidateQueries({ queryKey: keys.git(bookId) });
        qc.invalidateQueries({ queryKey: keys.scenes(bookId) });
        qc.invalidateQueries({ queryKey: ["jobs", bookId] });
        qc.invalidateQueries({ queryKey: ["conversations", bookId] });
        qc.invalidateQueries({ queryKey: ["todos", bookId] });
        qc.invalidateQueries({ queryKey: ["sceneTodos", bookId] });
      },
    });
  }, [bookId, qc]);
}
