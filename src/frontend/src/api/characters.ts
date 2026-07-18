import { apiGet, apiSend } from "./client";

export type CharacterRelationshipCategory =
  | "family"
  | "romantic"
  | "friendship"
  | "rivalry"
  | "professional"
  | "mentorship"
  | "other";

export interface Character {
  id: string;
  name: string;
  aliases: string[];
  age: string;
  gender: string;
  nationality: string;
  ethnicity: string;
  occupation: string;
  want: string;
  need: string;
  flaw: string;
  arc: string;
  personality: string;
  history: string;
  notes: string;
  voiceId: string;
  voiceName: string;
  sceneCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface CharacterInput {
  name?: string;
  aliases?: string[];
  age?: string;
  gender?: string;
  nationality?: string;
  ethnicity?: string;
  occupation?: string;
  want?: string;
  need?: string;
  flaw?: string;
  arc?: string;
  personality?: string;
  history?: string;
  notes?: string;
  voiceId?: string;
  voiceName?: string;
}

export interface CharacterRelationship {
  id: string;
  characterAId: string;
  characterBId: string;
  category: CharacterRelationshipCategory;
  aToB: string;
  bToA: string;
  description: string;
  createdAt: string;
  updatedAt: string;
}

export interface CharacterRelationshipInput {
  characterAId: string;
  characterBId: string;
  category: CharacterRelationshipCategory;
  aToB: string;
  bToA: string;
  description?: string;
}

export interface CharacterRelationshipUpdate {
  category?: CharacterRelationshipCategory;
  aToB?: string;
  bToA?: string;
  description?: string;
}

// ---- Characters ---------------------------------------------------------------

export const listCharacters = (bookId: string) =>
  apiGet<Character[]>(`/books/${bookId}/characters`);

export const createCharacter = (bookId: string, body: CharacterInput) =>
  apiSend<Character>("POST", `/books/${bookId}/characters`, body);

export const updateCharacter = (bookId: string, chrId: string, body: CharacterInput) =>
  apiSend<Character>("PATCH", `/books/${bookId}/characters/${chrId}`, body);

export const deleteCharacter = (bookId: string, chrId: string) =>
  apiSend<void>("DELETE", `/books/${bookId}/characters/${chrId}`);

// ---- Character relationships ---------------------------------------------------

export const listCharacterRelationships = (bookId: string) =>
  apiGet<CharacterRelationship[]>(`/books/${bookId}/character-relationships`);

export const createCharacterRelationship = (bookId: string, body: CharacterRelationshipInput) =>
  apiSend<CharacterRelationship>("POST", `/books/${bookId}/character-relationships`, body);

export const updateCharacterRelationship = (
  bookId: string,
  relId: string,
  body: CharacterRelationshipUpdate,
) => apiSend<CharacterRelationship>("PATCH", `/books/${bookId}/character-relationships/${relId}`, body);

export const deleteCharacterRelationship = (bookId: string, relId: string) =>
  apiSend<void>("DELETE", `/books/${bookId}/character-relationships/${relId}`);
