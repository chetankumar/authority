import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";

import {
  sendMessageStream,
  type Message,
  type MessageContext,
} from "../../api/conversations";

/**
 * One open conversation the author can see — either as the big modal or as a
 * small chip in the corner.
 */
export interface ConversationSession {
  id: string;
  sceneId?: string;
  title: string;
  /** Selection excerpt to attach to the first send, then cleared. */
  initialContext?: MessageContext | null;
}

export interface ToolLogEntry {
  name: string;
  argsPreview?: string;
  at: number;
}

/** Live reply for one conversation. Survives the modal being hidden. */
export interface ConversationStream {
  busy: boolean;
  streaming: string;
  streamPhase: string | null;
  toolLog: ToolLogEntry[];
  error: string | null;
  streamedMessages: Message[];
  /** Bumped when a reply finishes so the open modal can reload the saved thread. */
  doneSeq: number;
}

export interface OpenConversationOpts {
  sceneId?: string;
  title?: string;
  initialContext?: MessageContext | null;
}

interface ConversationSessionsApi {
  bookId: string | null;
  sessions: ConversationSession[];
  /** Which conversation is showing as the full modal. Null = all are chips. */
  focusedId: string | null;
  streams: Record<string, ConversationStream>;
  /** Show this conversation. If it is already open, just bring it to the front. */
  open: (id: string, extras?: OpenConversationOpts) => void;
  /** Drop this conversation from the dock. Stops its live reply if one is running. */
  close: (id: string) => void;
  /** Hide the modal; chips stay, replies keep running. */
  minimize: () => void;
  /** Expand this conversation's modal (hides whichever was showing). */
  focus: (id: string) => void;
  /** Send a user message and start (or continue) the live AI reply. */
  send: (id: string, content: string) => void;
  setTitle: (id: string, title: string) => void;
  /**
   * The scene editor registers its "flush unsaved prose" function here so an
   * edit proposal can save the open scene before applying.
   */
  registerAwaitSave: (sceneId: string, fn: () => Promise<void>) => () => void;
  awaitSaveFor: (sceneId?: string) => Promise<void>;
}

const ConversationSessionContext = createContext<ConversationSessionsApi | null>(null);

function emptyStream(): ConversationStream {
  return {
    busy: false,
    streaming: "",
    streamPhase: null,
    toolLog: [],
    error: null,
    streamedMessages: [],
    doneSeq: 0,
  };
}

/**
 * Holds every open AI conversation for the book you are in.
 *
 * The chat window used to own the network request that streams the AI's reply.
 * Closing the window, opening a second chat, or leaving the scene cancelled
 * that request. This provider lives in App instead, so replies keep running
 * while you write, start another chat, or move to a different scene.
 *
 * Book-wide events (git badge, list updates) stay on a different connection —
 * see useBookEvents. This file only owns the live reply for each chat.
 *
 * Closing one chat stops that chat only. Leaving the book (or refreshing the
 * tab) stops all of them.
 */
