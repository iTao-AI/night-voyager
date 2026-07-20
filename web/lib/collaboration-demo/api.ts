import {
  parseAdvisorConfirmedFactPage,
  parseAdvisorMemoryCandidateList,
  parseCollaborationThread,
  parseMemoryCandidateVerification,
  parseMessageEvent,
  parseMessagePage,
  parseParticipantConfirmedFactPage,
  parseParticipantMemoryCandidate,
  parseParticipantMemoryCandidateList,
  type CollaborationMessage,
  type CollaborationThread,
  type ConfirmedFactAdvisor,
  type ConfirmedFactParticipant,
  type MemoryCandidateAdvisor,
  type MemoryCandidateParticipant,
  type MemoryCandidateVerification,
  type MessagePage,
} from "./contracts";
import { parsePlanningSkillInspector, type PlanningSkillInspector } from "../skill-inspector/contracts";

export interface AppendMessageBody { schema_version: 1; body: string }
export interface ProposalBody { schema_version: 1; case_revision: number; proposal: { schema_version: 1; fact_key: string; value: unknown } }
export interface VerificationBody { schema_version: 1; expected_case_revision: number; decision: "confirm" | "reject"; reason: string }

export class CollaborationDemoApiError extends Error {
  constructor(public readonly status: number, public readonly code: string) { super(code); }
}

async function json(path: string, init: RequestInit = {}): Promise<unknown> {
  const response = await fetch(path, { ...init, cache: "no-store" });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const code = payload && typeof payload === "object" && "code" in payload ? String(payload.code) : "unknown";
    throw new CollaborationDemoApiError(response.status, code);
  }
  return payload;
}

function mutationHeaders(csrf: string, key: string): Headers {
  return new Headers({ "Content-Type": "application/json", "X-CSRF-Token": csrf, "Idempotency-Key": key });
}

export interface CollaborationDemoApi {
  thread(caseId: string): Promise<CollaborationThread>;
  messages(threadId: string, afterSequence?: number, limit?: number): Promise<MessagePage>;
  appendMessage(threadId: string, body: AppendMessageBody, csrf: string, key: string): Promise<CollaborationMessage>;
  proposeCandidate(messageId: string, body: ProposalBody, csrf: string, key: string): Promise<MemoryCandidateParticipant>;
  candidates(caseId: string, role: "parent"): Promise<readonly MemoryCandidateParticipant[]>;
  candidates(caseId: string, role: "advisor"): Promise<readonly MemoryCandidateAdvisor[]>;
  verifyCandidate(candidateId: string, body: VerificationBody, csrf: string, key: string): Promise<MemoryCandidateVerification>;
  confirmedFacts(caseId: string, role: "parent"): Promise<{ schema_version: 1; current: readonly ConfirmedFactParticipant[] }>;
  confirmedFacts(caseId: string, role: "advisor"): Promise<{ schema_version: 1; current: readonly ConfirmedFactAdvisor[]; history: readonly ConfirmedFactAdvisor[]; next_cursor: string | null }>;
  planningSkillInspector(caseId: string): Promise<PlanningSkillInspector>;
}

async function readCandidates(caseId: string, role: "parent"): Promise<readonly MemoryCandidateParticipant[]>;
async function readCandidates(caseId: string, role: "advisor"): Promise<readonly MemoryCandidateAdvisor[]>;
async function readCandidates(caseId: string, role: "parent" | "advisor"): Promise<readonly MemoryCandidateParticipant[] | readonly MemoryCandidateAdvisor[]> {
  const payload = await json(`/api/demo/cases/${caseId}/memory-candidates`);
  return role === "parent" ? parseParticipantMemoryCandidateList(payload) : parseAdvisorMemoryCandidateList(payload);
}

async function readConfirmedFacts(caseId: string, role: "parent"): Promise<{ schema_version: 1; current: readonly ConfirmedFactParticipant[] }>;
async function readConfirmedFacts(caseId: string, role: "advisor"): Promise<{ schema_version: 1; current: readonly ConfirmedFactAdvisor[]; history: readonly ConfirmedFactAdvisor[]; next_cursor: string | null }>;
async function readConfirmedFacts(caseId: string, role: "parent" | "advisor"): Promise<{ schema_version: 1; current: readonly ConfirmedFactParticipant[] } | { schema_version: 1; current: readonly ConfirmedFactAdvisor[]; history: readonly ConfirmedFactAdvisor[]; next_cursor: string | null }> {
  const payload = await json(`/api/demo/cases/${caseId}/confirmed-facts`);
  return role === "parent" ? parseParticipantConfirmedFactPage(payload) : parseAdvisorConfirmedFactPage(payload);
}

export function createCollaborationDemoApi(): CollaborationDemoApi {
  return {
    async thread(caseId) { return parseCollaborationThread(await json(`/api/demo/cases/${caseId}/collaboration-thread`)); },
    async messages(threadId, afterSequence = 0, limit = 50) { return parseMessagePage(await json(`/api/demo/collaboration-threads/${threadId}/messages?after_sequence=${afterSequence}&limit=${limit}`)); },
    async appendMessage(threadId, body, csrf, key) { return parseMessageEvent(await json(`/api/demo/collaboration-threads/${threadId}/messages`, { method: "POST", headers: mutationHeaders(csrf, key), body: JSON.stringify(body) })); },
    async proposeCandidate(messageId, body, csrf, key) { return parseParticipantMemoryCandidate(await json(`/api/demo/messages/${messageId}/memory-candidates`, { method: "POST", headers: mutationHeaders(csrf, key), body: JSON.stringify(body) })); },
    candidates: readCandidates,
    async verifyCandidate(candidateId, body, csrf, key) { return parseMemoryCandidateVerification(await json(`/api/demo/memory-candidates/${candidateId}/verification-decisions`, { method: "POST", headers: mutationHeaders(csrf, key), body: JSON.stringify(body) })); },
    confirmedFacts: readConfirmedFacts,
    async planningSkillInspector(caseId) { return parsePlanningSkillInspector(await json(`/api/demo/cases/${caseId}/planning-skill-inspector`)); },
  };
}
