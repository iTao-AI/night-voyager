import type { TimelineCheckpoint } from "../../lib/plan-execution/contracts";

export function CurrentCheckpoint({ checkpoint }: { checkpoint: TimelineCheckpoint | null }) {
  if (!checkpoint) return <p>当前没有待处理的 checkpoint。</p>;
  return (
    <dl>
      <div><dt>Checkpoint</dt><dd>{checkpoint.milestone_key}</dd></div>
      <div><dt>截止日期</dt><dd>{checkpoint.due_date}</dd></div>
      <div><dt>负责角色</dt><dd>{checkpoint.accountable_role}</dd></div>
      <div><dt>风险状态</dt><dd>{checkpoint.risk_state}</dd></div>
    </dl>
  );
}
