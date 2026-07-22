"use client";

import type { PlanningSkillInspector as Inspector } from "../../lib/skill-inspector/contracts";
import { presentCode } from "../../lib/presentation/codes";
import { usePresentation } from "../../lib/presentation/context";

function operation(value: Inspector["operation"], unavailable: string, empty: string): string {
  if (value === null) return empty;
  if (value === "generate_planning_run_v1" || value === "generate_governed_mixed_planning_run_v1") return value;
  return unavailable;
}

export function PlanningSkillInspector({ inspector }: { inspector: Inspector }) {
  const { locale, copy } = usePresentation();
  // The localized disclosure describes the same server-owned planning execution record.
  const adapter = inspector.adapter_id && inspector.adapter_version
    ? `${inspector.adapter_id}@${inspector.adapter_version}`
    : copy("skillNoAdapter");
  return (
    <aside className="skill-inspector" aria-labelledby="skill-inspector-title">
      <p className={`status ${inspector.pin_status === "matched" ? "trust" : ""}`}>{presentCode(locale, "skillPinStatus", inspector.pin_status)}</p>
      <details>
        <summary id="skill-inspector-title">{copy("skillInspectorTitle")}</summary>
        <p>{copy("skillInspectorBody")}</p>
        <dl className="inspector-grid">
          <div><dt>{copy("skillOperationLabel")}</dt><dd>{operation(inspector.operation, copy("statusUnavailable"), copy("skillNoOperation"))}</dd></div>
          <div><dt>{copy("skillActiveLabel")}</dt><dd>{inspector.active_skill_key}@{inspector.active_version}</dd></div>
          <div><dt>{copy("skillActivationLabel")}</dt><dd>{copy("skillSequenceLabel")} {inspector.activation_sequence}</dd></div>
          <div><dt>{copy("skillEvaluationLabel")}</dt><dd>{inspector.evaluator_id}@{inspector.evaluator_version}<br />{inspector.evaluation_dataset_id}@{inspector.evaluation_dataset_version}</dd></div>
          <div><dt>{copy("skillTaskRequestLabel")}</dt><dd>{inspector.task_request_sha256_prefix ?? copy("skillNoTaskDigest")}</dd></div>
          <div><dt>{copy("skillVersionContentLabel")}</dt><dd>{inspector.version_content_sha256_prefix}</dd></div>
          <div><dt>{copy("skillRuntimeBindingLabel")}</dt><dd>{inspector.runtime_binding_sha256_prefix}</dd></div>
          <div><dt>{copy("skillAdapterLabel")}</dt><dd>{adapter}</dd></div>
        </dl>
      </details>
    </aside>
  );
}
