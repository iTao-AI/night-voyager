import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { CollaborationDemo } from "../../components/collaboration-demo/CollaborationDemo";
import { ConfirmedFactSummary } from "../../components/collaboration-demo/ConfirmedFactSummary";
import { MemoryCandidateCard } from "../../components/collaboration-demo/MemoryCandidateCard";
import { SharedThread } from "../../components/collaboration-demo/SharedThread";

const CASE = "41000000-0000-0000-0000-000000000001";
const THREAD = "42000000-0000-0000-0000-000000000001";
const MESSAGE = "43000000-0000-0000-0000-000000000001";
const CANDIDATE = "44000000-0000-0000-0000-000000000001";
const FACT = "45000000-0000-0000-0000-000000000001";
const AT = "2026-07-20T01:02:03Z";
const SHA = "a".repeat(64);
const budget = { schema_version: 1 as const, currency: "CNY" as const, period: "program_total" as const, preferred_minor: 30_000_000, hard_ceiling_minor: 40_000_000, elasticity_bps: 1000, refused: false };
const thread = { schema_version: 1 as const, thread_id: THREAD, case_id: CASE, created_by_actor_id: CASE, created_at: AT };
const message = { schema_version: 1 as const, message_event_id: MESSAGE, thread_id: THREAD, case_id: CASE, sequence_no: 1, actor_id: CASE, actor_role: "parent" as const, body: "Our confirmed program budget is 300,000 to 400,000 CNY.", content_sha256: SHA, created_at: AT };
const participantCandidate = { schema_version: 1 as const, fact_key: "family.budget" as const, value: budget, state: "pending" as const, created_at: AT, expires_at: "2026-07-27T01:02:03Z" };
const advisorCandidate = { ...participantCandidate, candidate_id: CANDIDATE, message_event_id: MESSAGE, source_message_sequence_no: 1, subject_actor_id: CASE, subject_role: "parent" as const, case_revision: 1, verification_id: MESSAGE, decision: "confirm" as const, reason: "Confirmed by advisor.", request_sha256: SHA, value_sha256: SHA, state: "confirmed" as const };
const fact = { schema_version: 1 as const, fact_key: "family.budget" as const, value: budget, fact_version: 1, confirmed_at: AT, subject_role: "parent" as const, confirming_advisor_role: "advisor" as const, confirmed_fact_id: FACT, candidate_id: CANDIDATE, verification_id: MESSAGE, source_message_event_id: MESSAGE, source_message_sequence_no: 1, source_message_sha256_prefix: "aaaaaaaaaaaa", confirming_advisor_actor_id: CASE, reason: "Confirmed by advisor.", supersedes_fact_id: null };
const baseContext = { role: "parent" as const, caseId: CASE, thread, messages: [message], candidate: null, fact: null, caseRevision: 1 };

const hook = vi.hoisted(() => ({ current: {} as Record<string, unknown> }));
vi.mock("../../lib/collaboration-demo/use-collaboration-demo", async () => {
  const actual = await vi.importActual<typeof import("../../lib/collaboration-demo/use-collaboration-demo")>("../../lib/collaboration-demo/use-collaboration-demo");
  return { ...actual, useCollaborationDemo: () => hook.current };
});

function setState(state: unknown) {
  hook.current = { state, journeyConflict: null, connectParent: vi.fn(), appendMessage: vi.fn(), proposeBudget: vi.fn(), switchToAdvisor: vi.fn(), confirmCandidate: vi.fn(), retry: vi.fn(), endConflictingJourney: vi.fn() };
}

afterEach(() => { cleanup(); vi.clearAllMocks(); });

it("renders shared thread empty and populated states without UUID-first copy", () => {
  const { rerender, container } = render(<SharedThread messages={[]} />);
  expect(screen.getByRole("heading", { name: "Shared Case thread" })).toBeVisible();
  expect(screen.getByText("No participant messages yet.")).toBeVisible();
  rerender(<SharedThread messages={[message]} />);
  expect(screen.getByText(message.body)).toBeVisible();
  expect(screen.getByText(/Parent · message 1/i)).toBeVisible();
  expect(container).not.toHaveTextContent(MESSAGE);
});

it("presents the typed budget proposal and confirmed provenance", () => {
  const { rerender, container } = render(<MemoryCandidateCard candidate={participantCandidate} />);
  expect(screen.getByRole("heading", { name: "Budget proposal" })).toBeVisible();
  expect(screen.getByText("300,000–400,000 CNY")).toBeVisible();
  expect(screen.getByText("Pending advisor confirmation")).toBeVisible();
  rerender(<MemoryCandidateCard candidate={advisorCandidate} />);
  expect(screen.getByText("Confirmed by advisor.")).toBeVisible();
  rerender(<ConfirmedFactSummary fact={fact} caseRevision={2} />);
  expect(screen.getByRole("heading", { name: "Confirmed family fact" })).toBeVisible();
  expect(screen.getByText("Fact version 1")).toBeVisible();
  expect(screen.getByText("Case revision 2")).toBeVisible();
  expect(container).not.toHaveTextContent(/confirmed_fact_id|candidate_id|schema_version|45000000/i);
});

it("renders the six governed storyline beats and no task or generic-chat affordance", async () => {
  setState({ value: "bootstrapping_parent", context: { ...baseContext, thread: null, messages: [] } });
  const view = render(<CollaborationDemo />);
  expect(screen.getByRole("heading", { name: "Governed collaboration walkthrough" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Start parent walkthrough" }));
  expect(hook.current.connectParent).toHaveBeenCalledOnce();

  setState({ value: "thread_ready", context: baseContext });
  view.rerender(<CollaborationDemo />);
  expect(screen.getByText("Role: Parent")).toBeVisible();
  expect(screen.getByRole("button", { name: "Propose this budget for advisor review" })).toBeEnabled();

  setState({ value: "proposal_pending", context: { ...baseContext, candidate: participantCandidate } });
  view.rerender(<CollaborationDemo />);
  expect(screen.getByText("Pending advisor confirmation")).toBeVisible();
  expect(screen.getByRole("button", { name: "Continue as assigned advisor" })).toBeEnabled();

  setState({ value: "advisor_reviewing", context: { ...baseContext, role: "advisor", candidate: { ...advisorCandidate, state: "pending", verification_id: null, decision: null, reason: null } } });
  view.rerender(<CollaborationDemo />);
  expect(screen.getByText("Role: Advisor")).toBeVisible();
  expect(screen.getByRole("button", { name: "Confirm family budget" })).toBeEnabled();
  await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("heading", { name: "Advisor confirmation" })));

  setState({ value: "replan_required", context: { ...baseContext, role: "advisor", candidate: advisorCandidate, fact, caseRevision: 2 } });
  view.rerender(<CollaborationDemo />);
  expect(screen.getByRole("heading", { name: "Re-plan required" })).toBeVisible();
  expect(screen.getByText("Case revision 2")).toBeVisible();
  expect(screen.queryByRole("button", { name: /create.*task/i })).toBeNull();
  expect(screen.queryByText(/chat|agenttask|eventsource|schema_version|41000000/i)).toBeNull();
});

it("shows bounded recovery categories with an explicit retry", () => {
  setState({ value: "recoverable_error", category: "active_task_blocked", resumePhase: "advisor_reviewing", context: { ...baseContext, role: "advisor" } });
  render(<CollaborationDemo />);
  expect(screen.getByRole("heading", { name: "Collaboration paused safely" })).toBeVisible();
  expect(screen.getByText(/active planning task/i)).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Reload collaboration authority" }));
  expect(hook.current.retry).toHaveBeenCalledOnce();
});
