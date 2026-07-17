import { apiGet, apiSend } from "./client";

export type GitFileStatus = "modified" | "added" | "deleted" | "untracked" | "renamed";

export interface GitFile {
  path: string;
  status: GitFileStatus;
  staged: boolean;
}

export interface GitStatus {
  dirty: boolean;
  files: GitFile[];
  ahead: number;
  behind: number;
  hasRemote: boolean;
  /** Current branch; short sha if HEAD is detached. */
  branch: string;
  /** Human roll-up for the badge: "all-changes-synced" | "7-new, 1-updated". */
  summary: string;
}

export interface CommitInfo {
  hash: string;
  message: string;
  timestamp: string;
}

export interface GitDiff {
  path: string;
  diff: string;
  binary: boolean;
}

export interface SuggestedMessage {
  message: string;
  /** True when no utility model was configured and the text came from file stats. */
  fromStats: boolean;
}

export interface RemoteResult {
  ok: boolean;
  summary: string;
}

export const getGitStatus = (bookId: string) => apiGet<GitStatus>(`/books/${bookId}/git/status`);

export const stageFiles = (bookId: string, body: { paths?: string[]; all?: boolean }) =>
  apiSend<GitStatus>("POST", `/books/${bookId}/git/stage`, body);

export const unstageFiles = (bookId: string, body: { paths?: string[]; all?: boolean }) =>
  apiSend<GitStatus>("POST", `/books/${bookId}/git/unstage`, body);

export const discardFiles = (bookId: string, body: { paths?: string[]; all?: boolean }) =>
  apiSend<GitStatus>("POST", `/books/${bookId}/git/discard`, body);

export const getGitDiff = (bookId: string, path: string) =>
  apiGet<GitDiff>(`/books/${bookId}/git/diff?path=${encodeURIComponent(path)}`);

export const suggestCommitMessage = (bookId: string) =>
  apiSend<SuggestedMessage>("POST", `/books/${bookId}/git/suggest-message`);

export const commitStaged = (bookId: string, message: string) =>
  apiSend<CommitInfo>("POST", `/books/${bookId}/git/commit`, { message });

export const pushRemote = (bookId: string) => apiSend<RemoteResult>("POST", `/books/${bookId}/git/push`);

export const pullRemote = (bookId: string) => apiSend<RemoteResult>("POST", `/books/${bookId}/git/pull`);

export const getGitLog = (bookId: string, limit = 20) =>
  apiGet<CommitInfo[]>(`/books/${bookId}/git/log?limit=${limit}`);
