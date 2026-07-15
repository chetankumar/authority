import { apiSend } from "./client";
import type { RelationshipType, SoftRelationship } from "./scenes";

export const createRelationship = (
  bookId: string,
  body: { fromSceneId: string; toSceneId: string; type: RelationshipType },
) => apiSend<SoftRelationship>("POST", `/books/${bookId}/relationships`, body);

export const deleteRelationship = (bookId: string, relId: string) =>
  apiSend<void>("DELETE", `/books/${bookId}/relationships/${relId}`);
