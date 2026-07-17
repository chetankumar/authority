import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { deleteResource, listResources, uploadResource } from "../api/resources";
import { keys } from "./keys";

export function useResources(bookId: string) {
  return useQuery({
    queryKey: keys.resources(bookId),
    queryFn: () => listResources(bookId),
    enabled: !!bookId,
  });
}

export function useUploadResource(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => uploadResource(bookId, file),
    // Refetch rather than patch: the server may have renamed the file to dodge
    // a collision, so its list is the truth.
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.resources(bookId) }),
  });
}

export function useDeleteResource(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (filename: string) => deleteResource(bookId, filename),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.resources(bookId) }),
  });
}
