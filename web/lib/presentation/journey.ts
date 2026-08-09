export const JOURNEY_STAGES = [
  "family_input",
  "advisor_confirmation",
  "route_review",
  "family_decision",
  "plan_execution",
] as const;

export type JourneyStage = (typeof JOURNEY_STAGES)[number];

type StageMap = Readonly<Record<string, JourneyStage>>;

export type JourneyStateReference = {
  value: string;
  prior?: JourneyStateReference;
};

function mapStage(value: string, stages: StageMap): JourneyStage | null {
  return stages[value] ?? null;
}

const COLLABORATION_STAGES: StageMap = {
  bootstrapping_parent: "family_input",
  thread_ready: "family_input",
  message_submitting: "family_input",
  proposal_pending: "family_input",
  switching_to_advisor: "advisor_confirmation",
  advisor_reviewing: "advisor_confirmation",
  confirmation_submitting: "advisor_confirmation",
  replan_required: "route_review",
  handoff_validating: "route_review",
};

const CONNECTED_STAGES: StageMap = {
  bootstrapping: "advisor_confirmation",
  advisor_ready: "advisor_confirmation",
  advisor_review: "advisor_confirmation",
  review_submitting: "advisor_confirmation",
  revision_fact_pending: "advisor_confirmation",
  revision_review_required: "advisor_confirmation",
  revision_requested: "family_input",
  task_creating: "route_review",
  task_streaming: "route_review",
  replan_required: "route_review",
  revision_task_active: "route_review",
  revision_blocked: "route_review",
  terminal_task_failure: "route_review",
  family_review: "family_decision",
  decision_submitting: "family_decision",
  plan_ready: "plan_execution",
};

const PLAN_EXECUTION_STAGES: StageMap = {
  loading: "plan_execution",
  ready_to_start: "plan_execution",
  checkpoint_active: "plan_execution",
  mutation_in_flight: "plan_execution",
  awaiting_advisor: "plan_execution",
  execution_completed: "plan_execution",
  reassessment_required: "plan_execution",
  session_changed: "plan_execution",
  recoverable_error: "plan_execution",
};

export function collaborationJourneyStage(value: string, resumePhase?: string | null): JourneyStage | null {
  if (value === "recoverable_error") return resumePhase ? mapStage(resumePhase, COLLABORATION_STAGES) : null;
  return mapStage(value, COLLABORATION_STAGES);
}

export function connectedJourneyStage(value: string, prior?: JourneyStateReference | null): JourneyStage | null {
  if (value === "role_switching" || value === "recoverable_error") {
    return prior ? connectedJourneyStage(prior.value, prior.prior) : null;
  }
  return mapStage(value, CONNECTED_STAGES);
}

export function planExecutionJourneyStage(value: string): JourneyStage | null {
  return mapStage(value, PLAN_EXECUTION_STAGES);
}

/**
 * Presentation-only workflow vocabulary. The legacy journey projection above
 * remains available to the not-yet-migrated demo routes until their shared
 * shell migration is complete.
 */
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
