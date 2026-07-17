import { apiGet, apiSend } from "./client";

export type TodoStatus = "open" | "done" | "closed";
export type TodoOrigin = "user" | "dependency" | "ai";
export type ParentType = "scene" | "chapter" | "part" | "book";

export interface Todo {
  id: string;
  parentType: ParentType;
  parentId: string;
  parentTitle: string;
  action: string;
  status: TodoStatus;
  origin: TodoOrigin;
  sourceDependencyId: string | null;
  conversationId: string | null;
  createdAt: string;
  updatedAt: string;
}

// Book-level create (POST /books/{b}/todos): parentType must not be "scene" —
// use createSceneTodo for those.
export interface TodoCreate {
  parentType: Exclude<ParentType, "scene">;
  parentId: string;
  action: string;
}

export interface TodoUpdate {
  status?: TodoStatus;
  action?: string;
  conversationId?: string;
}

export const listBookTodos = (bookId: string, includeScenes = false) =>
  apiGet<Todo[]>(`/books/${bookId}/todos${includeScenes ? "?includeScenes=true" : ""}`);

export const listSceneTodos = (bookId: string, sceneId: string) =>
  apiGet<Todo[]>(`/books/${bookId}/scenes/${sceneId}/todos`);

export const createTodo = (bookId: string, body: TodoCreate) =>
  apiSend<Todo>("POST", `/books/${bookId}/todos`, body);

export const createSceneTodo = (bookId: string, sceneId: string, action: string) =>
  apiSend<Todo>("POST", `/books/${bookId}/scenes/${sceneId}/todos`, { action });

export const updateTodo = (bookId: string, todoId: string, body: TodoUpdate) =>
  apiSend<Todo>("PATCH", `/books/${bookId}/todos/${todoId}`, body);

export const deleteTodo = (bookId: string, todoId: string) =>
  apiSend<void>("DELETE", `/books/${bookId}/todos/${todoId}`);
