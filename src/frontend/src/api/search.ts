import { apiGet, apiSend } from "./client";

export interface SearchHit {
  sceneId: string;
  title: string;
  seq: number | null;
  chunkIndex: number;
  kind: string;
  snippet: string;
  score: number;
  stale: boolean;
}

export interface SearchAskResponse {
  answer: string;
  hits: SearchHit[];
  indexedSceneCount: number;
}

export interface IndexedScene {
  id: string;
  contentHash: string;
  chunkCount: number;
  indexedAt: string;
}

export interface SearchIndexStatus {
  status: string;
  sceneId: string | null;
  done: number;
  total: number;
  error: string | null;
  indexedSceneCount: number;
  scenes: IndexedScene[];
}

export const askSearch = (bookId: string, question: string) =>
  apiSend<SearchAskResponse>("POST", `/books/${bookId}/search`, { question });

export const getSearchIndex = (bookId: string) =>
  apiGet<SearchIndexStatus>(`/books/${bookId}/search/index`);

export const rebuildSearchIndex = (bookId: string) =>
  apiSend<SearchIndexStatus>("POST", `/books/${bookId}/search/index/rebuild`);

export const deleteSearchIndex = (bookId: string) =>
  apiSend<void>("DELETE", `/books/${bookId}/search/index`);

export const indexScene = (bookId: string, sceneId: string) =>
  apiSend<SearchIndexStatus>("POST", `/books/${bookId}/scenes/${sceneId}/index`);
