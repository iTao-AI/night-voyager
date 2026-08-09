export const WORKFLOW_STAGES = [
  "consultation_intake",
  "client_fact_review",
  "route_analysis",
  "client_confirmation",
  "execution_followup",
] as const;

export type WorkflowStage = (typeof WORKFLOW_STAGES)[number];

export type WorkflowProofSegment =
  | "connected_same_case"
  | "independent_execution_scenario";

export type WorkflowStateReference = {
  value: string;
  prior?: WorkflowStateReference;
};

type WorkflowStageMap = Readonly<Record<string, WorkflowStage>>;

const COLLABORATION_WORKFLOW_STAGES: WorkflowStageMap = {
  bootstrapping_parent: "consultation_intake",
  thread_ready: "consultation_intake",
  message_submitting: "consultation_intake",
  proposal_pending: "client_fact_review",
  switching_to_advisor: "client_fact_review",
  advisor_reviewing: "client_fact_review",
  confirmation_submitting: "client_fact_review",
  replan_required: "route_analysis",
  handoff_validating: "route_analysis",
};

const CONNECTED_WORKFLOW_STAGES: WorkflowStageMap = {
  revision_requested: "client_fact_review",
  revision_fact_pending: "client_fact_review",
  bootstrapping: "route_analysis",
  advisor_ready: "route_analysis",
  task_creating: "route_analysis",
  task_streaming: "route_analysis",
  advisor_review: "route_analysis",
  review_submitting: "route_analysis",
  replan_required: "route_analysis",
  revision_blocked: "route_analysis",
  terminal_task_failure: "route_analysis",
  family_review: "client_confirmation",
  decision_submitting: "client_confirmation",
  plan_ready: "execution_followup",
};

const PLAN_EXECUTION_WORKFLOW_STAGES: WorkflowStageMap = {
  loading: "execution_followup",
  ready_to_start: "execution_followup",
  checkpoint_active: "execution_followup",
  mutation_in_flight: "execution_followup",
  awaiting_advisor: "execution_followup",
  execution_completed: "execution_followup",
  reassessment_required: "execution_followup",
  session_changed: "execution_followup",
  recoverable_error: "execution_followup",
};

function mapWorkflowStage(value: string, stages: WorkflowStageMap): WorkflowStage | null {
  return stages[value] ?? null;
}

export function collaborationWorkflowStage(
  value: string,
  resumePhase?: string | null,
): WorkflowStage | null {
  if (value === "recoverable_error") {
    return resumePhase ? mapWorkflowStage(resumePhase, COLLABORATION_WORKFLOW_STAGES) : null;
  }
  return mapWorkflowStage(value, COLLABORATION_WORKFLOW_STAGES);
}

export function connectedWorkflowStage(
  value: string,
  prior?: WorkflowStateReference | null,
): WorkflowStage | null {
  if (value === "role_switching" || value === "recoverable_error") {
    return prior ? connectedWorkflowStage(prior.value, prior.prior) : null;
  }
  return mapWorkflowStage(value, CONNECTED_WORKFLOW_STAGES);
}

export function planExecutionWorkflowStage(value: string): WorkflowStage | null {
  return mapWorkflowStage(value, PLAN_EXECUTION_WORKFLOW_STAGES);
}
