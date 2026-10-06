import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { AdvisorLedger, AdvisorLedgerAction } from "../../components/connected-demo/AdvisorLedger";
import { RevisionFactEditor } from "../../components/connected-demo/RevisionFactEditor";
import { PlanningRevisionComparison } from "../../components/connected-demo/PlanningRevisionComparison";
import { PresentationProvider } from "../../lib/presentation/context";
import type { ConfirmedFactParticipant, MemoryCandidateAdvisor } from "../../lib/collaboration-demo/contracts";
import { parseLedger, parseLedgerV2 } from "../../lib/connected-demo/contracts";
import { validateRevisionIntent, revisionMessageBody, revisionProposalBody, pendingRevisionCandidate } from "../../lib/connected-demo/revision";
import { saveRecoveryMetadata, loadRecoveryMetadata } from "../../lib/connected-demo/session-storage";
import { CASE_ID, ledger } from "./connected-demo-test-data";

const fact: ConfirmedFactParticipant = {
  schema_version: 1, fact_key: "student.intake", value: "2027-02", fact_version: 1,
  confirmed_at: "2026-10-01T00:00:00Z", subject_role: "student", confirming_advisor_role: "advisor",
};
const facts = { caseId: CASE_ID, caseRevision: 7, facts: [fact] };
const intent = { expectedCaseRevision: 7, factKey: "student.intake" as const, value: "2028-02" };
const wrapper = PresentationProvider;
afterEach(() => { cleanup(); sessionStorage.clear(); localStorage.clear(); });

it("uses the current confirmed intake as the sole editable authority and submits the actual month", () => {
  expect(validateRevisionIntent(intent, facts)).toEqual({ ok: true, intent });
  expect(revisionProposalBody(intent)).toEqual({ schema_version: 1, case_revision: 7, proposal: { schema_version: 1, fact_key: "student.intake", value: "2028-02" } });
  expect(revisionMessageBody(intent).body).toContain('student.intake: "2028-02"');
});

it.each(["0000-02", "2028-00", "2028-13", "2028-2", "２０２８-02", "2028-02 ", " 2028-02", 202802, "2027-02"])("rejects invalid, coerced or unchanged intake %s", (value) => {
  expect(validateRevisionIntent({ ...intent, value } as never, facts).ok).toBe(false);
});

it("refuses missing, ambiguous, stale and parent-owned intake facts", () => {
  expect(validateRevisionIntent(intent, null).ok).toBe(false);
  expect(validateRevisionIntent(intent, { ...facts, facts: [] }).ok).toBe(false);
  expect(validateRevisionIntent(intent, { ...facts, facts: [fact, fact] }).ok).toBe(false);
  expect(validateRevisionIntent(intent, { ...facts, caseRevision: 8 })).toMatchObject({ ok: false, code: "stale" });
  expect(validateRevisionIntent(intent, { ...facts, facts: [{ ...fact, subject_role: "parent" }] }).ok).toBe(false);
});

it("matches only the actual current student intake candidate", () => {
  const candidate = { ...fact, state: "pending", case_revision: 7, candidate_id: CASE_ID, value: "2028-02" } as unknown as MemoryCandidateAdvisor;
  expect(pendingRevisionCandidate([candidate], 7)).toEqual(candidate);
  expect(pendingRevisionCandidate([{ ...candidate, subject_role: "parent" }], 7)).toBeNull();
  expect(pendingRevisionCandidate([candidate], 8)).toBeNull();
});

it("restores the exact intake intention without widening the saved envelope", () => {
  saveRecoveryMetadata({ schema_version: 3, journey: "advisor-family", role: "student", csrf: "csrf", caseId: CASE_ID, currentRevision: 7, currentTaskId: null, predecessorRunId: null, currentRunId: null, cursor: 0, phase: "revision_requested", mutations: {}, revisionIntent: intent });
  expect(loadRecoveryMetadata()?.revisionIntent).toEqual(intent);
});

it("edits the actual student month and retains the saved month after reload", () => {
  const submit = vi.fn();
  render(<RevisionFactEditor expectedCaseId={CASE_ID} currentFacts={facts} expectedCaseRevision={7} submittedIntent={intent} onSubmit={submit} />, { wrapper });
  const input = screen.getByRole("textbox", { name: "新入学月份" });
  expect(input).toHaveValue("2028-02");
  fireEvent.change(input, { target: { value: "2028-09" } });
  fireEvent.click(screen.getByRole("button", { name: "提交变更提案" }));
  expect(submit).toHaveBeenCalledWith({ ...intent, value: "2028-09" });
});

it("requires explicit student preparation when a parent sees the intake option", () => {
  const prepare = vi.fn();
  render(<RevisionFactEditor expectedCaseId={CASE_ID} currentFacts={facts} expectedCaseRevision={7} activeRole="parent" onPrepareFact={prepare} onSubmit={vi.fn()} />, { wrapper });
  expect(screen.queryByRole("textbox", { name: "新入学月份" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "以学生编辑入学月份" }));
  expect(prepare).toHaveBeenCalledWith("student.intake");
});

