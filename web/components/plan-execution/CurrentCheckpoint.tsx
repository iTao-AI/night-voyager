import type { TimelineCheckpoint } from "../../lib/plan-execution/contracts";

export function CurrentCheckpoint({
  checkpoint,
  labels,
}: {
  checkpoint: TimelineCheckpoint | null;
  labels: {
    empty: string;
    milestone: string;
    state: string;
    dueDate: string;
    ownerRole: string;
    riskState: string;
    milestones: Record<TimelineCheckpoint["milestone_key"], string>;
    states: Record<TimelineCheckpoint["state"], string>;
    roles: Record<TimelineCheckpoint["accountable_role"], string>;
    risks: Record<TimelineCheckpoint["risk_state"], string>;
  };
}) {
  if (!checkpoint) return <p>{labels.empty}</p>;
  return (
    <dl className="current-checkpoint-summary">
      <div><dt>{labels.milestone}</dt><dd>{labels.milestones[checkpoint.milestone_key]}</dd></div>
      <div><dt>{labels.state}</dt><dd>{labels.states[checkpoint.state]}</dd></div>
      <div><dt>{labels.dueDate}</dt><dd>{checkpoint.due_date}</dd></div>
      <div><dt>{labels.ownerRole}</dt><dd>{labels.roles[checkpoint.accountable_role]}</dd></div>
      <div><dt>{labels.riskState}</dt><dd>{labels.risks[checkpoint.risk_state]}</dd></div>
    </dl>
  );
}
