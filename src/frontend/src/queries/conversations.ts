import { useQuery, useQueryClient } from "@tanstack/react-query";

import { listSceneConversations, getConversation } from "../api/conversations";
import { listJobs } from "../api/jobs";
import { keys } from "./keys";

export function useSceneConversations(bookId: string, sceneId: string) {
  return useQuery({
    queryKey: keys.conversations(bookId, sceneId),
    queryFn: () => listSceneConversations(bookId, sceneId),
    enabled: !!bookId && !!sceneId,
  });
}

export function useConversation(bookId: string, conversationId: string | null) {
  return useQuery({
    queryKey: keys.conversation(bookId, conversationId ?? ""),
    queryFn: () => getConversation(bookId, conversationId!),
    enabled: !!bookId && !!conversationId,
  });
}

export function useSceneJobs(bookId: string, sceneId: string) {
  return useQuery({
    queryKey: keys.jobs(bookId, sceneId),
    queryFn: () => listJobs(bookId, sceneId),
    enabled: !!bookId && !!sceneId,
  });
}

export function useInvalidateConversation(bookId: string) {
  const qc = useQueryClient();
  return (sceneId?: string, conversationId?: string) => {
    if (sceneId) void qc.invalidateQueries({ queryKey: keys.conversations(bookId, sceneId) });
    if (conversationId) void qc.invalidateQueries({ queryKey: keys.conversation(bookId, conversationId) });
    void qc.invalidateQueries({ queryKey: keys.jobs(bookId, sceneId ?? "") });
  };
}
