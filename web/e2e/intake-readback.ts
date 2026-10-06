import { isDeepStrictEqual } from "node:util";
import {
  parseAdvisorMemoryCandidateList, parseParticipantMemoryCandidate,
  type MemoryCandidateAdvisor, type MemoryCandidateParticipant,
} from "../lib/collaboration-demo/contracts";

export function intakeProposalReplay(initial: unknown, replayed: unknown): MemoryCandidateParticipant {
  const candidate = parseParticipantMemoryCandidate(initial);
  const repeated = parseParticipantMemoryCandidate(replayed);
  if (candidate.fact_key !== "student.intake" || candidate.value !== "2028-02"
    || candidate.state !== "pending" || !isDeepStrictEqual(candidate, repeated)) {
    throw new Error("intake proposal replay mismatch");
  }
  return candidate;
}

export function intakeCandidateForConfirmation(readback: unknown, proposal: MemoryCandidateParticipant): MemoryCandidateAdvisor {
  const matches = parseAdvisorMemoryCandidateList(readback).filter(candidate =>
    candidate.case_revision === 1 && candidate.subject_role === "student"
    && candidate.fact_key === proposal.fact_key && candidate.value === proposal.value
    && candidate.state === proposal.state && candidate.created_at === proposal.created_at
    && candidate.expires_at === proposal.expires_at);
  if (matches.length !== 1) throw new Error("expected one persisted intake candidate for confirmation");
  return matches[0];
}
