import { describe, expect, it } from "vitest";

import {
  parseCollaborationThread,
  parseConfirmedFactPage,
  parseMemoryCandidateList,
  parseMemoryCandidateVerification,
  parseMessageEvent,
  parseMessagePage,
} from "../../lib/collaboration-demo/contracts";

const ID = "40000000-0000-0000-0000-000000000031";
const ID2 = "40000000-0000-0000-0000-000000000032";
const AT = "2026-07-20T01:02:03Z";
const SHA = "a".repeat(64);

const thread = {
  schema_version: 1,
  thread_id: ID,
  case_id: ID2,
  created_by_actor_id: ID,
  created_at: AT,
};

const message = {
  schema_version: 1,
  message_event_id: ID,
  thread_id: ID2,
  case_id: ID,
  sequence_no: 1,
  actor_id: ID2,
  actor_role: "parent",
  body: "Our family budget is now confirmed.",
  content_sha256: SHA,
  created_at: AT,
};

const participantCandidate = {
  schema_version: 1,
  fact_key: "family.budget",
  value: {
    schema_version: 1,
    currency: "CNY",
    period: "program_total",
    preferred_minor: 30_000_000,
    hard_ceiling_minor: 40_000_000,
    elasticity_bps: 1000,
    refused: false,
  },
  state: "pending",
  created_at: AT,
  expires_at: "2026-07-27T01:02:03Z",
};

const advisorCandidate = {
  ...participantCandidate,
  candidate_id: ID,
  message_event_id: ID2,
  source_message_sequence_no: 1,
  subject_actor_id: ID2,
  subject_role: "parent",
  case_revision: 1,
  verification_id: null,
  decision: null,
  reason: null,
  request_sha256: SHA,
  value_sha256: "b".repeat(64),
};

describe("collaboration response contracts", () => {
  it("accepts the exact thread and message projections", () => {
    expect(parseCollaborationThread(thread)).toEqual(thread);
    expect(parseMessageEvent(message)).toEqual(message);
    expect(parseMessagePage({ schema_version: 1, items: [message], next_after_sequence: 1 })).toMatchObject({ next_after_sequence: 1 });
  });

  it.each([
    ["extra thread field", { ...thread, internal_role: "api" }, parseCollaborationThread],
    ["malformed thread UUID", { ...thread, thread_id: "not-a-uuid" }, parseCollaborationThread],
    ["malformed timestamp", { ...message, created_at: "today" }, parseMessageEvent],
    ["malformed digest", { ...message, content_sha256: "short" }, parseMessageEvent],
    ["unknown message role", { ...message, actor_role: "operator" }, parseMessageEvent],
  ])("rejects %s", (_name, value, parse) => {
    expect(() => parse(value)).toThrow("invalid response");
  });

  it("keeps participant and advisor candidate projections closed", () => {
    expect(parseMemoryCandidateList([participantCandidate])).toEqual([participantCandidate]);
    expect(parseMemoryCandidateList([advisorCandidate])).toEqual([advisorCandidate]);
    expect(() => parseMemoryCandidateList([{ ...participantCandidate, candidate_id: ID }])).toThrow("invalid response");
    expect(() => parseMemoryCandidateList([{ ...advisorCandidate, request_sha256: undefined }])).toThrow("invalid response");
  });

  it("validates typed proposal values and terminal verification identity", () => {
    expect(() => parseMemoryCandidateList([{ ...participantCandidate, value: { ...participantCandidate.value, hard_ceiling_minor: "40000000" } }])).toThrow("invalid response");
    expect(parseMemoryCandidateVerification({ schema_version: 1, verification_id: ID, candidate_id: ID2, decision: "confirm", result_fact_id: ID, result_revision: 2, replayed: false })).toMatchObject({ result_revision: 2 });
    expect(() => parseMemoryCandidateVerification({ schema_version: 1, verification_id: ID, candidate_id: ID2, decision: "confirm", result_fact_id: null, result_revision: null, replayed: false })).toThrow("invalid response");
  });

  it("discriminates participant and advisor confirmed-fact pages", () => {
    const participantFact = { schema_version: 1, fact_key: "family.budget", value: participantCandidate.value, fact_version: 1, confirmed_at: AT, subject_role: "parent", confirming_advisor_role: "advisor" };
    const advisorFact = { ...participantFact, confirmed_fact_id: ID, candidate_id: ID2, verification_id: ID, source_message_event_id: ID2, source_message_sequence_no: 1, source_message_sha256_prefix: "abcdef123456", confirming_advisor_actor_id: ID, reason: "Confirmed with the family.", supersedes_fact_id: null };
    expect(parseConfirmedFactPage({ schema_version: 1, current: [participantFact] })).toMatchObject({ current: [participantFact] });
    expect(parseConfirmedFactPage({ schema_version: 1, current: [advisorFact], history: [], next_cursor: null })).toMatchObject({ current: [advisorFact] });
    expect(() => parseConfirmedFactPage({ schema_version: 1, current: [{ ...participantFact, candidate_id: ID }] })).toThrow("invalid response");
    expect(() => parseConfirmedFactPage({ schema_version: 1, current: [{ ...advisorFact, source_message_sha256_prefix: SHA }] , history: [], next_cursor: null })).toThrow("invalid response");
  });
});
