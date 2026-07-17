import { apiGet, apiSend } from "./client";

export type ConversationKind = "note" | "chat" | "ai-job" | "bookkeeping" | "task-discussion";
export type ConversationStatus =
  | "open"
  | "queued"
  | "running"
  | "waiting"
  | "done"
  | "failed"
  | "archived";
export type ParentType = "scene" | "chapter" | "part" | "book";
export type ProposalType =
  | "edit"
  | "metadata-update"
  | "todo-create"
  | "character-create"
  | "character-relationship-create"
  | "resource-create";
export type ProposalStatus = "pending" | "applied" | "rejected" | "not-found";

export interface AiParticipant {
  enabled: boolean;
  modelId: string | null;
}

export interface MessageContext {
  sceneId: string;
  excerpt: string;
}

export interface Proposal {
  id: string;
  type: ProposalType;
  status: ProposalStatus;
  resolvedAt: string | null;
  payload: Record<string, unknown>;
}

export interface Message {
  id: string;
  author: "user" | "assistant" | "system";
  modelId: string | null;
  content: string;
  context: MessageContext[];
  proposals: Proposal[];
  createdAt: string;
}

export interface ConversationSummary {
  id: string;
  kind: ConversationKind;
  title: string;
  parentType: ParentType;
  parentId: string;
  status: ConversationStatus;
  updatedAt: string;
  messageCount: number;
  pendingProposals: number;
}

export interface Conversation extends ConversationSummary {
  aiParticipant: AiParticipant;
  aiJobId: string | null;
  aiJobName?: string | null;
  createdAt: string;
  messages: Message[];
}

export function createConversation(
  bookId: string,
  body: {
    kind: ConversationKind;
    parentType: ParentType;
    parentId: string;
    aiParticipant?: AiParticipant;
  },
) {
  return apiSend<Conversation>("POST", `/books/${bookId}/conversations`, body);
}

export function getConversation(bookId: string, conversationId: string) {
  return apiGet<Conversation>(`/books/${bookId}/conversations/${conversationId}`);
}

export function patchConversation(
  bookId: string,
  conversationId: string,
  body: { title?: string; status?: "open" | "archived"; aiParticipant?: Partial<AiParticipant> },
) {
  return apiSend<Conversation>("PATCH", `/books/${bookId}/conversations/${conversationId}`, body);
}

export function deleteConversation(bookId: string, conversationId: string) {
  return apiSend<void>("DELETE", `/books/${bookId}/conversations/${conversationId}`);
}

export function listSceneConversations(bookId: string, sceneId: string) {
  return apiGet<ConversationSummary[]>(`/books/${bookId}/scenes/${sceneId}/conversations`);
}

/** Threads parented to the book itself — the Resources page's chats. */
export function listBookConversations(bookId: string) {
  return apiGet<ConversationSummary[]>(`/books/${bookId}/conversations`);
}

export interface StreamHandlers {
  onToken?: (text: string) => void;
  onMessage?: (message: Message, ai?: boolean) => void;
  onTitle?: (title: string) => void;
  onError?: (error: string) => void;
  onDone?: () => void;
}

/** POST /messages as SSE. Returns an abort function. */
export function sendMessageStream(
  bookId: string,
  conversationId: string,
  body: { content: string; context?: MessageContext[] },
  handlers: StreamHandlers,
): () => void {
  const controller = new AbortController();
  void (async () => {
    try {
      const res = await fetch(`/api/books/${bookId}/conversations/${conversationId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      if (!res.ok || !res.body) {
        handlers.onError?.(`Send failed (${res.status})`);
        return;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";
        for (const block of parts) {
          const lines = block.split("\n");
          let event = "message";
          let data = "";
          for (const line of lines) {
            if (line.startsWith("event:")) event = line.slice(6).trim();
            else if (line.startsWith("data:")) data += line.slice(5).trim();
          }
          if (!data) continue;
          try {
            const parsed = JSON.parse(data) as Record<string, unknown>;
            if (event === "token") handlers.onToken?.(String(parsed.text ?? ""));
            else if (event === "title") handlers.onTitle?.(String(parsed.title ?? ""));
            else if (event === "message") {
              const msg = parsed.message as Message;
              handlers.onMessage?.(msg, parsed.ai === false ? false : true);
            } else if (event === "error") handlers.onError?.(String(parsed.error ?? "Error"));
            else if (event === "done") handlers.onDone?.();
          } catch {
            /* ignore malformed */
          }
        }
      }
      handlers.onDone?.();
    } catch (err) {
      if ((err as Error).name !== "AbortError") handlers.onError?.("Connection lost.");
    }
  })();
  return () => controller.abort();
}

export function runAiJob(
  bookId: string,
  body: { aiJobId: string; sceneId: string; scope: "full" | "selection"; selectionText?: string },
) {
  // Prepares the run: resolves the prompt and opens the conversation with it
  // already inside. Nothing runs until the author sends. No separate job id —
  // the conversation is the run.
  return apiSend<{ conversationId: string }>("POST", `/books/${bookId}/ai-jobs/run`, body);
}
