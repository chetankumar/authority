import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

import * as todosApi from "../api/todos";
import { keys } from "./keys";

export const useBookTodos = (bookId: string, includeScenes: boolean) =>
  useQuery({
    queryKey: keys.todos(bookId, includeScenes),
    queryFn: () => todosApi.listBookTodos(bookId, includeScenes),
    enabled: !!bookId,
  });

export const useSceneTodos = (bookId: string, sceneId: string) =>
  useQuery({
    queryKey: keys.sceneTodos(bookId, sceneId),
    queryFn: () => todosApi.listSceneTodos(bookId, sceneId),
    enabled: !!bookId && !!sceneId,
  });

// Both the plain and includeScenes=true book-level lists, plus every scene's
// list, can be touched by one mutation (e.g. closing a scene todo also
// changes what the Tasks-page toggle shows) — invalidate both key prefixes
// rather than trying to track which variant is affected.
function invalidateAllTodos(qc: QueryClient, bookId: string) {
  void qc.invalidateQueries({ queryKey: ["todos", bookId] });
  void qc.invalidateQueries({ queryKey: ["sceneTodos", bookId] });
}

export function useCreateTodo(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: todosApi.TodoCreate) => todosApi.createTodo(bookId, body),
    onSuccess: () => invalidateAllTodos(qc, bookId),
  });
}

export function useCreateSceneTodo(bookId: string, sceneId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (action: string) => todosApi.createSceneTodo(bookId, sceneId, action),
    onSuccess: () => invalidateAllTodos(qc, bookId),
  });
}

export function useUpdateTodo(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ todoId, body }: { todoId: string; body: todosApi.TodoUpdate }) =>
      todosApi.updateTodo(bookId, todoId, body),
    onSuccess: () => invalidateAllTodos(qc, bookId),
  });
}

export function useDeleteTodo(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (todoId: string) => todosApi.deleteTodo(bookId, todoId),
    onSuccess: () => invalidateAllTodos(qc, bookId),
  });
}
