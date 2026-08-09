import { useState } from "react";

export function CheckpointAttestationForm({
  disabled,
  onProgress,
  onCompletion,
  onBlocked,
  labels,
}: {
  disabled: boolean;
  onProgress(): void;
  onCompletion(): void;
  onBlocked(reason: "missing_required_input" | "external_dependency_unavailable" | "deadline_at_risk"): void;
  labels: {
    group: string; progress: string; completion: string; blocked: string;
    blockedReason: string; missingInput: string; externalUnavailable: string; deadlineRisk: string;
  };
}) {
  const [reason, setReason] = useState<"missing_required_input" | "external_dependency_unavailable" | "deadline_at_risk">("missing_required_input");
  return (
    <div className="checkpoint-attestation" role="group" aria-label={labels.group}>
      <div className="execution-action-row">
        <button className="execution-primary-action" data-primary-action="true" disabled={disabled} onClick={onCompletion}>
          {labels.completion}
        </button>
        <button className="execution-secondary-action" disabled={disabled} onClick={onProgress}>
          {labels.progress}
        </button>
      </div>
      <div className="execution-blocker-row">
        <label>
        {labels.blockedReason}
        <select
          disabled={disabled}
          value={reason}
          onChange={(event) => setReason(event.target.value as typeof reason)}
        >
          <option value="missing_required_input">{labels.missingInput}</option>
          <option value="external_dependency_unavailable">{labels.externalUnavailable}</option>
          <option value="deadline_at_risk">{labels.deadlineRisk}</option>
        </select>
        </label>
        <button
          className="execution-danger-action"
          disabled={disabled}
          onClick={() => onBlocked(reason)}
        >
          {labels.blocked}
        </button>
      </div>
    </div>
  );
}
