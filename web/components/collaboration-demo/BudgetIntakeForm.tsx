"use client";

import type { BudgetDraft, BudgetValidationIssue } from "../../lib/collaboration-demo/budget";
import { validateBudgetDraft } from "../../lib/collaboration-demo/budget";
import { formatCnyRange } from "../../lib/presentation/format";
import { usePresentation } from "../../lib/presentation/context";

export function BudgetIntakeForm({
  draft,
  expectedCaseRevision,
  validation,
  onDraftChange,
  onSubmit,
}: {
  draft: BudgetDraft;
  expectedCaseRevision: number;
  validation: BudgetValidationIssue | null;
  onDraftChange: (draft: BudgetDraft) => void;
  onSubmit: () => void;
}) {
  const { locale, copy } = usePresentation();
  const preview = validateBudgetDraft(draft, expectedCaseRevision);
  const issueText = validation && !preview.ok
    ? copy(
      validation.code === "required"
        ? "budgetValidationRequired"
        : validation.code === "whole_yuan_positive"
          ? "budgetValidationWholePositive"
          : validation.code === "safe_integer"
            ? "budgetValidationSafeInteger"
            : validation.code === "preferred_exceeds_ceiling"
              ? "budgetValidationOrder"
              : "budgetValidationRevision",
    )
    : null;

  return (
    <section className="collaboration-action budget-intake-form" aria-labelledby="parent-action-title">
      <h3 id="parent-action-title">{copy("budgetIntakeTitle")}</h3>
      <p>{copy("budgetFormBody")}</p>
      <form onSubmit={(event) => { event.preventDefault(); onSubmit(); }} noValidate>
        <div className="budget-input-grid">
          <label htmlFor="preferred-budget">
            <span>{copy("preferredBudgetLabel")}</span>
            <input
              id="preferred-budget"
              name="preferred-budget"
              data-budget-input="preferred"
              type="text"
              inputMode="numeric"
              autoComplete="off"
              value={draft.preferredYuan}
              aria-invalid={validation?.field === "preferred"}
              onChange={(event) => onDraftChange({ ...draft, preferredYuan: event.target.value })}
            />
          </label>
          <label htmlFor="hard-ceiling-budget">
            <span>{copy("hardCeilingBudgetLabel")}</span>
            <input
              id="hard-ceiling-budget"
              name="hard-ceiling-budget"
              data-budget-input="hard-ceiling"
              type="text"
              inputMode="numeric"
              autoComplete="off"
              value={draft.hardCeilingYuan}
              aria-invalid={validation?.field === "hard_ceiling"}
              onChange={(event) => onDraftChange({ ...draft, hardCeilingYuan: event.target.value })}
            />
          </label>
        </div>
        <p className="budget-currency-note">{copy("budgetCurrencyLabel")}</p>
        <div className="budget-example-row" aria-label={copy("budgetExamplesLabel")}>
          <span>{copy("budgetExamplesLabel")}</span>
          <button type="button" onClick={() => onDraftChange({ preferredYuan: "300000", hardCeilingYuan: "400000" })}>{copy("budgetExampleNormal")}</button>
          <button type="button" onClick={() => onDraftChange({ preferredYuan: "100000", hardCeilingYuan: "120000" })}>{copy("budgetExampleTight")}</button>
        </div>
        {preview.ok ? (
          <dl className="budget-summary" aria-label={copy("budgetSummaryLabel")}>
            <div><dt>{copy("budgetSummaryLabel")}</dt><dd>{formatCnyRange(locale, preview.intent.value.preferred_minor, preview.intent.value.hard_ceiling_minor, "CNY")}</dd></div>
            <div><dt>{copy("budgetElasticityLabel")}</dt><dd>10%</dd></div>
          </dl>
        ) : null}
        {issueText ? <p className="form-error" role="alert">{issueText}</p> : null}
        <button className="primary-action workspace-primary-action" data-primary-action="true" type="submit">{copy("submitBudgetDetailsAction")}</button>
      </form>
    </section>
  );
}
