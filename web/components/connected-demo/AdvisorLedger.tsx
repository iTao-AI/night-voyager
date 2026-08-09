"use client";

import Link from "next/link";
import { useState } from "react";

import type { AdvisorLedger as Ledger } from "../../lib/connected-demo/contracts";
import type { ConfirmedFactAdvisor } from "../../lib/collaboration-demo/contracts";
import { usePresentation } from "../../lib/presentation/context";
import { presentCode, presentRouteOutcome, presentRouteReason } from "../../lib/presentation/codes";
import type { PresentationCopyKey } from "../../lib/presentation/catalog";
import { TaskProgress } from "./TaskProgress";
import { CurrentConfirmedFacts } from "./CurrentConfirmedFacts";
import { PlanningRevisionComparison } from "./PlanningRevisionComparison";

function actionKey(phase: Ledger["phase"]): PresentationCopyKey | null {
  if (phase === "task_ready" || phase === "replan_required") return "advisorCreateTask";
  if (phase === "review_required") return "approveCurrentPlanAction";
  if (phase === "revision_fact_pending") return "confirmRevisionFactAction";
  if (phase === "revision_review_required") return "approveRevisedPlanAction";
  if (phase === "family_review" || phase === "plan_ready") return "advisorContinueFamily";
  return null;
}

export function AdvisorLedger({
  ledger,
  confirmedFacts = null,
  onPrimaryAction,
  onSecondaryAction,
  busy = false,
}: {
  ledger: Ledger;
  confirmedFacts?: readonly ConfirmedFactAdvisor[] | null;
  onPrimaryAction: () => void;
  onSecondaryAction?: () => void;
  busy?: boolean;
}) {
  const { locale, copy } = usePresentation();
  const routes = ledger.routes;
  const [selectedCountry, setSelectedCountry] = useState<string>(String(routes[0]?.country ?? ""));
  const selectedRoute = routes.find((route) => route.country === selectedCountry) ?? routes[0];
  const primaryActionKey = actionKey(ledger.phase);
  const primaryAction = primaryActionKey ? copy(
    ledger.phase === "replan_required" ? "createRevisedTaskAction" : primaryActionKey,
  ) : null;
  const presentClaims = (values: readonly string[], kind: "evidenceClaim" | "knownGap", emptyKey: PresentationCopyKey) =>
    values.length ? values.map((value, index) => <span key={`${kind}-${value}-${index}`}>{presentCode(locale, kind, value)}{index < values.length - 1 ? ", " : ""}</span>) : copy(emptyKey);

  return (
    <section className="advisor-ledger" aria-labelledby="advisor-ledger-title">
      <header className="section-heading outcome-heading">
        <p className="overline">{copy("advisorLedgerOverline")}</p>
        <h3 id="advisor-ledger-title">{copy("advisorStageTitle")}</h3>
        <p className="role-status">{copy("activeRoleLabel")}: {presentCode(locale, "role", "advisor")}</p>
        <p className="stage-outcome"><strong>{presentCode(locale, "demoPhase", ledger.phase)}</strong></p>
        <p>{copy("advisorRoleAuthority")}</p>
        <p><span>{copy("caseRevisionLabel")} {ledger.case_revision}</span>{copy("caseRevisionLabel") === copy("caseRevisionTechnicalLabel") ? null : <span className="technical-label"> {copy("caseRevisionTechnicalLabel")} {ledger.case_revision}</span>}</p>
      </header>

      {ledger.comparison ? <PlanningRevisionComparison comparison={ledger.comparison} /> : null}

      <div className="current-stage">
        <div>
          <h2>
            {ledger.phase === "revision_blocked"
              ? copy("revisionBlockedTitle")
              : ledger.phase === "terminal_task_failure"
                ? copy("terminalFailureTitle")
                : primaryAction ?? presentCode(locale, "demoPhase", ledger.phase)}
          </h2>
          <p>
            {ledger.phase === "revision_blocked"
              ? copy("revisionBlockedBody")
              : primaryAction
                ? copy("advisorActionExplanation")
                : copy("noBusinessAction")}
          </p>
        </div>
        {primaryAction ? (
          <div className="action-row">
            <button className="primary-action" data-primary-action="true" type="button" disabled={busy} onClick={onPrimaryAction}>{primaryAction}</button>
            {ledger.phase === "review_required" && onSecondaryAction ? (
              <button className="secondary-action" type="button" disabled={busy} onClick={onSecondaryAction}>
                {copy("requestRevisionAction")}
              </button>
            ) : null}
          </div>
        ) : ["revision_blocked", "terminal_task_failure"].includes(ledger.phase) ? (
          <Link className="secondary-action" href="/">{copy("safeNavigationExit")}</Link>
        ) : null}
      </div>
      {busy ? <p aria-live="polite">{copy("busyStatus")}</p> : null}

      {!ledger.comparison && routes.length ? (
        <>
          <div className="table-wrap">
            <table aria-label={copy("routeComparisonLabel")}>
              <thead><tr><th>{copy("routeColumn")}</th><th>{copy("outcomeColumn")}</th><th>{copy("reasonColumn")}</th><th>{copy("eligibilityColumn")}</th><th>{copy("requiredClaims")}</th><th>{copy("knownGaps")}</th></tr></thead>
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
                      <td>{presentClaims(route.required_claims, "evidenceClaim", "noRequiredClaims")}</td>
                      <td>{presentClaims(route.known_gaps, "knownGap", "noKnownGaps")}</td>
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
      ) : !ledger.comparison ? <p className="empty-state">{copy("noRoutes")}</p> : null}

      <CurrentConfirmedFacts facts={confirmedFacts} caseRevision={ledger.case_revision} />
      <TaskProgress ledger={ledger} />
    </section>
  );
}
