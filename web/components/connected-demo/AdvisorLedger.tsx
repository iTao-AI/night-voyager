"use client";

import { useState } from "react";

import type { AdvisorLedger as Ledger } from "../../lib/connected-demo/contracts";
import type { ConfirmedFactAdvisor } from "../../lib/collaboration-demo/contracts";
import { presentRouteOutcome, presentRouteReason } from "../../lib/connected-demo/presentation";
import { EvidenceDisclosure } from "./EvidenceDisclosure";
import { TaskProgress } from "./TaskProgress";
import { CurrentConfirmedFacts } from "./CurrentConfirmedFacts";

function actionLabel(phase: Ledger["phase"]): string {
  if (phase === "task-ready") return "Create planning task";
  if (phase === "review-required") return "Approve Australia for family review";
  if (phase === "family-review" || phase === "plan-ready") return "Continue as family";
  return "Task in progress";
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
  const routes = ledger.routes;
  const [selectedCountry, setSelectedCountry] = useState<string>(String(routes[0]?.country ?? ""));
  const selectedRoute = routes.find((route) => route.country === selectedCountry) ?? routes[0];
  const disabled = busy || ledger.phase === "active-task";
  return (
    <section className="advisor-ledger" aria-labelledby="advisor-ledger-title">
      <div className="section-heading">
        <p className="overline">Advisor Ledger × Global Journey</p>
        <h1 id="advisor-ledger-title">Advisor Ledger</h1>
        <p>Current lifecycle stage: <strong>{ledger.phase}</strong>. Authority comes from the backend projection.</p>
        <p>Case revision {ledger.case_revision}</p>
      </div>
      <CurrentConfirmedFacts facts={confirmedFacts} caseRevision={ledger.case_revision} />
      {routes.length ? (
        <div className="table-wrap">
          <table aria-label="Route evidence comparison">
            <thead><tr><th>Route</th><th>Outcome</th><th>Reason</th><th>Eligibility</th></tr></thead>
            <tbody>
              {routes.map((route, index) => {
                const country = String(route.country);
                const blocked = route.eligible === false || route.outcome === "blocked";
                return (
                  <tr key={`${country}-${index}`}>
                    <th scope="row">{country}</th>
                    <td>{presentRouteOutcome(route.outcome)}</td>
                    <td>{presentRouteReason(route.reason_code)}</td>
                    <td><span className={`status ${blocked ? "danger" : "trust"}`}>{blocked ? "Not eligible" : "Eligible"}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
      {routes.length && selectedRoute ? (
        <fieldset className="country-switcher">
          <legend>Compare country routes</legend>
          <div className="switcher-row">
            {routes.map((route) => {
              const country = String(route.country);
              return <button key={country} type="button" aria-pressed={country === selectedRoute.country} onClick={() => setSelectedCountry(country)}>{country[0]?.toUpperCase()}{country.slice(1)}</button>;
            })}
          </div>
          <dl className="mobile-dimensions">
            <div><dt>Outcome</dt><dd>{presentRouteOutcome(selectedRoute.outcome)}</dd></div>
            <div><dt>Eligibility</dt><dd>{selectedRoute.eligible ? "Eligible for review" : "Not eligible"}</dd></div>
            <div><dt>Reason</dt><dd>{presentRouteReason(selectedRoute.reason_code)}</dd></div>
            <div><dt>Required claims</dt><dd>{selectedRoute.required_claims.join(", ") || "None projected"}</dd></div>
            <div><dt>Known gaps</dt><dd>{selectedRoute.known_gaps.join(", ") || "No projected gaps"}</dd></div>
          </dl>
        </fieldset>
      ) : null}
      <EvidenceDisclosure evidence={ledger.evidence ?? []} />
      <TaskProgress ledger={ledger} />
      <div className="current-stage">
        <div><h2>{actionLabel(ledger.phase)}</h2><p>One server-authorized primary action is available for this phase.</p></div>
        <button className="primary-action" type="button" disabled={disabled} onClick={onPrimaryAction}>{actionLabel(ledger.phase)}</button>
      </div>
    </section>
  );
}
