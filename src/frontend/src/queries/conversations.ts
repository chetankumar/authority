import { useQuery, useQueryClient } from "@tanstack/react-query";

import { listBookConversations, listSceneConversations, getConversation } from "../api/conversations";
import { keys } from "./keys";

// One query per scene. Both the Notes and AI Jobs panes are just different
// filters over this — there is no separate jobs list any more (the conversation
// is the run).
export function useSceneConversations(bookId: string, sceneId: string) {
  return useQuery({
    queryKey: keys.conversations(bookId, sceneId),
    queryFn: () => listSceneConversations(bookId, sceneId),
    enabled: !!bookId && !!sceneId,
  });
}

// Threads about the whole book rather than any one scene (Resources page).
export function useBookConversations(bookId: string) {
  return useQuery({
    queryKey: keys.bookConversations(bookId),
    queryFn: () => listBookConversations(bookId),
    enabled: !!bookId,
  });
}

export function useConversation(bookId: string, conversationId: string | null) {
  return useQuery({
    queryKey: keys.conversation(bookId, conversationId ?? ""),
    queryFn: () => getConversation(bookId, conversationId!),
    enabled: !!bookId && !!conversationId,
  });
}

export function useInvalidateConversation(bookId: string) {
  const qc = useQueryClient();
  return (sceneId?: string, conversationId?: string) => {
    if (sceneId) void qc.invalidateQueries({ queryKey: keys.conversations(bookId, sceneId) });
    if (conversationId) void qc.invalidateQueries({ queryKey: keys.conversation(bookId, conversationId) });
  };
}
