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
    <div aria-label={labels.group}>
      <button disabled={disabled} onClick={onVerify}>{labels.verify}</button>
      <button disabled={disabled} onClick={onRequestUpdate}>{labels.requestUpdate}</button>
    </div>
  );
}
