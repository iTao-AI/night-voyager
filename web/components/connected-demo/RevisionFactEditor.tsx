"use client";

import { useState } from "react";
import { isBudgetValue, type BudgetDraft } from "../../lib/collaboration-demo/budget";
import type { Country } from "../../lib/connected-demo/contracts";
import type { CurrentFactsProjection } from "../../lib/connected-demo/use-connected-demo";
import { isRevisionCountries, revisionFact, REVISION_COUNTRIES, validateBudgetRevision, validateRevisionIntent, type RevisionFactKey, type RevisionIntent } from "../../lib/connected-demo/revision";
import { presentCode } from "../../lib/presentation/codes";
import { formatCnyRange } from "../../lib/presentation/format";
import { usePresentation } from "../../lib/presentation/context";

interface EditorProps {
  expectedCaseId: string;
  currentFacts: CurrentFactsProjection | null;
  expectedCaseRevision: number;
  activeRole?: "student" | "parent";
  onPrepareFact?: (factKey: RevisionFactKey) => void;
  onSubmit: (intent: RevisionIntent) => void;
  submittedIntent?: RevisionIntent | null;
  busy?: boolean;
}

export function RevisionFactEditor(props: EditorProps) {
  return <RevisionForm key={`${props.activeRole}:${props.expectedCaseId}:${props.currentFacts?.caseId}:${props.currentFacts?.caseRevision}:${props.expectedCaseRevision}:${JSON.stringify(props.currentFacts?.facts)}:${JSON.stringify(props.submittedIntent)}`} {...props} />;
}

