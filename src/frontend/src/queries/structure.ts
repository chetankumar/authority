import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as structApi from "../api/structure";
import * as booksApi from "../api/books";
import { keys } from "./keys";

// ---- Parts ------------------------------------------------------------------

export const useParts = (bookId: string) =>
  useQuery({ queryKey: keys.parts(bookId), queryFn: () => structApi.listParts(bookId), enabled: !!bookId });

export function useCreatePart(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { title: string; description?: string }) => structApi.createPart(bookId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.parts(bookId) });
      qc.invalidateQueries({ queryKey: keys.book(bookId) });
    },
  });
}

export function useUpdatePart(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ partId, body }: { partId: string; body: { title?: string; description?: string } }) =>
      structApi.updatePart(bookId, partId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.parts(bookId) });
      qc.invalidateQueries({ queryKey: keys.book(bookId) });
    },
  });
}

export function useReorderParts(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ids: string[]) => structApi.reorderParts(bookId, ids),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.parts(bookId) });
      qc.invalidateQueries({ queryKey: keys.book(bookId) });
    },
  });
}

export function useDeletePart(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (partId: string) => structApi.deletePart(bookId, partId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.parts(bookId) });
      qc.invalidateQueries({ queryKey: keys.book(bookId) });
    },
  });
}

// ---- Chapters ---------------------------------------------------------------

export const useChapters = (bookId: string) =>
  useQuery({ queryKey: keys.chapters(bookId), queryFn: () => structApi.listChapters(bookId), enabled: !!bookId });

export function useCreateChapter(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { title: string; description?: string; partId?: string | null }) =>
      structApi.createChapter(bookId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.chapters(bookId) });
      qc.invalidateQueries({ queryKey: keys.book(bookId) });
    },
  });
}

export function useUpdateChapter(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ chpId, body }: { chpId: string; body: { title?: string; description?: string; partId?: string | null } }) =>
      structApi.updateChapter(bookId, chpId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.chapters(bookId) });
      qc.invalidateQueries({ queryKey: keys.book(bookId) });
    },
  });
}

export function useReorderChapters(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ids: string[]) => structApi.reorderChapters(bookId, ids),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.chapters(bookId) });
      qc.invalidateQueries({ queryKey: keys.book(bookId) });
    },
  });
}

export function useDeleteChapter(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (chpId: string) => structApi.deleteChapter(bookId, chpId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.chapters(bookId) });
      qc.invalidateQueries({ queryKey: keys.book(bookId) });
    },
  });
}

// ---- Plotlines --------------------------------------------------------------

export const usePlotlines = (bookId: string) =>
  useQuery({ queryKey: keys.plotlines(bookId), queryFn: () => structApi.listPlotlines(bookId), enabled: !!bookId });

export function useCreatePlotline(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: structApi.PlotlineCreate) => structApi.createPlotline(bookId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.plotlines(bookId) }),
  });
}

export function useUpdatePlotline(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ pltId, body }: { pltId: string; body: structApi.PlotlineUpdate }) =>
      structApi.updatePlotline(bookId, pltId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.plotlines(bookId) }),
  });
}

export function useDeletePlotline(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (pltId: string) => structApi.deletePlotline(bookId, pltId),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.plotlines(bookId) }),
  });
}

// ---- Book patch (Book tab) --------------------------------------------------

export function usePatchBook(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: booksApi.BookPatch) => booksApi.patchBook(bookId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.book(bookId) }),
  });
}
