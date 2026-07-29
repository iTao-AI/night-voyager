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
  labels: { title: string; empty: string; shown: string; total: string; items: string };
}) {
  return (
    <section aria-labelledby="execution-activity-title">
      <h2 id="execution-activity-title">{labels.title}</h2>
      {activity.length === 0
        ? <p>{labels.empty}</p>
        : <ol>{activity.map((item) => <li key={item.durable_id}>{item.kind}</li>)}</ol>}
      <p>{truncated
        ? `${labels.shown} ${activity.length} / ${total}`
        : `${labels.total} ${total} ${labels.items}`}</p>
    </section>
  );
}
