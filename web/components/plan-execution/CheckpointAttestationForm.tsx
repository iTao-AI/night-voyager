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
    <div aria-label={labels.group}>
      <button disabled={disabled} onClick={onProgress}>{labels.progress}</button>
      <button disabled={disabled} onClick={onCompletion}>{labels.completion}</button>
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
      <button disabled={disabled} onClick={() => onBlocked(reason)}>{labels.blocked}</button>
    </div>
  );
}
