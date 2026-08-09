"use client";

import { useEffect, useRef } from "react";

import { useCollaborationDemo } from "../../lib/collaboration-demo/use-collaboration-demo";
import { presentCode } from "../../lib/presentation/codes";
import { usePresentation } from "../../lib/presentation/context";
import { collaborationWorkflowStage } from "../../lib/presentation/journey";
import { AdvisorWorkspaceShell } from "../presentation/AdvisorWorkspaceShell";
import { JourneyConflictNotice } from "../demo-session/JourneyConflictNotice";
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
  const conflictHeading = useRef<HTMLHeadingElement>(null);
  const previousConflict = useRef<typeof demo.journeyConflict>(null);

  useEffect(() => {
    if (["advisor_reviewing", "replan_required", "handoff_validating", "recoverable_error"].includes(state.value)) phaseHeading.current?.focus();
  }, [state.value]);

  useEffect(() => {
    if (demo.journeyConflict && previousConflict.current !== demo.journeyConflict) conflictHeading.current?.focus();
    previousConflict.current = demo.journeyConflict;
  }, [demo.journeyConflict]);

  const context = state.context;
  const journeyStage = collaborationWorkflowStage(
    state.value,
    state.value === "recoverable_error" ? state.resumePhase : undefined,
  );
  const busy = state.value === "message_submitting" || state.value === "confirmation_submitting" || state.value === "switching_to_advisor";
  const advisorCandidate = context.candidate && "candidate_id" in context.candidate ? context.candidate : null;
  const canConfirm = state.value === "advisor_reviewing" && advisorCandidate?.state === "pending" && advisorCandidate.case_revision === context.caseRevision;
  const status = (() => {
    switch (state.value) {
      case "bootstrapping_parent": return copy("collaborationStartParent");
      case "thread_ready": return copy("parentMessageBoundary");
      case "message_submitting": return copy("recordingMessageTitle");
      case "proposal_pending": return copy("parentProposalPending");
      case "switching_to_advisor": return copy("switchingAuthorityBody");
      case "advisor_reviewing": return copy("advisorConfirmationBody");
      case "confirmation_submitting": return copy("publishingAuthorityTitle");
      case "replan_required": return copy("replanBody");
      case "handoff_validating": return copy("handoffBody");
      case "recoverable_error": return copy("collaborationRecoveryBoundary");
    }
  })();

  return (
    <AdvisorWorkspaceShell
      activeRole={context.role}
      contextKey="contextCollaboration"
      currentStage={journeyStage}
      mainId="collaboration-main"
      proofSegment="connected_same_case"
      status={<p className="status workspace-status-copy">{status}</p>}
      supportingEvidence={
        <>
          {context.thread ? <SharedThread messages={context.messages} loading={busy && context.messages.length === 0} /> : null}
          {context.candidate ? <MemoryCandidateCard candidate={context.candidate} /> : null}
          {["replan_required", "handoff_validating"].includes(state.value) && context.fact ? <ConfirmedFactSummary fact={context.fact} caseRevision={context.caseRevision} /> : null}
        </>
      }
      technicalEvidence={
        <>
          {context.role === "advisor" && demo.inspector ? <PlanningSkillInspector inspector={demo.inspector} /> : null}
          <ol className="authority-steps" aria-label={copy("collaborationPathLabel")}>
            <li>{copy("pathSharedMessage")}</li>
            <li><span>{copy("typedProposalLabel")}</span> <span className="technical-label">{copy("pathTypedProposal")}</span></li>
            <li>{copy("pathAdvisorReview")}</li>
            <li>{copy("pathConfirmedFact")}</li>
            <li><span>{copy("caseRevisionLabel")}</span> <span className="technical-label">{copy("pathCaseRevision")}</span></li>
            <li>{copy("pathReplanRequired")}</li>
          </ol>
        </>
      }
      titleKey="collaborationTitle"
    >
      {demo.journeyConflict === "advisor-family" ? (
        <JourneyConflictNotice
          currentJourney="advisor-family"
          returnHref="/demo"
          headingRef={conflictHeading}
          onEnd={() => void demo.endConflictingJourney()}
        />
      ) : (
        <>
          <p className="overline">{copy("collaborationHeroOverline")}</p>
          <p className="lede">{copy("collaborationLede")}</p>
          <p className="role-status">{copy("currentRoleLabel")}：{presentCode(locale, "role", context.role)}</p>

          {state.value === "bootstrapping_parent" ? <button className="primary-action" data-primary-action="true" type="button" onClick={() => void demo.connectParent()}>{copy("collaborationStartParent")}</button> : null}

          {state.value === "thread_ready" ? (
            <section className="collaboration-action" aria-labelledby="parent-action-title">
              <h3 id="parent-action-title">{copy(context.messages.length ? "parentProposeTitle" : "parentMessageTitle")}</h3>
              <p>{copy(context.messages.length ? "parentProposalPending" : "parentMessageBoundary")}</p>
              <button className="primary-action" data-primary-action="true" type="button" onClick={() => void (context.messages.length ? demo.proposeBudget() : demo.appendMessage())}>{copy(context.messages.length ? "parentProposeAction" : "parentMessageAction")}</button>
            </section>
          ) : null}

          {state.value === "message_submitting" ? <section className="collaboration-action" aria-live="polite"><h3>{copy("recordingMessageTitle")}</h3><button className="primary-action" data-primary-action="true" type="button" disabled>{copy("recordingMessageAction")}</button></section> : null}

          {state.value === "proposal_pending" ? (
            <section className="collaboration-action" aria-labelledby="switch-title"><h3 id="switch-title">{copy("moveAdvisorTitle")}</h3><p>{copy("moveAdvisorBody")}</p><button className="primary-action" data-primary-action="true" type="button" onClick={() => void demo.switchToAdvisor()}>{copy("moveAdvisorAction")}</button></section>
          ) : null}

          {state.value === "switching_to_advisor" ? <section className="collaboration-action" aria-live="polite"><h3>{copy("switchingAuthorityTitle")}</h3><p>{copy("switchingAuthorityBody")}</p><button className="primary-action" data-primary-action="true" type="button" disabled>{copy("switchingRoleAction")}</button></section> : null}

          {state.value === "advisor_reviewing" ? (
            <section className="collaboration-action" aria-labelledby="advisor-confirmation-title"><h3 id="advisor-confirmation-title" ref={phaseHeading} tabIndex={-1}>{copy("advisorConfirmationTitle")}</h3><p>{copy("advisorConfirmationBody")}</p><button className="primary-action" data-primary-action="true" type="button" disabled={!canConfirm} onClick={() => void demo.confirmCandidate()}>{copy("advisorConfirmBudget")}</button>{!canConfirm ? <p className="disabled-reason">{copy("advisorReloadBoundary")}</p> : null}</section>
          ) : null}

          {state.value === "confirmation_submitting" ? <section className="collaboration-action" aria-live="polite"><h3>{copy("publishingAuthorityTitle")}</h3><button className="primary-action" data-primary-action="true" type="button" disabled>{copy("publishingAuthorityAction")}</button></section> : null}

          {state.value === "replan_required" && context.fact ? (
            <section className="collaboration-action replan-boundary" aria-labelledby="replan-title"><h3 id="replan-title" ref={phaseHeading} tabIndex={-1}>{copy("replanTitle")}</h3><p>{copy("replanBody")}</p><button className="primary-action" data-primary-action="true" type="button" onClick={() => void demo.continueToPlanning()}>{copy("replanAction")}</button></section>
          ) : null}

          {state.value === "handoff_validating" && context.fact ? (
            <section className="collaboration-action replan-boundary" aria-labelledby="handoff-title" aria-live="polite"><h3 id="handoff-title" ref={phaseHeading} tabIndex={-1}>{copy("handoffTitle")}</h3><p>{copy("handoffBody")}</p><button className="primary-action" data-primary-action="true" type="button" disabled>{copy("handoffAction")}</button></section>
          ) : null}

          {state.value === "recoverable_error" ? <CollaborationRecoveryNotice category={state.category} onRetry={() => void demo.retry()} headingRef={phaseHeading} /> : null}
        </>
      )}
    </AdvisorWorkspaceShell>
  );
}
