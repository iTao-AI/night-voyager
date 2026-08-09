export function AdvisorVerificationPanel({
  disabled,
  onVerify,
  onRequestUpdate,
  labels,
}: {
  disabled: boolean;
  onVerify(): void;
  onRequestUpdate(): void;
  labels: { group: string; verify: string; requestUpdate: string };
}) {
  return (
    <div className="execution-action-row" role="group" aria-label={labels.group}>
      <button className="execution-primary-action" data-primary-action="true" disabled={disabled} onClick={onVerify}>
        {labels.verify}
      </button>
      <button className="execution-secondary-action" disabled={disabled} onClick={onRequestUpdate}>
        {labels.requestUpdate}
      </button>
    </div>
  );
}