function intakeLedger() {
  const value = structuredClone(ledger("revision_review_required"));
  return {
    ...value, schema_version: 3, case_intake: "2028-02",
    planning_run: { ...value.planning_run!, source_pack_id: "50000000-0000-0000-0000-000000000017" },
    routes: value.routes.map(route => ({ ...route, cost: route.cost ? { ...route.cost, tuition_minor: 4200000, living_minor: 2600000, fx_rate: "4.80", cny_total_minor: 32640000, intake: "2028-02" } : null })),
    comparison: {
      ...value.comparison!, schema: "night-voyager.planning-revision-comparison.v2",
      changed_fact: { fact_key: "student.intake", previous_value: "2027-02", current_value: "2028-02" },
      previous_request_review: { review_id: CASE_ID, review_version: 1, planning_run_id: value.comparison!.previous_planning_run_id, case_revision: 1, action: "request_revision" },
    },
  };
}

it("decodes exact V3 and shows changed intake alongside unchanged country eligibility", () => {
  const value = intakeLedger();
  expect(parseLedger(value)).toEqual(value);
  render(<PlanningRevisionComparison comparison={parseLedger(value).comparison!} />, { wrapper });
  expect(screen.getByText("2027-02")).toBeVisible();
  expect(screen.getByText("2028-02")).toBeVisible();
  expect(screen.getByText("上一版修订请求（历史）")).toBeVisible();
  expect(screen.getAllByText("结果未变化").length).toBeGreaterThan(0);
});

it.each(["cost_intake", "case_intake", "review_run", "review_revision", "review_notes", "unknown_schema", "extra_fact"])("rejects inconsistent V3 %s", (mutation) => {
  const value = intakeLedger();
  if (mutation === "cost_intake") value.routes[0].cost!.intake = "2027-02";
  else if (mutation === "case_intake") value.case_intake = "0000-02";
  else if (mutation === "review_run") value.comparison.previous_request_review.planning_run_id = "70000000-0000-0000-0000-000000000999";
  else if (mutation === "review_revision") value.comparison.previous_request_review.case_revision = 2;
  else if (mutation === "review_notes") Object.assign(value.comparison.previous_request_review, { reviewer_notes: "private" });
  else if (mutation === "extra_fact") Object.assign(value.comparison.changed_fact, { "family.budget": {} });
  else value.schema_version = 4;
  expect(() => parseLedger(value)).toThrow("invalid response");
});

it("allows an advisor to explicitly reject an unsupported intake proposal before replacing it", () => {
  const reject = vi.fn();
  const confirm = vi.fn();
  const candidate = { ...fact, value: "2028-09", state: "pending", case_revision: 1, candidate_id: CASE_ID } as unknown as MemoryCandidateAdvisor;
  render(<AdvisorLedgerAction ledger={ledger("revision_fact_pending")} revisionCandidates={[candidate]} onPrimaryAction={vi.fn()} onConfirmRevision={confirm} onRejectRevision={reject} />, { wrapper });
  fireEvent.change(screen.getByRole("textbox", { name: "确认理由" }), { target: { value: "No registered evidence for this month." } });
  fireEvent.click(screen.getByRole("button", { name: "拒绝当前入学提案" }));
  expect(reject).toHaveBeenCalledWith("No registered evidence for this month.");
  expect(confirm).not.toHaveBeenCalled();
});


it("keeps the exact old V2 decoder and rejects cross-version widening", () => {
  const legacy = JSON.parse(JSON.stringify(ledger("revision_review_required")));
  legacy.schema_version = 2;
  delete legacy.case_intake;
  legacy.routes.forEach((route: { cost: { intake?: string } | null }) => { if (route.cost) delete route.cost.intake; });
  legacy.comparison.schema = "night-voyager.planning-revision-comparison.v1";
  delete legacy.comparison.previous_request_review;
  expect(parseLedgerV2(legacy)).toEqual(legacy);
  expect(() => parseLedger(legacy)).toThrow("invalid response");
  expect(() => parseLedgerV2(intakeLedger())).toThrow("invalid response");
  expect(() => parseLedgerV2({ ...legacy, schema_version: 1 })).toThrow("invalid response");
});


it("discloses the actual current cost month and distinct hypothetical cost", () => {
  render(<AdvisorLedger ledger={parseLedger(intakeLedger())} onPrimaryAction={vi.fn()} />, { wrapper });
  expect(screen.getByRole("region", { name: "合成成本估算" })).toHaveTextContent("成本对应入学月份2028-02");
  expect(screen.getByText("¥326,400")).toBeVisible();
  expect(screen.getByRole("region", { name: "合成成本估算" })).toHaveTextContent("2026年7月1日");
});
