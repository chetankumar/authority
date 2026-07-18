import { apiGet, apiSend, apiUpload } from "./client";

export interface BookSummary {
  id: string;
  title: string;
  folderName: string;
  hasCover: boolean;
  error: boolean;
}

export interface Bookkeeping {
  summaryOnSave: boolean;
  charactersOnSave: boolean;
}

export interface Part {
  id: string;
  title: string;
  description: string;
  seq: number;
}

export interface Chapter {
  id: string;
  title: string;
  description: string;
  partId: string | null;
  seq: number;
}

export interface Book {
  id: string;
  title: string;
  hasCover: boolean;
  systemPrompt: string;
  storySummary: string;
  narratorVoiceId: string;
  narratorVoiceName: string;
  bookkeeping: Bookkeeping;
  parts: Part[];
  chapters: Chapter[];
}

export interface BookPatch {
  systemPrompt?: string;
  storySummary?: string;
  narratorVoiceId?: string;
  narratorVoiceName?: string;
  bookkeeping?: Bookkeeping;
}

export const listBooks = () => apiGet<BookSummary[]>("/books");
export const getBook = (id: string) => apiGet<Book>(`/books/${id}`);
export const patchBook = (id: string, body: BookPatch) => apiSend<Book>("PATCH", `/books/${id}`, body);

export function createBook(title: string, cover?: File | null): Promise<BookSummary> {
  const form = new FormData();
  form.append("title", title);
  if (cover) form.append("cover", cover);
  return apiUpload<BookSummary>("POST", "/books", form);
}

/** Cover image URL for a book (served by the backend; 404 → client placeholder). */
export const coverUrl = (id: string) => `/api/books/${id}/cover`;

// Per-book UI prefs (doc 04 §4): client-defined shape, stored verbatim.
export type BookUi = Record<string, unknown>;
export const getBookUi = (id: string) => apiGet<BookUi>(`/books/${id}/ui`);
export const patchBookUi = (id: string, patch: BookUi) => apiSend<BookUi>("PATCH", `/books/${id}/ui`, patch);
