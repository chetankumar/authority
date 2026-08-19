import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as searchApi from "../api/search";
import { keys } from "./keys";

export function useSearchIndex(bookId: string, enabled = true) {
  return useQuery({
    queryKey: keys.searchIndex(bookId),
    queryFn: () => searchApi.getSearchIndex(bookId),
    enabled: Boolean(bookId && enabled),
  });
}

export function useAskSearch(bookId: string) {
  return useMutation({
    mutationFn: (question: string) => searchApi.askSearch(bookId, question),
  });
}

export function useIndexScene(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sceneId: string) => searchApi.indexScene(bookId, sceneId),
    onSuccess: (data) => qc.setQueryData(keys.searchIndex(bookId), data),
  });
}

export function useRebuildSearchIndex(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => searchApi.rebuildSearchIndex(bookId),
    onSuccess: (data) => qc.setQueryData(keys.searchIndex(bookId), data),
  });
}

export function useDeleteSearchIndex(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => searchApi.deleteSearchIndex(bookId),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.searchIndex(bookId) }),
  });
}
