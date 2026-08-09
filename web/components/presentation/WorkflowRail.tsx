import type { PresentationCopyKey } from "../../lib/presentation/catalog";
import { WORKFLOW_STAGES, type WorkflowStage } from "../../lib/presentation/journey";

type WorkflowRailProps = {
  currentStage: WorkflowStage | null;
  copy: (key: PresentationCopyKey) => string;
};

const STAGE_COPY: Record<WorkflowStage, PresentationCopyKey> = {
  consultation_intake: "workflowStageConsultationIntake",
  client_fact_review: "workflowStageClientFactReview",
  route_analysis: "workflowStageRouteAnalysis",
  client_confirmation: "workflowStageClientConfirmation",
  execution_followup: "workflowStageExecutionFollowup",
};

export function WorkflowRail({ currentStage, copy }: WorkflowRailProps) {
  const currentIndex = currentStage === null ? -1 : WORKFLOW_STAGES.indexOf(currentStage);

  return (
    <nav className="workflow-rail" aria-label={copy("workflowRailLabel")}>
      <ol
        className="workflow-rail-list"
        aria-label={copy("workflowRailLabel")}
        data-current-stage={currentStage ?? undefined}
      >
        {WORKFLOW_STAGES.map((stage, index) => {
          const state = index < currentIndex ? "complete" : index === currentIndex ? "current" : "upcoming";
          return (
            <li
              key={stage}
              className="workflow-rail-item"
              data-stage={stage}
              data-state={state}
              aria-current={state === "current" ? "step" : undefined}
            >
              <span className="workflow-rail-number" aria-hidden="true">
                {String(index + 1).padStart(2, "0")}
              </span>
              <span className="workflow-rail-label">{copy(STAGE_COPY[stage])}</span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
