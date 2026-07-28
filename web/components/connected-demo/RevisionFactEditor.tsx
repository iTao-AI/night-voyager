"use client";

import type { ConfirmedFactAdvisor, ConfirmedFactParticipant } from "../../lib/collaboration-demo/contracts";
import type { CurrentFactsProjection } from "../../lib/connected-demo/use-connected-demo";
import { presentCode } from "../../lib/presentation/codes";
import { usePresentation } from "../../lib/presentation/context";

const BASELINE = ["australia", "japan", "malaysia"] as const;
const REVISED = ["australia", "japan"] as const;

function preferredCountries(
  facts: readonly (ConfirmedFactAdvisor | ConfirmedFactParticipant)[],
): readonly string[] | null {
  const matches = facts.filter((fact) => fact.fact_key === "student.preferred_countries");
  if (matches.length !== 1 || !Array.isArray(matches[0].value)) return null;
  return matches[0].value;
}

export function RevisionFactEditor({
  currentFacts,
  expectedCaseRevision,
  onSubmit,
  busy = false,
}: {
  currentFacts: CurrentFactsProjection | null;
  expectedCaseRevision: number;
  onSubmit: () => void;
  busy?: boolean;
}) {
  const { locale, copy } = usePresentation();
  const current = currentFacts ? preferredCountries(currentFacts.facts) : null;
  const valid = currentFacts?.caseRevision === expectedCaseRevision
    && current?.length === BASELINE.length
    && current.every((country, index) => country === BASELINE[index])
    && new Set(current).size === current.length;
  const countries = (values: readonly string[]) =>
    values.map((country) => presentCode(locale, "country", country)).join(locale === "zh-CN" ? "、" : ", ");

  return (
    <fieldset className="revision-fact-editor" disabled={busy}>
      <legend>{copy("revisionFactEditorLegend")}</legend>
      <p>{copy("revisionFactEditorBody")}</p>
      {valid && current ? (
        <dl>
          <div><dt>{copy("revisionCurrentCountries")}</dt><dd>{countries(current)}</dd></div>
          <div><dt>{copy("revisionTargetCountries")}</dt><dd>{countries(REVISED)}</dd></div>
        </dl>
      ) : null}
      <button
        className="primary-action"
        type="button"
        disabled={!valid || busy}
        onClick={onSubmit}
      >
        {copy("submitRevisionProposalAction")}
      </button>
      {!valid ? <p className="disabled-reason">{copy("revisionEditorUnavailable")}</p> : null}
    </fieldset>
  );
}
