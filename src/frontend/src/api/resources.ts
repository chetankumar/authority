// Book resources (doc 04 §Resources): files the author keeps beside the
// manuscript. Keyed by filename — there is no id, because the backend scans
// resources/ rather than indexing it.
import { apiGet, apiSend, apiUpload } from "./client";

export interface ResourceFile {
  filename: string;
  mimeType: string;
  sizeBytes: number;
  updatedAt: string;
}

export const listResources = (bookId: string) => apiGet<ResourceFile[]>(`/books/${bookId}/resources`);

export function uploadResource(bookId: string, file: File): Promise<ResourceFile> {
  const form = new FormData();
  form.append("file", file);
  // The returned filename may differ from the one sent — the server suffixes
  // rather than overwrite on a collision.
  return apiUpload<ResourceFile>("POST", `/books/${bookId}/resources`, form);
}

export const deleteResource = (bookId: string, filename: string) =>
  apiSend<void>("DELETE", `/books/${bookId}/resources/${encodeURIComponent(filename)}`);

/** Download URL for a resource (served by the backend as an attachment). */
export const resourceContentUrl = (bookId: string, filename: string) =>
  `/api/books/${bookId}/resources/${encodeURIComponent(filename)}/content`;
