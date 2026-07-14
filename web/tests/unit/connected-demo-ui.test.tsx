import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";

import { AdvisorLedger } from "../../components/connected-demo/AdvisorLedger";
import { DecisionReceiptTimeline } from "../../components/connected-demo/DecisionReceiptTimeline";
import { FamilyDecisionBrief } from "../../components/connected-demo/FamilyDecisionBrief";
import { RecoveryNotice } from "../../components/connected-demo/RecoveryNotice";
import type { AdvisorLedger as Ledger, CurrentDecisionBrief } from "../../lib/connected-demo/contracts";

afterEach(cleanup);

it("renders task-ready authority with one primary action", () => {
  const ledger = {
    schema_version: 1,
    proof_mode: "synthetic-demo",
    phase: "task-ready",
    case_id: "case",
    case_revision: 1,
    case_state: "planning",
    canonical_task_inputs: { schema_version: 1, operation: "generate_planning_run_v1" },
    task: null,
    planning_run: null,
    routes: [],
    evidence: [],
    review_inputs: null,
    current_brief_id: null,
    recovery: null,
  } as unknown as Ledger;
  render(<AdvisorLedger ledger={ledger} onPrimaryAction={() => undefined} />);
  expect(screen.getByRole("heading", { name: /Advisor Ledger/i })).toBeVisible();
  expect(screen.getByRole("button", { name: /Create planning task/i })).toBeEnabled();
  expect(screen.queryByText(/lease owner|organization_id|reviewer notes/i)).toBeNull();
});

it("keeps Malaysia blocked and discloses evidence", () => {
  const ledger = {
    phase: "review-required",
    routes: [{ country: "malaysia", outcome: "blocked", reason_code: "evidence_gap", eligible: false }],
    evidence: [{ claim: "australia_tuition", publisher: "Synthetic publisher", limitation: "Synthetic only" }],
  } as unknown as Ledger;
  render(<AdvisorLedger ledger={ledger} onPrimaryAction={() => undefined} />);
  expect(screen.getByRole("button", { name: /Choose Malaysia/i })).toBeDisabled();
  expect(screen.getByText(/Synthetic publisher/i)).toBeVisible();
});

it("renders only server-derived family constraints", () => {
  const brief = {
    phase: "family-review",
    decision_requirements: {
      currency: "CNY",
      pinned_cost_minor: 31_000_000,
      hard_ceiling_minor: 40_000_000,
      required_trade_offs: ["budget_elasticity"],
    },
  } as unknown as CurrentDecisionBrief;
  render(<FamilyDecisionBrief brief={brief} confirmed={false} onConfirm={() => undefined} onSubmit={() => undefined} />);
  expect(screen.getByText(/31,000,000 CNY/i)).toBeVisible();
  expect(screen.getByText(/40,000,000 CNY/i)).toBeVisible();
  expect(screen.getByRole("button", { name: /Confirm Australia route/i })).toBeDisabled();
});

it("shows fail-closed recovery without parent presentation", () => {
  render(<RecoveryNotice code="session_recovery_required" onReconnect={() => undefined} />);
  expect(screen.getByRole("heading", { name: /Recovery required/i })).toBeVisible();
  expect(screen.queryByText(/Decision Receipt/i)).toBeNull();
});

it("presents the parent receipt without internal identifiers or raw debug JSON", () => {
  const brief = {
    phase: "plan-ready",
    receipt: {
      decision_id: "hidden-decision-id",
      receipt_id: "hidden-receipt-id",
      selected_route_id: "hidden-route-id",
      accepted_budget_min_minor: 30_550_000,
      accepted_budget_max_minor: 40_000_000,
      currency: "CNY",
      accepted_trade_offs: ["budget_elasticity"],
    },
    timeline: {
      country: "australia",
      intake: "2027-02",
      milestones: [{ key: "documents", due_date: "2026-09-01" }],
    },
  } as unknown as CurrentDecisionBrief;
  render(<DecisionReceiptTimeline brief={brief} />);
  expect(screen.getByText(/30,550,000–40,000,000 CNY/i)).toBeVisible();
  expect(screen.getByText(/Budget elasticity/i)).toBeVisible();
  expect(screen.getByText(/Documents/i)).toBeVisible();
  expect(screen.queryByText(/hidden-|decision_id|receipt_id|selected_route_id/i)).toBeNull();
});
