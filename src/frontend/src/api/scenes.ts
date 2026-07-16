import { apiGet, apiSend } from "./client";

export type Placement = "trunk" | "unanchored" | "floating" | "orphan" | "archived";
export type SceneStatus = "active" | "archived";
export type RelationshipType = "before" | "after" | "around";

export const START_ID = "scn-START";
export const END_ID = "scn-END";

export interface Scene {
  id: string;
  title: string;
  file: string;
  description: string;
  location: string;
  dateTime: string;
  previousSceneId: string | null;
  nextSceneId: string | null;
  chapterId: string | null;
  partId: string | null;
  primaryPlotlineId: string | null;
  secondaryPlotlineIds: string[];
  mood: string;
  emotionalArc: string;
  summary: string;
  characterIds: string[];
  status: SceneStatus;
  contentHash: string;
  wordCount: number;
  seq: number | null;
  placement: Placement;
  createdAt: string;
  updatedAt: string;
}

export interface SoftRelationship {
  id: string;
  fromSceneId: string;
  toSceneId: string;
  type: RelationshipType;
  createdAt: string;
}

export interface ScenesResponse {
  scenes: Scene[];
  relationships: SoftRelationship[];
  sentinels: string[];
}

export interface SceneMutationResult {
  scene: Scene;
  affectedScenes: Scene[];
}

export interface SceneWithContent extends Scene {
  content: string;
}

export interface ContentSaveResult {
  wordCount: number;
  contentHash: string;
  todosCreated: unknown[];
}

export interface SoftRelationInput {
  type: RelationshipType;
  sceneId: string;
}

export interface SceneCreate {
  title: string;
  description: string;
  previousSceneId?: string | null;
  nextSceneId?: string | null;
  softRelations?: SoftRelationInput[];
  chapterId?: string | null;
  partId?: string | null;
  primaryPlotlineId?: string | null;
  secondaryPlotlineIds?: string[];
  location?: string;
  dateTime?: string;
  mood?: string;
  emotionalArc?: string;
}

// PATCH is partial: only send the keys you mean to change. Explicit null clears.
export interface SceneUpdate {
  title?: string;
  description?: string;
  location?: string;
  dateTime?: string;
  mood?: string;
  emotionalArc?: string;
  summary?: string;
  characterIds?: string[];
  chapterId?: string | null;
  partId?: string | null;
  primaryPlotlineId?: string | null;
  secondaryPlotlineIds?: string[];
  previousSceneId?: string | null;
  nextSceneId?: string | null;
  status?: SceneStatus;
}

export const getScenes = (bookId: string) => apiGet<ScenesResponse>(`/books/${bookId}/scenes`);

export const getScene = (bookId: string, sceneId: string) =>
  apiGet<SceneWithContent>(`/books/${bookId}/scenes/${sceneId}`);

export const createScene = (bookId: string, body: SceneCreate) =>
  apiSend<SceneMutationResult>("POST", `/books/${bookId}/scenes`, body);

export const updateScene = (bookId: string, sceneId: string, body: SceneUpdate) =>
  apiSend<SceneMutationResult>("PATCH", `/books/${bookId}/scenes/${sceneId}`, body);

export const deleteScene = (bookId: string, sceneId: string) =>
  apiSend<void>("DELETE", `/books/${bookId}/scenes/${sceneId}`);

export const saveContent = (bookId: string, sceneId: string, content: string) =>
  apiSend<ContentSaveResult>("PUT", `/books/${bookId}/scenes/${sceneId}/content`, { content });
