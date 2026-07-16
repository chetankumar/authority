import { apiSend } from "./client";
import type { Proposal } from "./conversations";

export interface ProposalAcceptResult {
  proposal: Proposal;
  result: Record<string, unknown>;
}

export function acceptProposal(bookId: string, proposalId: string) {
  return apiSend<ProposalAcceptResult>("POST", `/books/${bookId}/proposals/${proposalId}/accept`);
}

export function rejectProposal(bookId: string, proposalId: string) {
  return apiSend<Proposal>("POST", `/books/${bookId}/proposals/${proposalId}/reject`);
}
