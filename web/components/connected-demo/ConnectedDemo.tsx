"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";

import type { ConfirmedFactAdvisor } from "../../lib/collaboration-demo/contracts";
import { useConnectedDemo } from "../../lib/connected-demo/use-connected-demo";
import type { AdvisorLedger as Ledger } from "../../lib/connected-demo/contracts";
import type { DemoDisplayState } from "../../lib/connected-demo/reducer";
import { presentCode } from "../../lib/presentation/codes";
import { usePresentation } from "../../lib/presentation/context";
import { connectedWorkflowStage, type WorkflowStateReference } from "../../lib/presentation/journey";
import { AdvisorWorkspaceShell } from "../presentation/AdvisorWorkspaceShell";
import { JourneyConflictNotice } from "../demo-session/JourneyConflictNotice";
import { PlanningSkillInspector } from "../skill-inspector/PlanningSkillInspector";
import { AdvisorLedger, AdvisorLedgerAction } from "./AdvisorLedger";
import { DecisionReceiptTimeline } from "./DecisionReceiptTimeline";
import { EvidenceDisclosure } from "./EvidenceDisclosure";
import { FamilyDecisionAction, FamilyDecisionBrief } from "./FamilyDecisionBrief";
import { RecoveryAction, RecoveryNotice } from "./RecoveryNotice";
import { RevisionFactEditor } from "./RevisionFactEditor";

function retainedLedger(state: DemoDisplayState): Ledger | null {
  if ("ledger" in state) return state.ledger;
  if ((state.value === "role_switching" || state.value === "recoverable_error") && state.prior) {
    return retainedLedger(state.prior);
  }
  return null;
}

function workflowReference(state: DemoDisplayState): WorkflowStateReference {
  return {
    value: state.value,
    ...("prior" in state && state.prior ? { prior: workflowReference(state.prior) } : {}),
  };
}

function activeRole(state: DemoDisplayState): "student" | "parent" | "advisor" | null {
  if ("status" in state) return state.status.active_role;
  if ((state.value === "role_switching" || state.value === "recoverable_error") && state.prior) return activeRole(state.prior);
  return null;
}

