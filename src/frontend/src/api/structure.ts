import { apiGet, apiSend } from "./client";
import type { Part, Chapter } from "./books";

export interface Plotline {
  id: string;
  title: string;
  description: string;
  sceneCount: number;
}

export interface PlotlineCreate {
  title: string;
  description?: string;
}

export interface PlotlineUpdate {
  title?: string;
  description?: string;
}

// ---- Parts ------------------------------------------------------------------

export const listParts = (bookId: string) =>
  apiGet<Part[]>(`/books/${bookId}/parts`);

export const createPart = (bookId: string, body: { title: string; description?: string }) =>
  apiSend<Part>("POST", `/books/${bookId}/parts`, body);

export const updatePart = (bookId: string, partId: string, body: { title?: string; description?: string }) =>
  apiSend<Part>("PATCH", `/books/${bookId}/parts/${partId}`, body);

export const reorderParts = (bookId: string, ids: string[]) =>
  apiSend<Part[]>("POST", `/books/${bookId}/parts/reorder`, { ids });

export const deletePart = (bookId: string, partId: string) =>
  apiSend<void>("DELETE", `/books/${bookId}/parts/${partId}`);

// ---- Chapters ---------------------------------------------------------------

export const listChapters = (bookId: string) =>
  apiGet<Chapter[]>(`/books/${bookId}/chapters`);

export const createChapter = (bookId: string, body: { title: string; description?: string; partId?: string | null }) =>
  apiSend<Chapter>("POST", `/books/${bookId}/chapters`, body);

export const updateChapter = (bookId: string, chpId: string, body: { title?: string; description?: string; partId?: string | null }) =>
  apiSend<Chapter>("PATCH", `/books/${bookId}/chapters/${chpId}`, body);

export const reorderChapters = (bookId: string, ids: string[]) =>
  apiSend<Chapter[]>("POST", `/books/${bookId}/chapters/reorder`, { ids });

export const deleteChapter = (bookId: string, chpId: string) =>
  apiSend<void>("DELETE", `/books/${bookId}/chapters/${chpId}`);

// ---- Plotlines --------------------------------------------------------------

export const listPlotlines = (bookId: string) =>
  apiGet<Plotline[]>(`/books/${bookId}/plotlines`);

export const createPlotline = (bookId: string, body: PlotlineCreate) =>
  apiSend<Plotline>("POST", `/books/${bookId}/plotlines`, body);

export const updatePlotline = (bookId: string, pltId: string, body: PlotlineUpdate) =>
  apiSend<Plotline>("PATCH", `/books/${bookId}/plotlines/${pltId}`, body);

export const deletePlotline = (bookId: string, pltId: string) =>
  apiSend<void>("DELETE", `/books/${bookId}/plotlines/${pltId}`);
