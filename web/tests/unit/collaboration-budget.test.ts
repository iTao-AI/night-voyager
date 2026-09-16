import { expect, it } from "vitest";

import {
  DEFAULT_BUDGET_DRAFT,
  TIGHT_BUDGET_DRAFT,
  createBudgetIntent,
  defaultBudgetIntent,
  isBudgetIntent,
  messageRequestForBudget,
  proposalRequestForBudget,
  renderBudgetMessage,
  validateBudgetDraft,
} from "../../lib/collaboration-demo/budget";

it("builds an immutable default intent and deterministic mutation bodies", () => {
  const result = validateBudgetDraft(DEFAULT_BUDGET_DRAFT, 1);
  expect(result.ok).toBe(true);
  if (!result.ok) return;

  expect(result.intent).toEqual({
    schema_version: 1,
    expected_case_revision: 1,
    value: {
      schema_version: 1,
      currency: "CNY",
      period: "program_total",
      preferred_minor: 30_000_000,
      hard_ceiling_minor: 40_000_000,
      elasticity_bps: 1_000,
      refused: false,
    },
  });
  expect(Object.isFrozen(result.intent)).toBe(true);
  expect(Object.isFrozen(result.intent.value)).toBe(true);
  expect(renderBudgetMessage(result.intent)).toBe("Our confirmed program budget is 300,000 to 400,000 CNY.");
  expect(messageRequestForBudget(result.intent)).toEqual({ schema_version: 1, body: "Our confirmed program budget is 300,000 to 400,000 CNY." });
  expect(proposalRequestForBudget(result.intent).case_revision).toBe(1);
  expect(isBudgetIntent(result.intent)).toBe(true);
});

it("accepts a tight whole-yuan range without changing the fixed elasticity", () => {
  const intent = createBudgetIntent(TIGHT_BUDGET_DRAFT, 1);
  expect(intent.value.preferred_minor).toBe(10_000_000);
  expect(intent.value.hard_ceiling_minor).toBe(12_000_000);
  expect(intent.value.elasticity_bps).toBe(1_000);
  expect(renderBudgetMessage(intent)).toBe("Our confirmed program budget is 100,000 to 120,000 CNY.");
  expect(defaultBudgetIntent(2).expected_case_revision).toBe(2);
});

it.each([
  [{ preferredYuan: "", hardCeilingYuan: "400000" }, "required"],
  [{ preferredYuan: "-1", hardCeilingYuan: "400000" }, "whole_yuan_positive"],
  [{ preferredYuan: "1.5", hardCeilingYuan: "400000" }, "whole_yuan_positive"],
  [{ preferredYuan: "1e3", hardCeilingYuan: "400000" }, "whole_yuan_positive"],
  [{ preferredYuan: "NaN", hardCeilingYuan: "400000" }, "whole_yuan_positive"],
  [{ preferredYuan: "90071992547410", hardCeilingYuan: "90071992547410" }, "safe_integer"],
  [{ preferredYuan: "400001", hardCeilingYuan: "400000" }, "preferred_exceeds_ceiling"],
] as const)("rejects unsafe or invalid budget draft %j", (draft, code) => {
  const result = validateBudgetDraft(draft, 1);
  expect(result).toEqual({ ok: false, error: expect.objectContaining({ code }) });
});

it("does not manufacture an intent for an invalid draft", () => {
  const result = validateBudgetDraft({ preferredYuan: "0", hardCeilingYuan: "0" }, 1);
  expect(result.ok).toBe(false);
  expect(() => createBudgetIntent({ preferredYuan: "2.5", hardCeilingYuan: "3" }, 1)).toThrow("invalid budget intent");
});

it.each([
  { schema_version: 1, expected_case_revision: 1, value: { schema_version: 1, currency: "CNY", period: "program_total", preferred_minor: 1, hard_ceiling_minor: 2, elasticity_bps: 1000, refused: false } },
  { schema_version: 1, expected_case_revision: 1, value: { schema_version: 1, currency: "CNY", period: "program_total", preferred_minor: null, hard_ceiling_minor: null, elasticity_bps: 1000, refused: true } },
] as const)("rejects a stored intent that is not a positive whole-yuan range: %j", (intent) => {
  expect(isBudgetIntent(intent)).toBe(false);
});
