import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

import * as scenesApi from "../api/scenes";
import * as relApi from "../api/relationships";
import type { Scene, ScenesResponse, SceneMutationResult } from "../api/scenes";
import { keys } from "./keys";

export const useScenes = (bookId: string) =>
  useQuery({ queryKey: keys.scenes(bookId), queryFn: () => scenesApi.getScenes(bookId), enabled: !!bookId });

export const useScene = (bookId: string, sceneId: string) =>
  useQuery({
    queryKey: keys.scene(bookId, sceneId),
    queryFn: () => scenesApi.getScene(bookId, sceneId),
    enabled: !!bookId && !!sceneId,
  });

// Merge a mutation's { scene, affectedScenes } into the cached scenes list —
// no refetch needed (doc 06 §2: mutations patch ['scenes'] directly).
function patchScenes(qc: QueryClient, bookId: string, result: SceneMutationResult) {
  qc.setQueryData<ScenesResponse>(keys.scenes(bookId), (prev) => {
    if (!prev) return prev;
    const patched = new Map<string, Scene>(prev.scenes.map((s) => [s.id, s]));
    patched.set(result.scene.id, result.scene);
    for (const a of result.affectedScenes) patched.set(a.id, a);
    return { ...prev, scenes: [...patched.values()] };
  });
}

export function useCreateScene(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: scenesApi.SceneCreate) => scenesApi.createScene(bookId, body),
    onSuccess: (result) => {
      patchScenes(qc, bookId, result);
      qc.invalidateQueries({ queryKey: keys.scenes(bookId) });
    },
  });
}

export function useUpdateScene(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ sceneId, body }: { sceneId: string; body: scenesApi.SceneUpdate }) =>
      scenesApi.updateScene(bookId, sceneId, body),
    onSuccess: (result) => {
      patchScenes(qc, bookId, result);
      qc.invalidateQueries({ queryKey: keys.scenes(bookId) });
    },
  });
}

export function useDeleteScene(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sceneId: string) => scenesApi.deleteScene(bookId, sceneId),
    onSuccess: (_result, sceneId) => {
      qc.setQueryData<ScenesResponse>(keys.scenes(bookId), (prev) => {
        if (!prev) return prev;
        return { ...prev, scenes: prev.scenes.filter((s) => s.id !== sceneId) };
      });
      qc.invalidateQueries({ queryKey: keys.scenes(bookId) });
    },
  });
}

export function useCreateRelationship(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { fromSceneId: string; toSceneId: string; type: scenesApi.RelationshipType }) =>
      relApi.createRelationship(bookId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.scenes(bookId) }),
  });
}

export function useDeleteRelationship(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (relId: string) => relApi.deleteRelationship(bookId, relId),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.scenes(bookId) }),
  });
}
