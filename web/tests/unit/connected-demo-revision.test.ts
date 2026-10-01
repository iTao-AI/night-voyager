import { describe, expect, it } from "vitest";
import type { BudgetValue, ConfirmedFactParticipant, MemoryCandidateAdvisor } from "../../lib/collaboration-demo/contracts";
import { validateBudgetRevision, validateRevisionIntent, pendingRevisionCandidate } from "../../lib/connected-demo/revision";

const budget: BudgetValue = { schema_version: 1, currency: "CNY", period: "program_total", preferred_minor: 30000000, hard_ceiling_minor: 40000000, elasticity_bps: 0, refused: false };
const fact = (fact_key: ConfirmedFactParticipant["fact_key"], value: ConfirmedFactParticipant["value"]): ConfirmedFactParticipant => ({ schema_version: 1, fact_key, value, fact_version: 1, confirmed_at: "2026-10-01T00:00:00Z", subject_role: "student", confirming_advisor_role: "advisor" });
const projection = { caseId: "40000000-0000-0000-0000-000000000002", caseRevision: 7, facts: [fact("student.preferred_countries", ["japan", "malaysia"]), fact("family.budget", budget)] };

describe("explicit single-fact revision validation", () => {
  it("accepts a real changed subset from non-default authoritative countries and canonicalizes order", () => {
    expect(validateRevisionIntent({ expectedCaseRevision: 7, factKey: "student.preferred_countries", value: ["malaysia", "australia"] }, projection)).toEqual({ ok: true, intent: { expectedCaseRevision: 7, factKey: "student.preferred_countries", value: ["australia", "malaysia"] } });
  });
  it.each([[], ["japan", "japan"], ["canada"], ["malaysia", "japan"]].map(value => ({ value })))("rejects invalid or unchanged countries $value", ({ value }) => {
    expect(validateRevisionIntent({ expectedCaseRevision: 7, factKey: "student.preferred_countries", value } as never, projection).ok).toBe(false);
  });
  it("rejects stale revision, missing authority and unsupported facts", () => {
    const intent = { expectedCaseRevision: 6, factKey: "student.preferred_countries" as const, value: ["australia"] as const };
    expect(validateRevisionIntent(intent, projection)).toMatchObject({ ok: false, code: "stale" });
    expect(validateRevisionIntent({ ...intent, expectedCaseRevision: 7 }, null).ok).toBe(false);
    expect(validateRevisionIntent({ ...intent, expectedCaseRevision: 7, factKey: "student.intake" } as never, projection).ok).toBe(false);
  });
  it("converts entered budget yuan and preserves the authoritative budget metadata", () => {
    expect(validateBudgetRevision({ preferredYuan: "320000", hardCeilingYuan: "420000" }, 7, projection)).toEqual({ ok: true, intent: { expectedCaseRevision: 7, factKey: "family.budget", value: { ...budget, preferred_minor: 32000000, hard_ceiling_minor: 42000000 } } });
  });
  it.each([
    { preferredYuan: "", hardCeilingYuan: "420000" },
    { preferredYuan: "0", hardCeilingYuan: "420000" },
    { preferredYuan: "320000.5", hardCeilingYuan: "420000" },
    { preferredYuan: "420001", hardCeilingYuan: "420000" },
    { preferredYuan: "90071992547410", hardCeilingYuan: "90071992547411" },
    { preferredYuan: "300000", hardCeilingYuan: "400000" },
  ])("rejects invalid or unchanged budget %j", (draft) => {
    expect(validateBudgetRevision(draft, 7, projection).ok).toBe(false);
  });
  it("rejects unsupported changes to budget metadata", () => {
    expect(validateRevisionIntent({ expectedCaseRevision: 7, factKey: "family.budget", value: { ...budget, preferred_minor: 31000000, elasticity_bps: 1000 } }, projection).ok).toBe(false);
  });
});

it("selects the actual single supported advisor candidate and closes on ambiguity or stale authority", () => {
  const candidate = { schema_version: 1, fact_key: "student.preferred_countries", value: ["malaysia"], state: "pending", case_revision: 7, candidate_id: "44000000-0000-0000-0000-000000000001", message_event_id: "43000000-0000-0000-0000-000000000001", source_message_sequence_no: 1, subject_actor_id: "40000000-0000-0000-0000-000000000002", subject_role: "student", created_at: "2026-10-01T00:00:00Z", expires_at: "2026-10-08T00:00:00Z", verification_id: null, decision: null, reason: null, request_sha256: "a".repeat(64), value_sha256: "a".repeat(64) } as MemoryCandidateAdvisor;
  expect(pendingRevisionCandidate([candidate], 7)).toEqual(candidate);
  expect(pendingRevisionCandidate([candidate, { ...candidate, candidate_id: "44000000-0000-0000-0000-000000000002", fact_key: "family.budget", value: budget }], 7)).toBeNull();
  expect(pendingRevisionCandidate([candidate], 8)).toBeNull();
});
