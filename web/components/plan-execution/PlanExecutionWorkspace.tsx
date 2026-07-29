"use client";

import { PresentationShell } from "../presentation/PresentationShell";
import { usePresentation } from "../../lib/presentation/context";
import {
  usePlanExecution,
  type PlanExecutionController,
} from "../../lib/plan-execution/use-plan-execution";
import { AdvisorVerificationPanel } from "./AdvisorVerificationPanel";
import { CheckpointAttestationForm } from "./CheckpointAttestationForm";
import { CurrentCheckpoint } from "./CurrentCheckpoint";
import { ExecutionActivity } from "./ExecutionActivity";

export function PlanExecutionWorkspace({
  controller: suppliedController,
}: {
  controller?: PlanExecutionController;
}) {
  const liveController = usePlanExecution();
  const controller = suppliedController ?? liveController;
  const { state, busy } = controller;
  const { copy } = usePresentation();
  const role = state.context?.active_role;
  const checkpoint = state.view?.current_checkpoint ?? null;
  const canAttest = state.value === "checkpoint_active"
    && state.view?.current_action.owner_role === role;
  const canVerify = state.value === "awaiting_advisor"
    && state.view?.current_action.owner_role === role;
  return (
    <PresentationShell contextKey="contextPlanExecution" mainId="plan-execution-main">
      <div className="demo-shell">
        <section data-section="current-action" className="ledger-hero">
          <p className="eyebrow">{copy("planExecutionEyebrow")}</p>
          <h1>{copy("planExecutionCurrentAction")}</h1>
          {state.value === "loading" && <p>{copy("planExecutionConnectPrompt")}</p>}
          {state.value === "ready_to_start" && (
            <button disabled={busy || role === "advisor"} onClick={() => void controller.start()}>
              {copy("planExecutionStart")}
            </button>
          )}
          {canAttest && (
            <CheckpointAttestationForm
              disabled={busy}
              onProgress={() => void controller.attest("progress")}
              onCompletion={() => void controller.attest("completion")}
              labels={{
                group: copy("planExecutionAttestationLabel"),
                progress: copy("planExecutionProgress"),
                completion: copy("planExecutionSubmitCompletion"),
              }}
            />
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
          {state.value === "session_changed" && <p>{copy("planExecutionSessionChanged")}</p>}
          {state.value === "recoverable_error" && (
            <>
              <p>{copy("planExecutionRecoverableError")}</p>
              <button disabled={busy} onClick={() => void controller.recover()}>
                {copy("planExecutionRecover")}
              </button>
            </>
          )}
        </section>
        <section aria-labelledby="plan-role-title">
          <h2 id="plan-role-title">{copy("planExecutionRoleTitle")}</h2>
          <div>
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
        <section aria-labelledby="checkpoint-title">
          <h2 id="checkpoint-title">{copy("planExecutionCheckpointTitle")}</h2>
          <CurrentCheckpoint
            checkpoint={checkpoint}
            labels={{
              empty: copy("planExecutionNoCurrentCheckpoint"),
              dueDate: copy("planExecutionDueDate"),
              ownerRole: copy("planExecutionOwnerRole"),
              riskState: copy("planExecutionRiskState"),
            }}
          />
        </section>
        <ExecutionActivity
          activity={state.view?.activity ?? []}
          total={state.view?.activity_total ?? 0}
          truncated={state.view?.activity_truncated ?? false}
          labels={{
            title: copy("planExecutionActivityTitle"),
            empty: copy("planExecutionNoActivity"),
            shown: copy("planExecutionActivityShown"),
            total: copy("planExecutionActivityTotal"),
            items: copy("planExecutionActivityItems"),
          }}
        />
      </div>
    </PresentationShell>
  );
}
