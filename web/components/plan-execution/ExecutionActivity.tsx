import type { TimelineActivity } from "../../lib/plan-execution/contracts";

export function ExecutionActivity({
  activity,
  total,
  truncated,
  labels,
}: {
  activity: TimelineActivity[];
  total: number;
  truncated: boolean;
  labels: {
    title: string;
    disclosure: string;
    empty: string;
    shown: string;
    total: string;
    items: string;
    latest64: string;
    attestation: string;
    verification: string;
    reassessment: string;
    receipt: string;
  };
}) {
  const activityLabels: Record<TimelineActivity["kind"], string> = {
    attestation_recorded: labels.attestation,
    verification_recorded: labels.verification,
    reassessment_recorded: labels.reassessment,
    mutation_receipt_recorded: labels.receipt,
  };
  return (
    <section className="execution-activity" aria-labelledby="execution-activity-title">
      <h2 id="execution-activity-title">{labels.title}</h2>
      <details className="technical-details">
        <summary>{labels.disclosure}</summary>
        {activity.length === 0
          ? <p>{labels.empty}</p>
          : <ol>{activity.map((item) => (
              <li key={item.durable_id}>{activityLabels[item.kind]}</li>
            ))}</ol>}
        <p>{truncated
          ? `${labels.shown} ${activity.length} / ${total}`
          : `${labels.total} ${total} ${labels.items}`}</p>
        {truncated && <p>{labels.latest64}</p>}
      </details>
    </section>
  );
}
