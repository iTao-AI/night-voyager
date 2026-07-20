import type { PlanningSkillInspector as Inspector } from "../../lib/skill-inspector/contracts";

const STATUS = {
  not_created: "No planning task created",
  matched: "Pinned execution matched",
  legacy_unpinned: "Legacy task without runtime pin",
} as const;

function operation(value: Inspector["operation"]): string {
  if (value === "generate_planning_run_v1") return "Deterministic planning run";
  if (value === "generate_governed_mixed_planning_run_v1") return "Governed mixed-evidence planning run";
  return "Planning task not created";
}

export function PlanningSkillInspector({ inspector }: { inspector: Inspector }) {
  const adapter = inspector.adapter_id && inspector.adapter_version ? `${inspector.adapter_id}@${inspector.adapter_version}` : "No recorded leaf adapter";
  return (
    <aside className="skill-inspector" aria-labelledby="skill-inspector-title">
      <p className={`status ${inspector.pin_status === "matched" ? "trust" : ""}`}>{STATUS[inspector.pin_status]}</p>
      <details>
        <summary id="skill-inspector-title">Planning Skill inspector</summary>
        <p>This read-only projection comes from the server-owned planning execution record.</p>
        <dl className="inspector-grid">
          <div><dt>Operation</dt><dd>{operation(inspector.operation)}</dd></div>
          <div><dt>Active Skill</dt><dd>{inspector.active_skill_key}@{inspector.active_version}</dd></div>
          <div><dt>Activation</dt><dd>Sequence {inspector.activation_sequence}</dd></div>
          <div><dt>Evaluation</dt><dd>{inspector.evaluator_id}@{inspector.evaluator_version}<br />{inspector.evaluation_dataset_id}@{inspector.evaluation_dataset_version}</dd></div>
          <div><dt>Task request</dt><dd>{inspector.task_request_sha256_prefix ?? "No task digest"}</dd></div>
          <div><dt>Version content</dt><dd>{inspector.version_content_sha256_prefix}</dd></div>
          <div><dt>Runtime binding</dt><dd>{inspector.runtime_binding_sha256_prefix}</dd></div>
          <div><dt>Actual adapter</dt><dd>{adapter}</dd></div>
        </dl>
      </details>
    </aside>
  );
}