export function ConversationSessionProvider({
  bookId,
  children,
}: {
  bookId: string | null;
  children: ReactNode;
}) {
  const qc = useQueryClient();
  const [sessions, setSessions] = useState<ConversationSession[]>([]);
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const [streams, setStreams] = useState<Record<string, ConversationStream>>({});

  const sessionsRef = useRef(sessions);
  sessionsRef.current = sessions;
  const streamsRef = useRef(streams);
  streamsRef.current = streams;
  const abortById = useRef(new Map<string, () => void>());
  const awaitSaveByScene = useRef(new Map<string, () => Promise<void>>());
  const bookIdRef = useRef(bookId);
  bookIdRef.current = bookId;

  const patchStream = useCallback(
    (id: string, patch: Partial<ConversationStream> | ((s: ConversationStream) => ConversationStream)) => {
      setStreams((prev) => {
        const cur = prev[id] ?? emptyStream();
        const next = typeof patch === "function" ? patch(cur) : { ...cur, ...patch };
        return { ...prev, [id]: next };
      });
    },
    [],
  );

  const abortAll = useCallback(() => {
    for (const abort of abortById.current.values()) abort();
    abortById.current.clear();
  }, []);

  useEffect(() => {
    return () => abortAll();
  }, [abortAll]);

  const open = useCallback((id: string, extras?: OpenConversationOpts) => {
    setSessions((prev) => {
      if (prev.some((s) => s.id === id)) return prev;
      return [
        ...prev,
        {
          id,
          sceneId: extras?.sceneId,
          title: extras?.title?.trim() || "Conversation",
          initialContext: extras?.initialContext ?? null,
        },
      ];
    });
    setStreams((prev) => (prev[id] ? prev : { ...prev, [id]: emptyStream() }));
    setFocusedId(id);
  }, []);

  const close = useCallback((id: string) => {
    abortById.current.get(id)?.();
    abortById.current.delete(id);
    setSessions((prev) => prev.filter((s) => s.id !== id));
    setStreams((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
    setFocusedId((cur) => (cur === id ? null : cur));
  }, []);

  const minimize = useCallback(() => {
    setFocusedId(null);
  }, []);

  const focus = useCallback((id: string) => {
    setFocusedId(id);
  }, []);

  const setTitle = useCallback((id: string, title: string) => {
    const trimmed = title.trim();
    if (!trimmed) return;
    setSessions((prev) => prev.map((s) => (s.id === id ? { ...s, title: trimmed } : s)));
  }, []);

  const send = useCallback(
    (id: string, content: string) => {
      const text = content.trim();
      const currentBook = bookIdRef.current;
      if (!text || !currentBook) return;
      if (streamsRef.current[id]?.busy) return;

      const session = sessionsRef.current.find((s) => s.id === id);
      const context = session?.initialContext ? [session.initialContext] : undefined;
      if (session?.initialContext) {
        setSessions((prev) =>
          prev.map((s) => (s.id === id ? { ...s, initialContext: null } : s)),
        );
      }

      patchStream(id, {
        busy: true,
        error: null,
        streaming: "",
        streamPhase: "Working…",
        toolLog: [],
        streamedMessages: [],
      });

      let finished = false;
      // The stream helper can fire both `error`/`done` and a trailing `done`
      // when the connection closes. Run cleanup once.
      const finish = (fn: () => void) => {
        if (finished) return;
        finished = true;
        fn();
      };

      const abort = sendMessageStream(
        currentBook,
        id,
        { content: text, context },
        {
          onToken: (t) => {
            patchStream(id, (s) => ({ ...s, streamPhase: null, streaming: s.streaming + t }));
          },
          onStatus: (status) => {
            if (status.phase === "waiting") {
              const sec = status.elapsedSec ?? 0;
              patchStream(id, { streamPhase: sec > 0 ? `Waiting… ${sec}s` : "Waiting…" });
            } else if (status.phase === "thinking") {
              patchStream(id, { streamPhase: "Thinking…" });
            } else if (status.phase === "tool" && status.name) {
              patchStream(id, (s) => ({
                ...s,
                toolLog: [
                  ...s.toolLog,
                  { name: status.name!, argsPreview: status.argsPreview, at: Date.now() },
                ],
              }));
            } else if (status.phase) {
              patchStream(id, { streamPhase: "Working…" });
            }
          },
          onTitle: (title) => setTitle(id, title),
          onMessage: (msg) => {
            if (msg.author !== "user") {
              patchStream(id, (s) => ({ ...s, streaming: "" }));
            }
            patchStream(id, (s) => ({
              ...s,
              streamedMessages: s.streamedMessages.some((m) => m.id === msg.id)
                ? s.streamedMessages
                : [...s.streamedMessages, msg],
            }));
          },
          onError: (e) => {
            finish(() => {
              abortById.current.delete(id);
              patchStream(id, {
                error: e,
                busy: false,
                streamPhase: null,
                toolLog: [],
              });
            });
          },
          onDone: () => {
            finish(() => {
              abortById.current.delete(id);
              patchStream(id, (s) => ({
                ...s,
                busy: false,
                streaming: "",
                streamPhase: null,
                toolLog: [],
                doneSeq: s.doneSeq + 1,
              }));
              void qc.invalidateQueries({ queryKey: ["conversations", currentBook] });
            });
          },
        },
      );
      abortById.current.set(id, abort);
    },
    [patchStream, qc, setTitle],
  );

  const registerAwaitSave = useCallback((sceneId: string, fn: () => Promise<void>) => {
    awaitSaveByScene.current.set(sceneId, fn);
    return () => {
      if (awaitSaveByScene.current.get(sceneId) === fn) {
        awaitSaveByScene.current.delete(sceneId);
      }
    };
  }, []);

  const awaitSaveFor = useCallback(async (sceneId?: string) => {
    if (!sceneId) return;
    await awaitSaveByScene.current.get(sceneId)?.();
  }, []);

  const value = useMemo<ConversationSessionsApi>(
    () => ({
      bookId,
      sessions,
      focusedId,
      streams,
      open,
      close,
      minimize,
      focus,
      send,
      setTitle,
      registerAwaitSave,
      awaitSaveFor,
    }),
    [
      bookId,
      sessions,
      focusedId,
      streams,
      open,
      close,
      minimize,
      focus,
      send,
      setTitle,
      registerAwaitSave,
      awaitSaveFor,
    ],
  );

  return (
    <ConversationSessionContext.Provider value={value}>{children}</ConversationSessionContext.Provider>
  );
}

export function useConversationSessions(): ConversationSessionsApi {
  const ctx = useContext(ConversationSessionContext);
  if (!ctx) {
    throw new Error("useConversationSessions must be used within ConversationSessionProvider");
  }
  return ctx;
}

export function streamDockStatus(stream: ConversationStream | undefined): string {
  if (!stream?.busy) return "Done — click to open";
  if (stream.streamPhase) return stream.streamPhase;
  const lastTool = stream.toolLog[stream.toolLog.length - 1];
  if (lastTool) return lastTool.name;
  if (stream.streaming) return "Streaming…";
  return "Working…";
}
