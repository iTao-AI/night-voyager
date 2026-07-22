"use client";

import { useEffect, useRef } from "react";

import { useCollaborationDemo } from "../../lib/collaboration-demo/use-collaboration-demo";
import { presentCode } from "../../lib/presentation/codes";
import { usePresentation } from "../../lib/presentation/context";
import { JourneyConflictNotice } from "../demo-session/JourneyConflictNotice";
import { PresentationShell } from "../presentation/PresentationShell";
import { PlanningSkillInspector } from "../skill-inspector/PlanningSkillInspector";
import { CollaborationRecoveryNotice } from "./CollaborationRecoveryNotice";
import { ConfirmedFactSummary } from "./ConfirmedFactSummary";
import { MemoryCandidateCard } from "./MemoryCandidateCard";
import { SharedThread } from "./SharedThread";

export function CollaborationDemo() {
  const demo = useCollaborationDemo();
  const { locale, copy } = usePresentation();
  const { state } = demo;
  const phaseHeading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (["advisor_reviewing", "replan_required", "handoff_validating", "recoverable_error"].includes(state.value)) phaseHeading.current?.focus();
  }, [state.value]);

  const context = state.context;
  const busy = state.value === "message_submitting" || state.value === "confirmation_submitting" || state.value === "switching_to_advisor";
  const advisorCandidate = context.candidate && "candidate_id" in context.candidate ? context.candidate : null;
  const canConfirm = state.value === "advisor_reviewing" && advisorCandidate?.state === "pending" && advisorCandidate.case_revision === context.caseRevision;

  return (
    <PresentationShell contextKey="contextCollaboration" mainId="collaboration-main">
      <div className="demo-shell collaboration-shell">
        {demo.journeyConflict === "advisor-family" ? <JourneyConflictNotice currentJourney="advisor-family" returnHref="/demo" onEnd={() => void demo.endConflictingJourney()} /> : null}
        {!demo.journeyConflict ? (
          <>
            <section className="ledger-hero collaboration-hero" aria-labelledby="collaboration-title">
              <p className="overline">{copy("collaborationHeroOverline")}</p>
              <h1 id="collaboration-title">{copy("collaborationTitle")}</h1>
              <p className="lede">{copy("collaborationLede")}</p>
              <p className="role-status" role="status">{copy("currentRoleLabel")}：{presentCode(locale, "role", context.role)}</p>
              {state.value === "bootstrapping_parent" ? <button className="primary-action" type="button" onClick={() => void demo.connectParent()}>{copy("collaborationStartParent")}</button> : null}

              {state.value === "thread_ready" ? (
                <section className="collaboration-action" aria-labelledby="parent-action-title">
                  <h2 id="parent-action-title">{copy(context.messages.length ? "parentProposeTitle" : "parentMessageTitle")}</h2>
                  <p>{copy(context.messages.length ? "parentProposalPending" : "parentMessageBoundary")}</p>
                  <button type="button" onClick={() => void (context.messages.length ? demo.proposeBudget() : demo.appendMessage())}>{copy(context.messages.length ? "parentProposeAction" : "parentMessageAction")}</button>
                </section>
              ) : null}

              {state.value === "message_submitting" ? <section className="collaboration-action" aria-live="polite"><h2>{copy("recordingMessageTitle")}</h2><button type="button" disabled>{copy("recordingMessageAction")}</button></section> : null}

              {state.value === "proposal_pending" ? (
                <section className="collaboration-action" aria-labelledby="switch-title"><h2 id="switch-title">{copy("moveAdvisorTitle")}</h2><p>{copy("moveAdvisorBody")}</p><button type="button" onClick={() => void demo.switchToAdvisor()}>{copy("moveAdvisorAction")}</button></section>
              ) : null}

              {state.value === "switching_to_advisor" ? <section className="collaboration-action" aria-live="polite"><h2>{copy("switchingAuthorityTitle")}</h2><p>{copy("switchingAuthorityBody")}</p><button type="button" disabled>{copy("switchingRoleAction")}</button></section> : null}

              {state.value === "advisor_reviewing" ? (
                <section className="collaboration-action" aria-labelledby="advisor-confirmation-title"><h2 id="advisor-confirmation-title" ref={phaseHeading} tabIndex={-1}>{copy("advisorConfirmationTitle")}</h2><p>{copy("advisorConfirmationBody")}</p><button type="button" disabled={!canConfirm} onClick={() => void demo.confirmCandidate()}>{copy("advisorConfirmBudget")}</button>{!canConfirm ? <p className="disabled-reason">{copy("advisorReloadBoundary")}</p> : null}</section>
              ) : null}

              {state.value === "confirmation_submitting" ? <section className="collaboration-action" aria-live="polite"><h2>{copy("publishingAuthorityTitle")}</h2><button type="button" disabled>{copy("publishingAuthorityAction")}</button></section> : null}

              {state.value === "replan_required" && context.fact ? (
                <section className="collaboration-action replan-boundary" aria-labelledby="replan-title"><h2 id="replan-title" ref={phaseHeading} tabIndex={-1}>{copy("replanTitle")}</h2><p>{copy("replanBody")}</p><button className="primary-action" type="button" onClick={() => void demo.continueToPlanning()}>{copy("replanAction")}</button></section>
              ) : null}

              {state.value === "handoff_validating" && context.fact ? (
                <section className="collaboration-action replan-boundary" aria-labelledby="handoff-title" aria-live="polite"><h2 id="handoff-title" ref={phaseHeading} tabIndex={-1}>{copy("handoffTitle")}</h2><p>{copy("handoffBody")}</p><button className="primary-action" type="button" disabled>{copy("handoffAction")}</button></section>
              ) : null}

              {state.value === "recoverable_error" ? <CollaborationRecoveryNotice category={state.category} onRetry={() => void demo.retry()} headingRef={phaseHeading} /> : null}

              <ol className="authority-steps" aria-label={copy("collaborationPathLabel")}>
                <li>{copy("pathSharedMessage")}</li><li>{copy("pathTypedProposal")}</li><li>{copy("pathAdvisorReview")}</li><li>{copy("pathConfirmedFact")}</li><li>{copy("pathCaseRevision")}</li><li>{copy("pathReplanRequired")}</li>
              </ol>
            </section>

            {context.thread ? <SharedThread messages={context.messages} loading={busy && context.messages.length === 0} /> : null}

            {context.candidate ? <MemoryCandidateCard candidate={context.candidate} /> : null}
            {context.role === "advisor" && demo.inspector ? <PlanningSkillInspector inspector={demo.inspector} /> : null}

            {["replan_required", "handoff_validating"].includes(state.value) && context.fact ? <ConfirmedFactSummary fact={context.fact} caseRevision={context.caseRevision} /> : null}
          </>
        ) : null}
      </div>
    </PresentationShell>
  );
}
