"use client";

import { useState } from "react";

import type {
  Country,
  PlanningRevisionComparison as Comparison,
  PlanningRevisionCountryComparison,
} from "../../lib/connected-demo/contracts";
import {
  presentCode,
  presentComparisonDelta,
  presentRouteOutcome,
  presentRouteReason,
} from "../../lib/presentation/codes";
import { usePresentation } from "../../lib/presentation/context";
import { formatCnyRange } from "../../lib/presentation/format";

function routeResult(
  locale: "zh-CN" | "en",
  row: PlanningRevisionCountryComparison,
  side: "previous" | "current",
  removed: string,
  added: string,
): string {
  const outcome = side === "previous" ? row.previous_outcome : row.current_outcome;
  const reason = side === "previous" ? row.previous_reason_code : row.current_reason_code;
  if (outcome === null && reason === null) {
    return side === "current" && row.delta === "removed" ? removed : added;
  }
  return `${presentRouteOutcome(locale, outcome)} — ${presentRouteReason(locale, reason)}`;
}

export function PlanningRevisionComparison({ comparison }: { comparison: Comparison }) {
  const { locale, copy } = usePresentation();
  const [selectedCountry, setSelectedCountry] = useState<Country>(
    comparison.countries[0]?.country ?? "australia",
  );
  const selected = comparison.countries.find((row) => row.country === selectedCountry)
    ?? comparison.countries[0];
  const changed = comparison.changed_fact;
  const presentFactValue = (value: Comparison["changed_fact"]["previous_value"]): string => {
    if (Array.isArray(value)) {
      return value.map((country) => presentCode(locale, "country", country)).join(locale === "zh-CN" ? "、" : ", ");
    }
    if (value.refused || value.preferred_minor === null || value.hard_ceiling_minor === null) {
      return copy("statusUnavailable");
    }
    return formatCnyRange(locale, value.preferred_minor, value.hard_ceiling_minor, value.currency);
  };
  const currentText = (row: PlanningRevisionCountryComparison) =>
    routeResult(locale, row, "current", copy("removedFromRevisedPlan"), copy("notPresentInPreviousPlan"));
  const previousText = (row: PlanningRevisionCountryComparison) =>
    routeResult(locale, row, "previous", copy("removedFromRevisedPlan"), copy("notPresentInPreviousPlan"));

  return (
    <section className="revision-comparison" aria-labelledby="revision-comparison-title">
      <header className="section-heading">
        <p className="overline">{copy("revisionComparisonOverline")}</p>
        <h2 id="revision-comparison-title">{copy("revisionComparisonTitle")}</h2>
      </header>
      <section className="changed-fact-summary" aria-labelledby="changed-fact-title">
        <h3 id="changed-fact-title">{copy("changedFactTitle")}</h3>
        <p>{copy(changed.fact_key === "student.preferred_countries" ? "preferredCountriesChanged" : "familyBudgetChanged")}</p>
        <dl>
          <div><dt>{copy("previousValueLabel")}</dt><dd>{presentFactValue(changed.previous_value)}</dd></div>
          <div><dt>{copy("revisedValueLabel")}</dt><dd>{presentFactValue(changed.current_value)}</dd></div>
        </dl>
      </section>
      <div className="revision-plan-labels" aria-label={copy("revisionComparisonTitle")}>
        <div className="revision-plan-history">
          <strong>{copy("previousPlanLabel")}</strong>
          <span>{copy("historyOnlyLabel")} · {copy("caseRevisionLabel")} {comparison.previous_revision}</span>
        </div>
        <div className="revision-plan-current">
          <strong>{copy("currentRevisedPlanLabel")}</strong>
          <span>{copy("currentPlanLabel")} · {copy("caseRevisionLabel")} {comparison.current_revision}</span>
        </div>
      </div>
      <div className="revision-comparison-table">
        <table aria-label={copy("revisionComparisonTitle")}>
          <thead>
            <tr>
              <th>{copy("comparisonCountryColumn")}</th>
              <th>{copy("comparisonPreviousColumn")}</th>
              <th>{copy("comparisonCurrentColumn")}</th>
              <th>{copy("comparisonChangeColumn")}</th>
            </tr>
          </thead>
          <tbody>
            {comparison.countries.map((row) => (
              <tr key={row.country} className={row.delta === "removed" ? "revision-route-removed" : undefined}>
                <th scope="row">{presentCode(locale, "country", row.country)}</th>
                <td>{previousText(row)}</td>
                <td>{currentText(row)}</td>
                <td>{presentComparisonDelta(locale, row.delta)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <fieldset className="revision-country-switcher">
        <legend>{copy("compareRevisionCountries")}</legend>
        <div className="switcher-row">
          {comparison.countries.map((row) => (
            <button
              key={row.country}
              type="button"
              aria-pressed={row.country === selected?.country}
              onClick={() => setSelectedCountry(row.country)}
            >
              {presentCode(locale, "country", row.country)}
            </button>
          ))}
        </div>
        {selected ? (
          <article className={`revision-country-card ${selected.delta === "removed" ? "revision-route-removed" : ""}`}>
            <h3>{presentCode(locale, "country", selected.country)}</h3>
            <dl>
              <div><dt>{copy("comparisonPreviousColumn")}</dt><dd>{previousText(selected)}</dd></div>
              <div><dt>{copy("comparisonCurrentColumn")}</dt><dd>{currentText(selected)}</dd></div>
              <div><dt>{copy("comparisonChangeColumn")}</dt><dd>{presentComparisonDelta(locale, selected.delta)}</dd></div>
            </dl>
          </article>
        ) : null}
      </fieldset>
    </section>
  );
}
