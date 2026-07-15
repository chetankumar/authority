import { apiGet, apiSend } from "./client";

export type Provider = "anthropic" | "openai" | "gemini" | "openai-compatible" | "ollama";
export type OutputType = "chat" | "edit-proposals" | "metadata-proposals";

export interface UserSettings {
  name: string | null;
  booksHome: string | null;
}

export interface UserPatch {
  name?: string | null;
  booksHome?: string | null;
  createBooksHome?: boolean;
}

export interface ModelConfig {
  id: string;
  label: string;
  provider: Provider;
  modelName: string;
  apiKeyMasked: string | null;
  baseUrl: string | null;
}

export interface ModelInput {
  label: string;
  provider: Provider;
  modelName: string;
  apiKey?: string;
  baseUrl?: string | null;
}

export interface ModelTestResult {
  ok: boolean;
  message: string | null;
  error: string | null;
  latencyMs: number | null;
}

export type ThemePref = "light" | "dark" | "system";

export interface Appearance {
  theme: ThemePref;
}

export interface AISettings {
  utilityModelId: string | null;
}

export interface AIJobDefinition {
  id: string;
  name: string;
  prompt: string;
  defaultModelId: string;
  outputType: OutputType;
}

export interface AIJobInput {
  name: string;
  prompt: string;
  defaultModelId: string;
  outputType: OutputType;
  force?: boolean;
}

export interface Placeholder {
  name: string;
  description: string;
}

// -- user -------------------------------------------------------------------
export const getUser = () => apiGet<UserSettings>("/settings/user");
export const patchUser = (patch: UserPatch) => apiSend<UserSettings>("PATCH", "/settings/user", patch);

// -- appearance (app-wide theme) --------------------------------------------
export const getAppearance = () => apiGet<Appearance>("/settings/appearance");
export const patchAppearance = (theme: ThemePref) =>
  apiSend<Appearance>("PATCH", "/settings/appearance", { theme });

// -- models -----------------------------------------------------------------
export const listModels = () => apiGet<ModelConfig[]>("/settings/models");
export const createModel = (body: ModelInput) => apiSend<ModelConfig>("POST", "/settings/models", body);
export const patchModel = (id: string, body: Partial<ModelInput>) =>
  apiSend<ModelConfig>("PATCH", `/settings/models/${id}`, body);
export const deleteModel = (id: string) => apiSend<void>("DELETE", `/settings/models/${id}`);
export const testModel = (id: string) => apiSend<ModelTestResult>("POST", `/settings/models/${id}/test`);

// -- ai (utility model) -----------------------------------------------------
export const getAI = () => apiGet<AISettings>("/settings/ai");
export const patchAI = (patch: AISettings) => apiSend<AISettings>("PATCH", "/settings/ai", patch);

// -- ai-jobs ----------------------------------------------------------------
export const listJobs = () => apiGet<AIJobDefinition[]>("/settings/ai-jobs");
export const createJob = (body: AIJobInput) => apiSend<AIJobDefinition>("POST", "/settings/ai-jobs", body);
export const patchJob = (id: string, body: Partial<AIJobInput>) =>
  apiSend<AIJobDefinition>("PATCH", `/settings/ai-jobs/${id}`, body);
export const deleteJob = (id: string) => apiSend<void>("DELETE", `/settings/ai-jobs/${id}`);

// -- placeholders -----------------------------------------------------------
export const listPlaceholders = () => apiGet<Placeholder[]>("/settings/placeholders");