export function ConnectedDemo() {
  const demo = useConnectedDemo();
  const { locale, copy } = usePresentation();
  const { state } = demo;
  const userTransition = useRef(false);
  const previousState = useRef(state.value);
  const conflictHeading = useRef<HTMLHeadingElement>(null);
  const previousConflict = useRef<typeof demo.journeyConflict>(null);
  const recoveryHeading = useRef<HTMLHeadingElement>(null);

  const runUserAction = (action: () => Promise<unknown> | void) => {
    userTransition.current = true;
    void action();
  };

  useEffect(() => {
    const busy = ["task_creating", "review_submitting", "decision_submitting", "role_switching"].includes(state.value);
    if (userTransition.current && previousState.current !== state.value && !busy) {
      const heading = document.querySelector<HTMLElement>("#demo-main .workspace-current-work > h2");
      heading?.setAttribute("tabindex", "-1");
      heading?.focus();
      userTransition.current = false;
    }
    previousState.current = state.value;
  }, [state.value]);

  useEffect(() => {
    if (demo.journeyConflict && previousConflict.current !== demo.journeyConflict) conflictHeading.current?.focus();
    previousConflict.current = demo.journeyConflict;
  }, [demo.journeyConflict]);

  useEffect(() => {
    if (state.value === "recoverable_error") recoveryHeading.current?.focus();
  }, [state.value]);

  const inspectorVisible = ["advisor_ready", "task_creating", "task_streaming", "advisor_review", "review_submitting", "terminal_task_failure"].includes(state.value);
  const confirmedFactsFor = (caseId: string, caseRevision: number): readonly ConfirmedFactAdvisor[] | null =>
    demo.currentFacts?.caseId === caseId && demo.currentFacts.caseRevision === caseRevision
      ? demo.currentFacts.facts.filter(
          (fact): fact is ConfirmedFactAdvisor => "confirmed_fact_id" in fact,
        )
      : null;
  const ledger = retainedLedger(state);
  const journeyStage = connectedWorkflowStage(
    state.value,
    "prior" in state && state.prior ? workflowReference(state.prior) : undefined,
  );
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
  const ledgerOwnsAction = Boolean(ledger && !["role_switching", "recoverable_error"].includes(state.value));
  const status = (() => {
    if (ledger) return presentCode(locale, "demoPhase", ledger.phase);
    switch (state.value) {
      case "bootstrapping": return copy("demoStartBody");
      case "revision_requested": return copy("revisionProposalBody");
      case "family_review": return copy("familyBriefOutcome");
      case "decision_submitting": return copy("demoRecordingDecision");
      case "plan_ready": return copy("receiptSummary");
      case "recoverable_error": return copy("recoveryBoundary");
      case "role_switching": return rotateAction ? copy(rotateAction.body) : copy("statusUnavailable");
    }
  })();
  const authorityAction = demo.journeyConflict ? (
    <JourneyConflictNotice
      currentJourney="collaboration"
      returnHref="/demo/collaboration"
      headingRef={conflictHeading}
      onEnd={() => void demo.endConflictingJourney()}
    />
  ) : state.value === "bootstrapping" ? (
    <button className="primary-action workspace-primary-action" data-primary-action="true" type="button" onClick={() => runUserAction(() => demo.connectAdvisor())}>{copy("demoStartAction")}</button>
  ) : state.value === "revision_requested" ? (
    <RevisionFactEditor
      currentFacts={demo.currentFacts}
      expectedCaseRevision={state.status.current_revision}
      onSubmit={() => runUserAction(() => demo.submitPreferredCountries())}
    />
  ) : rotateAction ? (
    <section className="collaboration-action" aria-live="polite">
      <h3>{copy(rotateAction.title)}</h3>
      <p>{copy(rotateAction.body)}</p>
      <button className="primary-action workspace-primary-action" data-primary-action="true" type="button" onClick={() => runUserAction(rotateAction.run)}>{copy(rotateAction.action)}</button>
    </section>
  ) : state.value === "family_review" ? (
    <FamilyDecisionAction brief={state.brief} confirmed={demo.confirmed} onConfirm={demo.setConfirmed} onSubmit={() => runUserAction(() => demo.decide())} />
  ) : state.value === "recoverable_error" ? (
    <RecoveryAction onReconnect={() => runUserAction(() => demo.retry())} />
  ) : ledgerOwnsAction && ledger ? (
    <AdvisorLedgerAction
      ledger={ledger}
      busy={busy}
      onPrimaryAction={() => runUserAction(primaryFor(ledger))}
      onSecondaryAction={ledger.phase === "review_required" ? () => runUserAction(() => demo.requestRevision()) : undefined}
    />
  ) : state.value === "decision_submitting" ? (
    <p className="workspace-authority-status" aria-live="polite">{copy("demoRecordingDecision")}</p>
  ) : state.value === "plan_ready" ? (
    <p className="workspace-authority-status">{copy("parentRoleAuthority")}</p>
  ) : (
    <p className="workspace-authority-status">{copy("workspaceAwaitingAction")}</p>
  );

  return (
    <AdvisorWorkspaceShell
      activeRole={activeRole(state)}
      contextKey="contextAdvisorFamily"
      currentStage={journeyStage}
      mainId="demo-main"
      proofSegment="connected_same_case"
      status={<p className="status workspace-status-copy">{status}</p>}
      supportingEvidence={ledger?.evidence?.length ? <EvidenceDisclosure evidence={ledger.evidence} /> : undefined}
      authority={authorityAction}
      technicalEvidence={
        demo.inspector && inspectorVisible
          ? <PlanningSkillInspector inspector={demo.inspector} />
          : <p>{copy("advisorRoleAuthority")}</p>
      }
      titleKey="connectedWorkspaceTitle"
    >
      {demo.journeyConflict === "collaboration" ? <p className="workspace-authority-status">{copy("journeyConflictBody")}</p> : null}

      {!demo.journeyConflict && state.value === "bootstrapping" ? (
        <section className="ledger-hero"><p className="overline">{copy("demoStartOverline")}</p><h3>{copy("demoStartTitle")}</h3><p className="lede">{copy("demoStartBody")}</p></section>
      ) : null}

      {!demo.journeyConflict && ledger ? (
        <AdvisorLedger
          ledger={ledger}
          confirmedFacts={confirmedFactsFor(ledger.case_id, ledger.case_revision)}
          busy={busy}
          renderAction={false}
          onPrimaryAction={() => runUserAction(primaryFor(ledger))}
          onSecondaryAction={ledger.phase === "review_required"
            ? () => runUserAction(() => demo.requestRevision())
            : undefined}
        />
      ) : null}

      {!demo.journeyConflict && state.value === "revision_requested" ? (
        <section className="ledger-hero" aria-labelledby="revision-proposal-title">
          <p className="role-status">{copy("activeRoleLabel")}: {presentCode(locale, "role", "student")}</p>
          <h3 id="revision-proposal-title">{copy("revisionProposalTitle")}</h3>
          <p>{copy("studentRoleAuthority")}</p>
          <p>{copy("revisionProposalBody")}</p>
        </section>
      ) : null}

      {!demo.journeyConflict && rotateAction ? (
        <section className="ledger-hero" aria-live="polite"><h3>{copy(rotateAction.title)}</h3><p>{copy(rotateAction.body)}</p></section>
      ) : null}

      {!demo.journeyConflict && state.value === "family_review" ? <FamilyDecisionBrief brief={state.brief} confirmed={demo.confirmed} onConfirm={demo.setConfirmed} onSubmit={() => runUserAction(() => demo.decide())} renderAction={false} /> : null}
      {!demo.journeyConflict && state.value === "decision_submitting" ? <section className="ledger-hero" aria-live="polite"><h3>{copy("demoRecordingDecision")}</h3></section> : null}
      {!demo.journeyConflict && state.value === "plan_ready" ? (
        <>
          <div className="section-heading">
            <p className="role-status">{copy("activeRoleLabel")}: {presentCode(locale, "role", "parent")}</p>
            <p>{copy("parentRoleAuthority")}</p>
          </div>
          <DecisionReceiptTimeline brief={state.brief} />
          <p className="separate-scenario-handoff"><Link className="secondary-action" href="/demo/plan">{copy("separateExecutionScenario")}</Link></p>
        </>
      ) : null}
      {!demo.journeyConflict && state.value === "recoverable_error" ? <RecoveryNotice code={state.code} onReconnect={() => runUserAction(() => demo.retry())} headingRef={recoveryHeading} renderAction={false} /> : null}
    </AdvisorWorkspaceShell>
  );
}
