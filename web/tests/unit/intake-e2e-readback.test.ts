import { expect, it } from "vitest";
import { intakeCandidateForConfirmation, intakeProposalReplay } from "../../e2e/intake-readback";

const participant = {
  schema_version: 1, fact_key: "student.intake", value: "2028-02", state: "pending",
  created_at: "2026-07-01T00:00:00Z", expires_at: "2026-07-02T00:00:00Z",
};

it("checks an exact replay of the actual student projection without inventing a candidate ID", () => {
  expect(intakeProposalReplay(participant, { ...participant })).toEqual(participant);
  expect(participant).not.toHaveProperty("candidate_id");
});

it("rejects a different replay when both participant projections omit candidate IDs", () => {
  expect(() => intakeProposalReplay(participant, { ...participant, value: "2029-02" })).toThrow("intake proposal replay mismatch");
});

it("rejects a missing participant projection instead of comparing two undefined IDs", () => {
  expect(() => intakeProposalReplay({}, {})).toThrow();
});

const advisor = {
  ...participant, candidate_id: "49000000-0000-0000-0000-000000000101",
  message_event_id: "49000000-0000-0000-0000-000000000102", source_message_sequence_no: 1,
  subject_actor_id: "20000000-0000-0000-0000-000000000002", subject_role: "student", case_revision: 1,
  verification_id: null, decision: null, reason: null, request_sha256: "a".repeat(64), value_sha256: "b".repeat(64),
};

it("binds confirmation to the one advisor candidate matching the replayed student projection", () => {
  const proposal = intakeProposalReplay(participant, { ...participant });
  expect(intakeCandidateForConfirmation([
    { ...advisor, candidate_id: "49000000-0000-0000-0000-000000000103", case_revision: 2 }, advisor,
  ], proposal).candidate_id).toBe(advisor.candidate_id);
});

it("refuses missing or duplicate persisted candidates instead of selecting an arbitrary ID", () => {
  const proposal = intakeProposalReplay(participant, { ...participant });
  expect(() => intakeCandidateForConfirmation([], proposal)).toThrow("expected one persisted intake candidate");
  expect(() => intakeCandidateForConfirmation([
    advisor, { ...advisor, candidate_id: "49000000-0000-0000-0000-000000000103" },
  ], proposal)).toThrow("expected one persisted intake candidate");
});

it("uses the actual array DTO and rejects missing advisor identity", () => {
  const proposal = intakeProposalReplay(participant, { ...participant });
  expect(() => intakeCandidateForConfirmation({ schema_version: 1, items: [advisor] }, proposal)).toThrow();
  expect(() => intakeCandidateForConfirmation([participant], proposal)).toThrow();
});
