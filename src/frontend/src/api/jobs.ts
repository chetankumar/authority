import { apiGet } from "./client";

export type JobStatus = "queued" | "running" | "done" | "failed";
export type JobType = "user" | "system";

export interface Job {
  id: string;
  type: JobType;
  aiJobId: string | null;
  conversationId: string | null;
  sceneId: string | null;
  scope: string;
  modelId: string | null;
  status: JobStatus;
  error: string | null;
  result: Record<string, unknown>;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
}

export function listJobs(bookId: string, sceneId?: string) {
  const q = sceneId ? `?scene=${encodeURIComponent(sceneId)}` : "";
  return apiGet<Job[]>(`/books/${bookId}/jobs${q}`);
}
