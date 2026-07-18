import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as audioApi from "../api/audio";
import { ApiError } from "../api/client";
import { keys } from "./keys";

export function useAudioManifest(bookId: string, sceneId: string, enabled = true) {
  return useQuery({
    queryKey: keys.audio(bookId, sceneId),
    queryFn: async () => {
      try {
        return await audioApi.getAudioManifest(bookId, sceneId);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null;
        throw err;
      }
    },
    enabled: Boolean(bookId && sceneId && enabled),
  });
}

export function useGenerateAudio(bookId: string, sceneId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => audioApi.generateAudioAll(bookId, sceneId),
    onSuccess: (data) => qc.setQueryData(keys.audio(bookId, sceneId), data),
  });
}

export function useGenerateAudioLine(bookId: string, sceneId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (itemId: string) => audioApi.generateAudioLine(bookId, sceneId, itemId),
    onSuccess: (data) => qc.setQueryData(keys.audio(bookId, sceneId), data),
  });
}

export function usePatchAudioLine(bookId: string, sceneId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ itemId, body }: { itemId: string; body: audioApi.AudioLinePatch }) =>
      audioApi.patchAudioLine(bookId, sceneId, itemId, body),
    onSuccess: (data) => qc.setQueryData(keys.audio(bookId, sceneId), data),
  });
}

export function useDeleteAudio(bookId: string, sceneId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => audioApi.deleteAudio(bookId, sceneId),
    onSuccess: () => qc.setQueryData(keys.audio(bookId, sceneId), null),
  });
}

export function useElevenLabs() {
  return useQuery({
    queryKey: keys.settings("elevenlabs"),
    queryFn: audioApi.getElevenLabs,
  });
}

export function useElevenLabsVoices() {
  return useQuery({
    queryKey: keys.settings("elevenlabs-voices"),
    queryFn: audioApi.listElevenLabsVoices,
  });
}

export function useSyncElevenLabsVoices() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: audioApi.syncElevenLabsVoices,
    onSuccess: (voices) => {
      qc.setQueryData(keys.settings("elevenlabs-voices"), voices);
      void qc.invalidateQueries({ queryKey: keys.settings("elevenlabs") });
    },
  });
}

export function useGitignore(bookId: string) {
  return useQuery({
    queryKey: keys.gitignore(bookId),
    queryFn: () => audioApi.getGitignore(bookId),
    enabled: Boolean(bookId),
  });
}

export function usePutGitignore(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patterns: string[]) => audioApi.putGitignore(bookId, patterns),
    onSuccess: (data) => qc.setQueryData(keys.gitignore(bookId), data),
  });
}
