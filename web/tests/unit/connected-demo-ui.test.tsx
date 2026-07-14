import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";

import { AdvisorLedger } from "../../components/connected-demo/AdvisorLedger";
import { DecisionReceiptTimeline } from "../../components/connected-demo/DecisionReceiptTimeline";
import { FamilyDecisionBrief } from "../../components/connected-demo/FamilyDecisionBrief";
import { RecoveryNotice } from "../../components/connected-demo/RecoveryNotice";
import type { AdvisorLedger as Ledger, CurrentDecisionBrief } from "../../lib/connected-demo/contracts";
import { brief as briefFixture, ledger as ledgerFixture } from "./connected-demo-test-data";

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
  const ledger = ledgerFixture("review-required");
  const { container } = render(<AdvisorLedger ledger={ledger} onPrimaryAction={() => undefined} />);
  expect(screen.queryByRole("button", { name: /Choose (Australia|Japan|Malaysia)/i })).toBeNull();
  expect(screen.getAllByText("Not eligible").length).toBeGreaterThanOrEqual(2);
  expect(screen.getAllByText("Recommended with budget condition").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Conditional alternative").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Blocked").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Cost and FX evidence are within the approved boundary").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Higher-risk synthetic alternative").length).toBeGreaterThan(0);
  fireEvent.click(screen.getByRole("button", { name: "Malaysia" }));
  expect(screen.getByText("malaysia_gap")).toBeVisible();
  expect(screen.getAllByText("Program-fit evidence is missing").length).toBeGreaterThan(0);
  expect(screen.getByRole("button", { name: "Malaysia" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByText(/Synthetic publisher/i)).toBeVisible();
  expect(container).not.toHaveTextContent(/recommended_with_condition|synthetic_high_risk_alternative|direct_program_fit_evidence_absent/);
});

it("announces public task status outside the collapsed technical trail", () => {
  render(<AdvisorLedger ledger={ledgerFixture("active-task")} busy onPrimaryAction={() => undefined} />);
  const status = screen.getByRole("status");
  expect(status).toBeVisible();
  expect(status).toHaveTextContent(/Status: preparing/i);
  expect(screen.getByText("Task trail").closest("details")).not.toHaveAttribute("open");
});

it("renders only server-derived family constraints", () => {
  const brief = briefFixture("family-review");
  const { container } = render(<FamilyDecisionBrief brief={brief} confirmed={false} onConfirm={() => undefined} onSubmit={() => undefined} />);
  expect(screen.getByText("305,500 CNY")).toBeVisible();
  expect(screen.getByText("400,000 CNY")).toBeVisible();
  expect(screen.getAllByText("Budget flexibility").length).toBeGreaterThan(0);
  expect(screen.getByRole("button", { name: /Confirm Australia route/i })).toBeDisabled();
  expect(container).not.toHaveTextContent(/budget_elasticity|30,550,000|40,000,000/);
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
  expect(screen.getByText("305,500–400,000 CNY")).toBeVisible();
  expect(screen.getByText("Budget flexibility")).toBeVisible();
  expect(screen.getByText(/Documents/i)).toBeVisible();
  expect(screen.queryByText(/hidden-|decision_id|receipt_id|selected_route_id|budget_elasticity|30,550,000|40,000,000/i)).toBeNull();
});
