"""Conversation & message schemas (doc 03 db/conversations; doc 04 §2.2 / §9)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import ConversationKind, ConversationStatus, MessageAuthor, ParentType
from app.models.proposal import Proposal


class AiParticipant(BaseModel):
    enabled: bool = False
    modelId: str | None = None


class MessageContext(BaseModel):
    sceneId: str
    excerpt: str


class Message(BaseModel):
    id: str
    author: MessageAuthor
    modelId: str | None = None
    content: str = ""
    context: list[MessageContext] = Field(default_factory=list)
    proposals: list[Proposal] = Field(default_factory=list)
    createdAt: str


class ConversationSummary(BaseModel):
    id: str
    kind: ConversationKind
    title: str
    parentType: ParentType
    parentId: str
    status: ConversationStatus = ConversationStatus.open
    updatedAt: str
    messageCount: int = 0
    pendingProposals: int = 0


class Conversation(BaseModel):
    id: str
    kind: ConversationKind
    title: str = "Untitled"
    parentType: ParentType
    parentId: str
    aiParticipant: AiParticipant = Field(default_factory=AiParticipant)
    aiJobId: str | None = None
    aiJobName: str | None = None  # snapshot at run time
    status: ConversationStatus = ConversationStatus.open
    createdAt: str
    updatedAt: str
    messages: list[Message] = Field(default_factory=list)


# ---- request bodies ---------------------------------------------------------


class ConversationCreate(BaseModel):
    kind: ConversationKind
    parentType: ParentType
    parentId: str
    aiParticipant: AiParticipant | None = None
    title: str | None = None


class ConversationPatch(BaseModel):
    title: str | None = None
    status: ConversationStatus | None = None
    aiParticipant: AiParticipant | None = None


class MessageCreate(BaseModel):
    content: str
    context: list[MessageContext] | None = None


class AiJobRunRequest(BaseModel):
    aiJobId: str
    sceneId: str
    scope: str = "full"  # full | selection
    selectionText: str | None = None


class AiJobRunResponse(BaseModel):
    jobId: str
    conversationId: str
