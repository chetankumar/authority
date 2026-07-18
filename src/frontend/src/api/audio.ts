import { apiGet, apiSend } from "./client";

export type AudioSequenceItemType = "dialogue" | "narration" | "sfx";
export type AudioLineStatus = "new" | "regenerate" | "unchanged";
export type AudioSynthesisStatus = "idle" | "running" | "done" | "failed";

export interface VoiceSettings {
  stability: number;
  similarity_boost: number;
}

export interface Speaker {
  name: string;
  role: string;
  voice_name: string;
  voice_id: string;
  direction: string;
}

export interface AudioSequenceItem {
  id: string;
  type: AudioSequenceItemType;
  speaker: string | null;
  speaker_id: string | null;
  text: string;
  voice_settings: VoiceSettings | null;
  generation_status: AudioLineStatus;
  change_reason: string;
  renderedFile: string | null;
  duration_seconds: number | null;
  prompt_influence: number | null;
}

export interface AudioManifest {
  title: string;
  revision: number;
  speakers: Record<string, Speaker>;
  notes: Record<string, unknown>;
  sequence: AudioSequenceItem[];
  synthesisStatus: AudioSynthesisStatus;
  updatedAt: string;
  stitchedFile: string | null;
  lastError: string | null;
}

export interface AudioLinePatch {
  text?: string;
  voice_settings?: VoiceSettings;
}

export interface VoiceInfo {
  voiceId: string;
  name: string;
  category: string;
  gender: string;
  age: string;
  accent: string;
  description: string;
  previewUrl: string;
}

export interface ElevenLabsSettings {
  apiKeyMasked: string | null;
  voicesSyncedAt: string | null;
}

export const getAudioManifest = (bookId: string, sceneId: string) =>
  apiGet<AudioManifest>(`/books/${bookId}/scenes/${sceneId}/audio`);

export const patchAudioLine = (bookId: string, sceneId: string, itemId: string, body: AudioLinePatch) =>
  apiSend<AudioManifest>("PATCH", `/books/${bookId}/scenes/${sceneId}/audio/lines/${itemId}`, body);

export const generateAudioLine = (bookId: string, sceneId: string, itemId: string) =>
  apiSend<AudioManifest>("POST", `/books/${bookId}/scenes/${sceneId}/audio/lines/${itemId}/generate`);

export const generateAudioAll = (bookId: string, sceneId: string) =>
  apiSend<AudioManifest>("POST", `/books/${bookId}/scenes/${sceneId}/audio/generate`);

export const deleteAudio = (bookId: string, sceneId: string) =>
  apiSend<void>("DELETE", `/books/${bookId}/scenes/${sceneId}/audio`);

export const audioLineUrl = (bookId: string, sceneId: string, filename: string) =>
  `/api/books/${bookId}/scenes/${sceneId}/audio/lines/${encodeURIComponent(filename)}`;

export const audioStitchedUrl = (bookId: string, sceneId: string) =>
  `/api/books/${bookId}/scenes/${sceneId}/audio/stitched`;

export const getGitignore = (bookId: string) =>
  apiGet<{ patterns: string[] }>(`/books/${bookId}/gitignore`);

export const putGitignore = (bookId: string, patterns: string[]) =>
  apiSend<{ patterns: string[] }>("PUT", `/books/${bookId}/gitignore`, { patterns });

export const getElevenLabs = () => apiGet<ElevenLabsSettings>("/settings/elevenlabs");
export const patchElevenLabs = (body: { apiKey?: string | null }) =>
  apiSend<ElevenLabsSettings>("PATCH", "/settings/elevenlabs", body);
export const listElevenLabsVoices = () => apiGet<VoiceInfo[]>("/settings/elevenlabs/voices");
export const syncElevenLabsVoices = () => apiSend<VoiceInfo[]>("POST", "/settings/elevenlabs/voices/sync");

export const suggestVoice = (bookId: string, characterId: string) =>
  apiSend<{ voiceId: string | null; rationale: string }>(
    "POST",
    `/books/${bookId}/characters/${characterId}/voice/suggest`,
  );

/** Playlist gap timing — mirrors backend / speech_generator.py */
export const DEFAULT_GAP_MS = 500;
export const SPEAKER_CHANGE_GAP_MS = 650;
export const SFX_GAP_MS = 400;

export function gapMs(
  prev: AudioSequenceItem | null,
  curr: AudioSequenceItem,
): number {
  if (!prev) return 0;
  if (curr.type === "sfx" || prev.type === "sfx") return Math.max(DEFAULT_GAP_MS, SFX_GAP_MS);
  if (prev.speaker_id !== curr.speaker_id) return Math.max(DEFAULT_GAP_MS, SPEAKER_CHANGE_GAP_MS);
  return DEFAULT_GAP_MS;
}