function RevisionForm({ expectedCaseId, currentFacts, expectedCaseRevision, activeRole = "student", onPrepareFact, onSubmit, submittedIntent = null, busy = false }: EditorProps) {
  const { locale, copy } = usePresentation();
  const projectionCurrent = currentFacts?.caseId === expectedCaseId && currentFacts.caseRevision === expectedCaseRevision;
  const currentCountries = projectionCurrent ? revisionFact(currentFacts.facts, "student.preferred_countries")?.value : null;
  const currentBudget = projectionCurrent ? revisionFact(currentFacts.facts, "family.budget")?.value : null;
  const available: RevisionFactKey[] = [];
  if (isRevisionCountries(currentCountries)) available.push("student.preferred_countries");
  if (isBudgetValue(currentBudget) && !currentBudget.refused) available.push("family.budget");
  const roleFact = activeRole === "parent" ? "family.budget" : "student.preferred_countries";
  const restored = submittedIntent?.expectedCaseRevision === expectedCaseRevision ? submittedIntent : null;
  const savedUnavailable = submittedIntent !== null && (!restored || !available.includes(submittedIntent.factKey));
  // Role preparation can deliberately open the other editor while keeping its submitted replay data.
  const initialFact = restored?.factKey === roleFact ? restored.factKey : available.includes(roleFact) ? roleFact : available[0] ?? null;
  const [factKey, setFactKey] = useState<RevisionFactKey | null>(initialFact);
  const [selectedCountries, setSelectedCountries] = useState<readonly Country[]>(restored?.factKey === "student.preferred_countries" ? restored.value : isRevisionCountries(currentCountries) ? currentCountries : []);
  const initialBudget = restored?.factKey === "family.budget" ? restored.value : isBudgetValue(currentBudget) ? currentBudget : null;
  const [draft, setDraft] = useState<BudgetDraft>({ preferredYuan: initialBudget?.preferred_minor ? String(initialBudget.preferred_minor / 100) : "", hardCeilingYuan: initialBudget?.hard_ceiling_minor ? String(initialBudget.hard_ceiling_minor / 100) : "" });
  const countries = (values: readonly string[]) => values.map((country) => presentCode(locale, "country", country)).join(locale === "zh-CN" ? "、" : ", ");
  const savedValue = submittedIntent?.factKey === "family.budget"
    ? formatCnyRange(locale, submittedIntent.value.preferred_minor, submittedIntent.value.hard_ceiling_minor, "CNY")
    : submittedIntent ? countries(submittedIntent.value) : "";
  const savedSummary = submittedIntent ? <p aria-label={copy("revisionSavedIntentLabel")}>{copy("revisionSavedIntentLabel")}: {copy(submittedIntent.factKey === "family.budget" ? "revisionBudgetOption" : "revisionCountriesOption")} — {savedValue}</p> : null;
  const blockingReason = !currentFacts ? "revisionProjectionUnavailable" : !projectionCurrent ? "revisionProjectionStale" : savedUnavailable ? "revisionSavedIntentUnavailable" : !available.length ? "revisionNoEditableFacts" : null;

  if (blockingReason || !factKey) return (
    <fieldset className="revision-fact-editor" disabled={busy}>
      <legend>{copy("revisionFactEditorLegend")}</legend>
      {savedSummary}
      <p className="disabled-reason" aria-live="polite">{copy(blockingReason ?? "revisionNoEditableFacts")}</p>
    </fieldset>
  );

  const requiresRoleHandoff = activeRole !== (factKey === "family.budget" ? "parent" : "student");
  const validation = factKey === "family.budget"
    ? validateBudgetRevision(draft, expectedCaseRevision, currentFacts)
    : validateRevisionIntent({ expectedCaseRevision, factKey, value: selectedCountries }, currentFacts);
  const currentValue = factKey === "student.preferred_countries"
    ? isRevisionCountries(currentCountries) ? countries(currentCountries) : copy("statusUnavailable")
    : isBudgetValue(currentBudget) ? formatCnyRange(locale, currentBudget.preferred_minor, currentBudget.hard_ceiling_minor, "CNY") : copy("statusUnavailable");
  const proposedValue = factKey === "student.preferred_countries" ? countries(selectedCountries)
    : validation.ok && validation.intent.factKey === "family.budget" ? formatCnyRange(locale, validation.intent.value.preferred_minor, validation.intent.value.hard_ceiling_minor, "CNY") : `${draft.preferredYuan}–${draft.hardCeilingYuan} CNY`;

  return (
    <fieldset className="revision-fact-editor" disabled={busy}>
      <legend>{copy("revisionFactEditorLegend")}</legend>
      <p>{copy("revisionFactEditorBody")}</p>
      {savedSummary}
      {!available.includes("student.preferred_countries") ? <p>{copy("revisionCountriesUnconfirmed")}</p> : null}
      <label className="revision-field" htmlFor="revision-fact-key"><span>{copy("revisionFactLabel")}</span>
        <select id="revision-fact-key" value={factKey} onChange={(event) => { const next = event.target.value as RevisionFactKey; if (available.includes(next)) setFactKey(next); }}>
          {available.map(key => <option key={key} value={key}>{copy(key === "family.budget" ? "revisionBudgetOption" : "revisionCountriesOption")}</option>)}
        </select>
      </label>
      {requiresRoleHandoff ? <p>{copy("revisionRoleHandoffBody")}</p> : <>
        <dl><div><dt>{copy("revisionCurrentCountries")}</dt><dd>{currentValue}</dd></div><div><dt>{copy("revisionTargetCountries")}</dt><dd>{proposedValue || copy("statusUnavailable")}</dd></div></dl>
        {factKey === "student.preferred_countries" ? (
          <fieldset className="revision-country-options"><legend>{copy("revisionCountriesOption")}</legend>
            {REVISION_COUNTRIES.map((country) => <label key={country}><input type="checkbox" checked={selectedCountries.includes(country)} onChange={(event) => setSelectedCountries(event.target.checked ? [...selectedCountries, country].sort() : selectedCountries.filter((item) => item !== country))} />{presentCode(locale, "country", country)}</label>)}
          </fieldset>
        ) : <div className="budget-input-grid">
          <label htmlFor="revision-preferred-budget"><span>{copy("preferredBudgetLabel")}</span><input id="revision-preferred-budget" type="text" inputMode="numeric" autoComplete="off" value={draft.preferredYuan} onChange={(event) => setDraft({ ...draft, preferredYuan: event.target.value })} /></label>
          <label htmlFor="revision-hard-ceiling-budget"><span>{copy("hardCeilingBudgetLabel")}</span><input id="revision-hard-ceiling-budget" type="text" inputMode="numeric" autoComplete="off" value={draft.hardCeilingYuan} onChange={(event) => setDraft({ ...draft, hardCeilingYuan: event.target.value })} /></label>
          <p>{copy("budgetCurrencyLabel")}</p>
        </div>}
        <button className="primary-action" data-primary-action="true" type="button" disabled={!validation.ok || busy} onClick={() => { if (validation.ok) onSubmit(validation.intent); }}>{copy(factKey === "family.budget" ? "submitParentBudgetRevisionAction" : "submitRevisionProposalAction")}</button>
        {!validation.ok ? <p className="disabled-reason" aria-live="polite">{copy(validation.code === "unchanged" ? "revisionUnchanged" : validation.code === "invalid" ? "revisionInvalid" : "revisionEditorUnavailable")}</p> : null}
      </>}
      {requiresRoleHandoff ? <button className="primary-action" data-primary-action="true" type="button" disabled={busy || !onPrepareFact} onClick={() => onPrepareFact?.(factKey)}>{copy(factKey === "family.budget" ? "revisionPrepareParentAction" : "revisionPrepareStudentAction")}</button> : null}
      {busy ? <p aria-live="polite">{copy("busyStatus")}</p> : null}
    </fieldset>
  );
}
