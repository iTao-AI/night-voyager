"use client";

import { useEffect, useRef } from "react";

import { usePresentation } from "../../lib/presentation/context";
import { planExecutionWorkflowStage } from "../../lib/presentation/journey";
import {
  usePlanExecution,
  type PlanExecutionController,
} from "../../lib/plan-execution/use-plan-execution";
import { AdvisorVerificationPanel } from "./AdvisorVerificationPanel";
import { CheckpointAttestationForm } from "./CheckpointAttestationForm";
import { CurrentCheckpoint } from "./CurrentCheckpoint";
import { ExecutionActivity } from "./ExecutionActivity";
import { ExecutionRecoveryNotice } from "./ExecutionRecoveryNotice";
import { ReassessmentHandoff } from "./ReassessmentHandoff";
import { AdvisorWorkspaceShell } from "../presentation/AdvisorWorkspaceShell";
import type { PlanExecutionDemoScenario } from "../../lib/plan-execution/scenario";

export function PlanExecutionWorkspace({
  controller: suppliedController,
  scenario = "happy",
}: {
  controller?: PlanExecutionController;
  scenario?: PlanExecutionDemoScenario;
}) {
  const liveController = usePlanExecution(undefined, scenario);
  const controller = suppliedController ?? liveController;
  const { state, busy } = controller;
  const { copy } = usePresentation();
  const workflowStage = planExecutionWorkflowStage(state.value);
  const role = state.context?.active_role;
  const checkpoint = state.view?.current_checkpoint ?? null;
  const canAttest = state.value === "checkpoint_active"
    && checkpoint?.state === "in_progress"
    && state.view?.current_action.code === "checkpoint_attestation_required"
    && state.view.current_action.owner_role === role;
  const canVerify = state.value === "awaiting_advisor"
    && state.view?.current_action.code === "advisor_verification_required"
    && state.view?.current_action.owner_role === role;
  const isBlocked = state.view?.execution.state === "active"
    && checkpoint?.state === "blocked";
  const isOverdue = state.view?.execution.state === "active"
    && checkpoint?.risk_state === "overdue";
  const canReassess = role === "advisor" && (isBlocked || isOverdue);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const previousState = useRef(state.value);

  useEffect(() => {
    const changed = previousState.current !== state.value;
    previousState.current = state.value;
    if (changed && state.value !== "loading" && state.value !== "mutation_in_flight") {
      headingRef.current?.focus();
    }
  }, [state.value]);

  const milestones = {
    documents: copy("planExecutionMilestoneDocuments"),
    application: copy("planExecutionMilestoneApplication"),
    visa: copy("planExecutionMilestoneVisa"),
    arrival: copy("planExecutionMilestoneArrival"),
  };
  const checkpointStates = {
    pending: copy("planExecutionCheckpointPending"),
    in_progress: copy("planExecutionCheckpointInProgress"),
    awaiting_advisor: copy("planExecutionCheckpointAwaitingAdvisor"),
    verified: copy("planExecutionCheckpointVerified"),
    blocked: copy("planExecutionCheckpointBlocked"),
  };
  const roles = {
    student: copy("roleStudent"),
    parent: copy("roleParent"),
  };
  const risks = {
    on_track: copy("planExecutionRiskOnTrack"),
    due_soon: copy("planExecutionRiskDueSoon"),
    overdue: copy("planExecutionRiskOverdue"),
  };
  const nextHandoff = state.view?.current_action.code === "checkpoint_attestation_required"
    ? copy("planExecutionNextAdvisor")
    : state.view?.current_action.code === "advisor_verification_required"
      ? copy("planExecutionNextFamily")
      : state.view?.current_action.code === "reassessment_handoff_required"
        ? copy("planExecutionNextFuture")
        : state.view?.current_action.code === "execution_completed"
          ? copy("planExecutionNextNone")
          : copy("planExecutionConnectPrompt");
  const liveMessage = state.value === "awaiting_advisor"
    ? copy("planExecutionWaitingAdvisor")
    : state.value === "execution_completed"
      ? copy("planExecutionCompleted")
      : state.value === "reassessment_required"
        ? copy("planExecutionReassessment")
        : state.value === "session_changed"
          ? copy("planExecutionSessionChanged")
          : state.value === "recoverable_error"
            ? copy("planExecutionRecoverableError")
            : "";

  const authorityAction = (
    <div className="plan-execution-authority" data-execution-authority>
      <div className="current-action-controls" data-current-action-controls>
        {state.value === "loading" && <p>{copy("planExecutionConnectPrompt")}</p>}
        {state.value === "ready_to_start" && (
          <>
            {role === "advisor" && <p>{copy("planExecutionConnectPrompt")}</p>}
            <button
              className="execution-primary-action workspace-primary-action"
              data-primary-action="true"
              disabled={busy || role === "advisor"}
              onClick={() => void controller.start()}
            >
              {copy("planExecutionStart")}
            </button>
          </>
        )}
        {canAttest && (
          <CheckpointAttestationForm
            disabled={busy}
            onProgress={() => void controller.attest("progress")}
            onCompletion={() => void controller.attest("completion")}
            onBlocked={(reason) => void controller.attest("blocked", reason)}
            labels={{
              group: copy("planExecutionAttestationLabel"),
              progress: copy("planExecutionProgress"),
              completion: copy("planExecutionSubmitCompletion"),
              blocked: copy("planExecutionRecordBlocked"),
              blockedReason: copy("planExecutionBlockedReason"),
              missingInput: copy("planExecutionMissingInput"),
              externalUnavailable: copy("planExecutionExternalUnavailable"),
              deadlineRisk: copy("planExecutionDeadlineRisk"),
            }}
          />
        )}
        {isBlocked && <p>{copy("planExecutionBlocked")}</p>}
        {isOverdue && <p>{copy("planExecutionOverdue")}</p>}
        {canReassess && (
          <>
            <p>{copy("planExecutionReassessmentStop")}</p>
            <button
              className="execution-primary-action workspace-primary-action"
              data-primary-action="true"
              disabled={busy}
              onClick={() => void controller.reassess(isBlocked ? "blocked_attestation" : "deadline_elapsed")}
            >
              {copy("planExecutionRequestReassessment")}
            </button>
          </>
        )}
        {state.value === "awaiting_advisor" && !canVerify && (
          <p>{copy("planExecutionWaitingAdvisor")}</p>
        )}
        {canVerify && (
          <AdvisorVerificationPanel
            disabled={busy}
            onVerify={() => void controller.verify("verify")}
            onRequestUpdate={() => void controller.verify("request_update")}
            labels={{
              group: copy("planExecutionVerificationLabel"),
              verify: copy("planExecutionVerify"),
              requestUpdate: copy("planExecutionRequestUpdate"),
            }}
          />
        )}
        {state.value === "execution_completed" && <p>{copy("planExecutionCompleted")}</p>}
        {state.value === "reassessment_required" && <p>{copy("planExecutionReassessment")}</p>}
        {(state.value === "session_changed" || state.value === "recoverable_error") && (
          <ExecutionRecoveryNotice
            sessionChanged={state.value === "session_changed"}
            disabled={busy}
            onRecover={() => void controller.recover()}
            labels={{
              sessionChanged: copy("planExecutionSessionChanged"),
              recoverable: copy("planExecutionRecoverableError"),
              recover: copy("planExecutionRecover"),
            }}
          />
        )}
      </div>
    </div>
  );

  return (
    <AdvisorWorkspaceShell
      activeRole={role ?? null}
      contextKey="contextPlanExecution"
      currentStage={workflowStage}
      mainId="plan-execution-main"
      proofSegment="independent_execution_scenario"
      status={<p className="status workspace-status-copy">{liveMessage || copy("planExecutionConnectPrompt")}</p>}
      supportingEvidence={
        <>
          <section className="plan-role-switcher" aria-labelledby="plan-role-title">
            <h3 id="plan-role-title">{copy("planExecutionRoleTitle")}</h3>
            <p>{copy("planExecutionRoleBody")}</p>
            <div className="role-switcher-row">
              {(["student", "parent", "advisor"] as const).map((nextRole) => (
                <button
                  aria-pressed={role === nextRole}
                  disabled={busy}
                  key={nextRole}
                  onClick={() => void (state.context
                    ? controller.switchRole(nextRole)
                    : controller.connect(nextRole))}
                >
                  {copy(nextRole === "student" ? "roleStudent" : nextRole === "parent" ? "roleParent" : "roleAdvisor")}
                </button>
              ))}
            </div>
          </section>
          <section className="approved-plan" aria-labelledby="approved-plan-title">
            <div className="section-heading">
              <h3 id="approved-plan-title">{copy("planExecutionApprovedPlanTitle")}</h3>
              <p>{copy("planExecutionApprovedPlanBody")}</p>
            </div>
            <ol className="approved-plan-steps">
              {(state.view?.checkpoints ?? []).map((item) => (
                <li data-state={item.state} key={item.checkpoint_id}>
                  <span className="plan-step-number" aria-hidden="true">
                    {String(item.ordinal).padStart(2, "0")}
                  </span>
                  <strong>{milestones[item.milestone_key]}</strong>
                  <span>{checkpointStates[item.state]}</span>
                  <small>{item.due_date} · {roles[item.accountable_role]}</small>
                </li>
              ))}
            </ol>
          </section>
          <ExecutionActivity
            activity={state.view?.activity ?? []}
            total={state.view?.activity_total ?? 0}
            truncated={state.view?.activity_truncated ?? false}
            labels={{
              title: copy("planExecutionActivityTitle"),
              disclosure: copy("planExecutionActivityDisclosure"),
              empty: copy("planExecutionNoActivity"),
              shown: copy("planExecutionActivityShown"),
              total: copy("planExecutionActivityTotal"),
              items: copy("planExecutionActivityItems"),
              latest64: copy("planExecutionActivityLatest64"),
              attestation: copy("planExecutionActivityAttestation"),
              verification: copy("planExecutionActivityVerification"),
              reassessment: copy("planExecutionActivityReassessment"),
              receipt: copy("planExecutionActivityReceipt"),
            }}
          />
        </>
      }
      authority={authorityAction}
      technicalEvidence={<p>{copy("planExecutionApprovedPlanBody")}</p>}
      titleKey="planExecutionWorkspaceTitle"
    >
      <p className="sr-only" role="status" aria-atomic="true" aria-live="polite">
        {liveMessage}
      </p>
      <section data-section="current-action" className="ledger-hero plan-execution-hero">
        <p className="eyebrow">{copy("planExecutionEyebrow")}</p>
        <h3 ref={headingRef} tabIndex={-1}>{copy("planExecutionCurrentAction")}</h3>
        <div className="plan-execution-current-grid">
          <div
            className="plan-authority-summary"
            data-plan-authority-summary
          >
            <CurrentCheckpoint
              checkpoint={checkpoint}
              labels={{
                empty: copy("planExecutionNoCurrentCheckpoint"),
                milestone: copy("planExecutionCheckpointLabel"),
                state: copy("planExecutionCheckpointState"),
                dueDate: copy("planExecutionDueDate"),
                ownerRole: copy("planExecutionOwnerRole"),
                riskState: copy("planExecutionRiskState"),
                milestones,
                states: checkpointStates,
                roles,
                risks,
              }}
            />
            <div className="next-handoff">
              <p className="field-label">{copy("planExecutionNextHandoff")}</p>
              <p>{nextHandoff}</p>
            </div>
          </div>
        </div>
      </section>
      {state.value === "reassessment_required" && state.view?.reassessment && (
        <ReassessmentHandoff
          reassessment={state.view.reassessment}
          labels={{
            title: copy("planExecutionHandoffTitle"),
            stop: copy("planExecutionReassessmentStop"),
            pending: copy("planExecutionHandoffPending"),
            whoNext: copy("planExecutionWhoNext"),
            blockedTrigger: copy("planExecutionBlockedTrigger"),
            deadlineTrigger: copy("planExecutionDeadlineTrigger"),
          }}
        />
      )}
    </AdvisorWorkspaceShell>
  );
}
