import type { TimelineCheckpoint } from "../../lib/plan-execution/contracts";

export function CurrentCheckpoint({
  checkpoint,
  labels,
}: {
  checkpoint: TimelineCheckpoint | null;
  labels: { empty: string; dueDate: string; ownerRole: string; riskState: string };
}) {
  if (!checkpoint) return <p>{labels.empty}</p>;
  return (
    <dl>
      <div><dt>Checkpoint</dt><dd>{checkpoint.milestone_key}</dd></div>
      <div><dt>{labels.dueDate}</dt><dd>{checkpoint.due_date}</dd></div>
      <div><dt>{labels.ownerRole}</dt><dd>{checkpoint.accountable_role}</dd></div>
      <div><dt>{labels.riskState}</dt><dd>{checkpoint.risk_state}</dd></div>
    </dl>
  );
}
