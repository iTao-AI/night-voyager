"use client";

import { useEffect, useRef } from "react";

import { useConnectedDemo } from "../../lib/connected-demo/use-connected-demo";
import type { DemoDisplayState } from "../../lib/connected-demo/reducer";
import { usePresentation } from "../../lib/presentation/context";
import { presentCode } from "../../lib/presentation/codes";
import { PresentationShell } from "../presentation/PresentationShell";
import { AdvisorLedger } from "./AdvisorLedger";
import { DecisionReceiptTimeline } from "./DecisionReceiptTimeline";
import { FamilyDecisionBrief } from "./FamilyDecisionBrief";
import { RecoveryNotice } from "./RecoveryNotice";
import { JourneyConflictNotice } from "../demo-session/JourneyConflictNotice";
import { PlanningSkillInspector } from "../skill-inspector/PlanningSkillInspector";
import type { ConfirmedFactAdvisor } from "../../lib/collaboration-demo/contracts";
import type { AdvisorLedger as Ledger } from "../../lib/connected-demo/contracts";
import { RevisionFactEditor } from "./RevisionFactEditor";

function retainedLedger(state: DemoDisplayState): Ledger | null {
  if ("ledger" in state) return state.ledger;
  if ((state.value === "role_switching" || state.value === "recoverable_error") && state.prior) {
    return retainedLedger(state.prior);
  }
  return null;
}

export function ConnectedDemo() {
  const demo = useConnectedDemo();
  const { locale, copy } = usePresentation();
  const { state } = demo;
  const userTransition = useRef(false);
  const previousState = useRef(state.value);
  const runUserAction = (action: () => Promise<unknown> | void) => {
    userTransition.current = true;
    void action();
  };
  useEffect(() => {
    const busy = ["task_creating", "review_submitting", "decision_submitting", "role_switching"].includes(state.value);
    if (userTransition.current && previousState.current !== state.value && !busy) {
      const heading = document.querySelector<HTMLElement>("#demo-main h1");
      heading?.setAttribute("tabindex", "-1");
      heading?.focus();
      userTransition.current = false;
    }
    previousState.current = state.value;
  }, [state.value]);
  const inspectorVisible = ["advisor_ready", "task_creating", "task_streaming", "advisor_review", "review_submitting", "terminal_task_failure"].includes(state.value);
  const confirmedFactsFor = (caseId: string, caseRevision: number): readonly ConfirmedFactAdvisor[] | null =>
    demo.currentFacts?.caseId === caseId && demo.currentFacts.caseRevision === caseRevision
      ? demo.currentFacts.facts.filter(
          (fact): fact is ConfirmedFactAdvisor => "confirmed_fact_id" in fact,
        )
      : null;
  const ledger = retainedLedger(state);
  const busy = ["task_creating", "task_streaming", "review_submitting", "role_switching", "recoverable_error"].includes(state.value);
  const primaryFor = (current: Ledger) => {
    switch (current.phase) {
      case "task_ready": return () => demo.createTask();
      case "review_required": return () => demo.approve();
      case "revision_fact_pending": return () => demo.confirmPreferredCountries();
      case "replan_required": return () => demo.createRevisionTask();
      case "revision_review_required": return () => demo.approveRevision();
      default: return () => undefined;
    }
  };
  const rotateAction = state.value === "role_switching"
    ? state.targetRole === "student"
      ? { title: "demoSwitchingStudentTitle" as const, body: "demoSwitchingStudentBody" as const, action: "continueAsStudentAction" as const, run: () => demo.rotateToStudent(state.caseId) }
      : state.targetRole === "advisor"
        ? { title: "demoSwitchingAdvisorTitle" as const, body: "demoSwitchingAdvisorBody" as const, action: "continueAsAdvisorAction" as const, run: () => demo.rotateToAdvisor(state.caseId) }
        : { title: "demoSwitchingTitle" as const, body: "demoSwitchingBody" as const, action: "continueAsParentAction" as const, run: () => demo.rotateToParent(state.caseId) }
    : null;

  return (
    <PresentationShell contextKey="contextAdvisorFamily" mainId="demo-main">
      <div className="demo-shell">
        {demo.journeyConflict === "collaboration" ? <JourneyConflictNotice currentJourney="collaboration" returnHref="/demo/collaboration" onEnd={() => void demo.endConflictingJourney()} /> : null}
        {state.value === "bootstrapping" && !demo.journeyConflict ? (
          <section className="ledger-hero"><p className="overline">{copy("demoStartOverline")}</p><h1>{copy("demoStartTitle")}</h1><p className="lede">{copy("demoStartBody")}</p><button className="primary-action" type="button" onClick={() => runUserAction(() => demo.connectAdvisor())}>{copy("demoStartAction")}</button></section>
        ) : null}
        {ledger ? (
          <AdvisorLedger
            ledger={ledger}
            confirmedFacts={confirmedFactsFor(ledger.case_id, ledger.case_revision)}
            busy={busy}
            onPrimaryAction={() => runUserAction(primaryFor(ledger))}
            onSecondaryAction={ledger.phase === "review_required"
              ? () => runUserAction(() => demo.requestRevision())
              : undefined}
          />
        ) : null}
        {demo.inspector && inspectorVisible ? <PlanningSkillInspector inspector={demo.inspector} /> : null}
        {state.value === "revision_requested" ? (
          <section className="ledger-hero" aria-labelledby="revision-proposal-title">
            <p className="role-status">{copy("activeRoleLabel")}: {presentCode(locale, "role", "student")}</p>
            <h1 id="revision-proposal-title">{copy("revisionProposalTitle")}</h1>
            <p>{copy("studentRoleAuthority")}</p>
            <p>{copy("revisionProposalBody")}</p>
            <RevisionFactEditor
              currentFacts={demo.currentFacts}
              expectedCaseRevision={state.status.current_revision}
              onSubmit={() => runUserAction(() => demo.submitPreferredCountries())}
            />
          </section>
        ) : null}
        {rotateAction ? (
          <section className="ledger-hero" aria-live="polite">
            <h1>{copy(rotateAction.title)}</h1>
            <p>{copy(rotateAction.body)}</p>
            <button className="primary-action" type="button" onClick={() => runUserAction(rotateAction.run)}>
              {copy(rotateAction.action)}
            </button>
          </section>
        ) : null}
        {state.value === "family_review" ? <FamilyDecisionBrief brief={state.brief} confirmed={demo.confirmed} onConfirm={demo.setConfirmed} onSubmit={() => runUserAction(() => demo.decide())} /> : null}
        {state.value === "decision_submitting" ? <section className="ledger-hero" aria-live="polite"><h1>{copy("demoRecordingDecision")}</h1></section> : null}
        {state.value === "plan_ready" ? (
          <>
            <div className="section-heading">
              <p className="role-status">{copy("activeRoleLabel")}: {presentCode(locale, "role", "parent")}</p>
              <p>{copy("parentRoleAuthority")}</p>
            </div>
            <DecisionReceiptTimeline brief={state.brief} />
          </>
        ) : null}
        {state.value === "recoverable_error" ? <RecoveryNotice code={state.code} onReconnect={() => runUserAction(() => demo.retry())} /> : null}
      </div>
    </PresentationShell>
  );
}
