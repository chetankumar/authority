import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as gitApi from "../api/git";
import type { GitStatus } from "../api/git";
import { keys } from "./keys";

// Belt and braces (doc 07 §28). SSE already pushes `git-status` — instantly
// after an explicit stage/commit, and ~5s after the author stops typing. This
// poll is the net underneath: it re-reads server truth into the same cache key,
// so a dropped signal, a flaky reconnect, or a bug in the debounce can't leave
// the amber badge quietly lying. A stale nudge is worse than no nudge.
//
// Left to pause while the tab is hidden (TanStack's default): nobody is reading
// the badge then, and refetch-on-focus makes it current before they can.
const STATUS_POLL_MS = 10000;

export const useGitStatus = (bookId: string) =>
  useQuery({
    queryKey: keys.git(bookId),
    queryFn: () => gitApi.getGitStatus(bookId),
    enabled: !!bookId,
    refetchInterval: STATUS_POLL_MS,
    // A book folder with no .git 404s; retrying won't grow one.
    retry: false,
  });

export const useGitLog = (bookId: string, limit = 20) =>
  useQuery({
    queryKey: [...keys.git(bookId), "log", limit],
    queryFn: () => gitApi.getGitLog(bookId, limit),
    enabled: !!bookId,
    retry: false,
  });

export const useGitDiff = (bookId: string, path: string | null) =>
  useQuery({
    queryKey: [...keys.git(bookId), "diff", path],
    queryFn: () => gitApi.getGitDiff(bookId, path!),
    enabled: !!bookId && !!path,
    retry: false,
  });

/** Mutating git endpoints return the refreshed status — patch, don't refetch. */
function useGitMutation<TArgs>(bookId: string, fn: (args: TArgs) => Promise<GitStatus>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (status) => qc.setQueryData(keys.git(bookId), status),
  });
}

export const useStageFiles = (bookId: string) =>
  useGitMutation(bookId, (body: { paths?: string[]; all?: boolean }) => gitApi.stageFiles(bookId, body));

export const useUnstageFiles = (bookId: string) =>
  useGitMutation(bookId, (body: { paths?: string[]; all?: boolean }) => gitApi.unstageFiles(bookId, body));

export function useCommitStaged(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (message: string) => gitApi.commitStaged(bookId, message),
    onSuccess: () => {
      // The commit response carries the hash, not the status; the server also
      // emitted `git-status`, but don't rely on the event for the author's own
      // action — ask.
      qc.invalidateQueries({ queryKey: keys.git(bookId) });
    },
  });
}

export const useSuggestCommitMessage = (bookId: string) =>
  useMutation({ mutationFn: () => gitApi.suggestCommitMessage(bookId) });

export function useRemoteOp(bookId: string, op: "push" | "pull") {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => (op === "push" ? gitApi.pushRemote(bookId) : gitApi.pullRemote(bookId)),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.git(bookId) }),
  });
}
