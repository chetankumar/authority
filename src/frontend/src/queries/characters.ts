import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as charApi from "../api/characters";
import { keys } from "./keys";

// ---- Characters ---------------------------------------------------------------

export const useCharacters = (bookId: string) =>
  useQuery({
    queryKey: keys.characters(bookId),
    queryFn: () => charApi.listCharacters(bookId),
    enabled: !!bookId,
  });

export function useCreateCharacter(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: charApi.CharacterInput) => charApi.createCharacter(bookId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.characters(bookId) }),
  });
}

export function useUpdateCharacter(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ chrId, body }: { chrId: string; body: charApi.CharacterInput }) =>
      charApi.updateCharacter(bookId, chrId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.characters(bookId) }),
  });
}

export function useDeleteCharacter(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (chrId: string) => charApi.deleteCharacter(bookId, chrId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.characters(bookId) });
      qc.invalidateQueries({ queryKey: keys.characterRelationships(bookId) });
    },
  });
}

// ---- Character relationships ---------------------------------------------------

export const useCharacterRelationships = (bookId: string) =>
  useQuery({
    queryKey: keys.characterRelationships(bookId),
    queryFn: () => charApi.listCharacterRelationships(bookId),
    enabled: !!bookId,
  });

export function useCreateCharacterRelationship(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: charApi.CharacterRelationshipInput) =>
      charApi.createCharacterRelationship(bookId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.characterRelationships(bookId) }),
  });
}

export function useUpdateCharacterRelationship(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ relId, body }: { relId: string; body: charApi.CharacterRelationshipUpdate }) =>
      charApi.updateCharacterRelationship(bookId, relId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.characterRelationships(bookId) }),
  });
}

export function useDeleteCharacterRelationship(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (relId: string) => charApi.deleteCharacterRelationship(bookId, relId),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.characterRelationships(bookId) }),
  });
}
