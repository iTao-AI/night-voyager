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
