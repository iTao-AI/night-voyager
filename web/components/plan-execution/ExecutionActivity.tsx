import type { TimelineActivity } from "../../lib/plan-execution/contracts";

export function ExecutionActivity({
  activity,
  total,
  truncated,
}: {
  activity: TimelineActivity[];
  total: number;
  truncated: boolean;
}) {
  return (
    <section aria-labelledby="execution-activity-title">
      <h2 id="execution-activity-title">活动记录</h2>
      {activity.length === 0
        ? <p>尚无活动记录。</p>
        : <ol>{activity.map((item) => <li key={item.durable_id}>{item.kind}</li>)}</ol>}
      <p>{truncated ? `显示 ${activity.length} / ${total}` : `共 ${total} 条`}</p>
    </section>
  );
}
