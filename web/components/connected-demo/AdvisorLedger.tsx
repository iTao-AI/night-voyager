"use client";

import { useState } from "react";

import type { AdvisorLedger as Ledger } from "../../lib/connected-demo/contracts";
import type { ConfirmedFactAdvisor } from "../../lib/collaboration-demo/contracts";
import { usePresentation } from "../../lib/presentation/context";
import { presentCode, presentRouteOutcome, presentRouteReason } from "../../lib/presentation/codes";
import type { PresentationCopyKey } from "../../lib/presentation/catalog";
import { EvidenceDisclosure } from "./EvidenceDisclosure";
import { TaskProgress } from "./TaskProgress";
import { CurrentConfirmedFacts } from "./CurrentConfirmedFacts";

function actionKey(phase: Ledger["phase"]): PresentationCopyKey {
  if (phase === "task-ready") return "advisorCreateTask";
  if (phase === "review-required") return "advisorApproveAustralia";
  if (phase === "family-review" || phase === "plan-ready") return "advisorContinueFamily";
  return "advisorTaskInProgress";
}

export function AdvisorLedger({
  ledger,
  confirmedFacts = null,
  onPrimaryAction,
  busy = false,
}: {
  ledger: Ledger;
  confirmedFacts?: readonly ConfirmedFactAdvisor[] | null;
  onPrimaryAction: () => void;
  busy?: boolean;
}) {
  const { locale, copy } = usePresentation();
  const routes = ledger.routes;
  const [selectedCountry, setSelectedCountry] = useState<string>(String(routes[0]?.country ?? ""));
  const selectedRoute = routes.find((route) => route.country === selectedCountry) ?? routes[0];
  const disabled = busy || ledger.phase === "active-task";
  const primaryAction = copy(actionKey(ledger.phase));
  const presentClaims = (values: readonly string[], kind: "evidenceClaim" | "knownGap", emptyKey: PresentationCopyKey) =>
    values.length ? values.map((value) => presentCode(locale, kind, value)).join(", ") : copy(emptyKey);

  return (
    <section className="advisor-ledger" aria-labelledby="advisor-ledger-title">
      <header className="section-heading outcome-heading">
        <p className="overline">Advisor Ledger × Global Journey</p>
        <h1 id="advisor-ledger-title">{copy("advisorStageTitle")}</h1>
        <p className="stage-outcome"><strong>{presentCode(locale, "demoPhase", ledger.phase)}</strong></p>
        <p>{copy("advisorStageAuthority")}</p>
        <p>{copy("caseRevisionLabel")} {ledger.case_revision}</p>
      </header>

      <div className="current-stage">
        <div><h2>{primaryAction}</h2><p>{copy("advisorActionExplanation")}</p></div>
        <button className="primary-action" type="button" disabled={disabled} onClick={onPrimaryAction}>{primaryAction}</button>
      </div>

      {routes.length ? (
        <>
          <div className="table-wrap">
            <table aria-label={copy("routeComparisonLabel")}>
              <thead><tr><th>{copy("routeColumn")}</th><th>{copy("outcomeColumn")}</th><th>{copy("reasonColumn")}</th><th>{copy("eligibilityColumn")}</th></tr></thead>
              <tbody>
                {routes.map((route, index) => {
                  const country = String(route.country);
                  const blocked = route.eligible === false || route.outcome === "blocked";
                  return (
                    <tr key={`${country}-${index}`}>
                      <th scope="row">{presentCode(locale, "country", country)}</th>
                      <td>{presentRouteOutcome(locale, route.outcome)}</td>
                      <td>{presentRouteReason(locale, route.reason_code)}</td>
                      <td><span className={`status ${blocked ? "danger" : "trust"}`}>{copy(blocked ? "notEligibleForReview" : "eligibleForReview")}</span></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {selectedRoute ? (
            <fieldset className="country-switcher">
              <legend>{copy("compareRoutes")}</legend>
              <div className="switcher-row">
                {routes.map((route) => {
                  const country = String(route.country);
                  return <button key={country} type="button" aria-pressed={country === selectedRoute.country} onClick={() => setSelectedCountry(country)}>{presentCode(locale, "country", country)}</button>;
                })}
              </div>
              <dl className="mobile-dimensions">
                <div><dt>{copy("outcomeColumn")}</dt><dd>{presentRouteOutcome(locale, selectedRoute.outcome)}</dd></div>
                <div><dt>{copy("eligibilityColumn")}</dt><dd>{copy(selectedRoute.eligible ? "eligibleForReview" : "notEligibleForReview")}</dd></div>
                <div><dt>{copy("reasonColumn")}</dt><dd>{presentRouteReason(locale, selectedRoute.reason_code)}</dd></div>
                <div><dt>{copy("requiredClaims")}</dt><dd>{presentClaims(selectedRoute.required_claims, "evidenceClaim", "noRequiredClaims")}</dd></div>
                <div><dt>{copy("knownGaps")}</dt><dd>{presentClaims(selectedRoute.known_gaps, "knownGap", "noKnownGaps")}</dd></div>
              </dl>
            </fieldset>
          ) : null}
        </>
      ) : <p className="empty-state">{copy("noRoutes")}</p>}

      <CurrentConfirmedFacts facts={confirmedFacts} caseRevision={ledger.case_revision} />
      <TaskProgress ledger={ledger} />
      <EvidenceDisclosure evidence={ledger.evidence ?? []} />
    </section>
  );
}
