import type { PlanExecutionContext, TimelineExecutionView } from "./contracts";
import type { PresentationLocale } from "../presentation/locales";
import { getPresentationCopy, type PresentationCopyKey } from "../presentation/catalog";

export interface HandoffField { label: string; value: string }
export interface ReassessmentHandoffSummary {
  facts: HandoffField[];
  identities: HandoffField[];
  text: string;
}

export function buildReassessmentHandoff(
  context: PlanExecutionContext,
  view: TimelineExecutionView,
  locale: PresentationLocale,
): ReassessmentHandoffSummary | null {
  const execution = view.execution;
  const saved = view.reassessment;
  if (execution.state !== "reassessment_required" || !saved
    || context.execution_id !== execution.execution_id
    || context.case_id !== execution.case_id || context.case_revision !== execution.case_revision
    || context.decision_id !== execution.decision_id
    || context.decision_receipt_id !== execution.decision_receipt_id
    || context.timeline_plan_id !== execution.timeline_plan_id
    || saved.execution_id !== execution.execution_id
    || saved.predecessor_case_id !== execution.case_id
    || saved.predecessor_case_revision !== execution.case_revision
    || saved.predecessor_decision_id !== execution.decision_id
    || saved.predecessor_decision_receipt_id !== execution.decision_receipt_id
    || saved.predecessor_timeline_plan_id !== execution.timeline_plan_id
    || saved.predecessor_execution_id !== execution.execution_id
    || saved.predecessor_checkpoint_id !== saved.checkpoint_id
  ) return null;

  const copy = (key: PresentationCopyKey) => getPresentationCopy(locale, key);
  const checkpoint = view.checkpoints.find((item) =>
    item.checkpoint_id === saved.checkpoint_id && item.execution_id === saved.execution_id);
  const attestation = view.latest_attestation;
  const matchingBlocker = attestation !== null
    && attestation.attestation_id === saved.trigger_reference_id
    && attestation.execution_id === saved.execution_id
    && attestation.checkpoint_id === saved.checkpoint_id
    && attestation.attestation_kind === "blocked" && attestation.status_code === "work_blocked";
  const milestoneKeys = {
    documents: "planExecutionMilestoneDocuments", application: "planExecutionMilestoneApplication",
    visa: "planExecutionMilestoneVisa", arrival: "planExecutionMilestoneArrival",
  } as const;
  const reasonKeys = {
    missing_required_input: "planExecutionMissingInput",
    external_dependency_unavailable: "planExecutionExternalUnavailable",
    deadline_at_risk: "planExecutionDeadlineRisk", not_applicable: "handoffMissingBlocker",
  } as const;
  const field = (key: PresentationCopyKey, value: string): HandoffField => ({ label: copy(key), value });
  const facts = [
    field("caseRevisionDisclosureLabel", String(saved.predecessor_case_revision)),
    field("handoffSavedCheckpoint", checkpoint ? copy(milestoneKeys[checkpoint.milestone_key]) : copy("handoffMissingDetail")),
    field("planExecutionDueDate", checkpoint?.due_date ?? copy("handoffMissingDetail")),
    field("planExecutionOwnerRole", checkpoint
      ? copy(checkpoint.accountable_role === "student" ? "roleStudent" : "roleParent")
      : copy("handoffMissingDetail")),
    field("handoffTrigger", copy(saved.trigger === "blocked_attestation"
      ? "planExecutionBlockedTrigger" : "planExecutionDeadlineTrigger")),
    field("handoffKnownReason", saved.trigger === "deadline_elapsed"
      ? copy("handoffDeadlineReason") : matchingBlocker
        ? copy(reasonKeys[attestation.reason_code]) : copy("handoffMissingBlocker")),
    field("handoffAcceptedDate", saved.accepted_database_date),
    field("handoffObservedDate", view.observed_date),
    field("handoffNextOwner", copy("handoffAdvisorResponsibility")),
  ];
  const identities = [
    field("handoffCaseId", saved.predecessor_case_id),
    field("handoffDecisionId", saved.predecessor_decision_id),
    field("handoffReceiptId", saved.predecessor_decision_receipt_id),
    field("handoffPlanId", saved.predecessor_timeline_plan_id),
    field("handoffExecutionId", saved.execution_id),
    field("handoffCheckpointId", saved.checkpoint_id),
    field("handoffReassessmentId", saved.reassessment_id),
    field("handoffTriggerReference", saved.trigger_reference_id ?? copy("handoffNoTriggerReference")),
    field("handoffStatus", saved.successor_status),
    field("handoffProjectionReference", saved.accepted_trigger_projection_sha256),
  ];
  const text = [
    `Night Voyager · ${copy("syntheticLabel")}`, copy("planExecutionHandoffTitle"),
    copy("planExecutionReassessmentStop"), copy("planExecutionHandoffPending"),
    copy("planExecutionWhoNext"), "",
    ...facts.map(({ label, value }) => `${label}${locale === "zh-CN" ? "：" : ": "}${value}`), "",
    copy("handoffIdentities"),
    ...identities.map(({ label, value }) => `${label}${locale === "zh-CN" ? "：" : ": "}${value}`),
    copy("handoffProjectionNote"),
  ].join("\n");
  return { facts, identities, text };
}
