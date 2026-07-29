export function ExecutionRecoveryNotice({
  sessionChanged,
  disabled,
  onRecover,
  labels,
}: {
  sessionChanged: boolean;
  disabled: boolean;
  onRecover(): void;
  labels: { sessionChanged: string; recoverable: string; recover: string };
}) {
  return (
    <div role="status" aria-live="polite">
      <p>{sessionChanged ? labels.sessionChanged : labels.recoverable}</p>
      <button disabled={disabled} onClick={onRecover}>{labels.recover}</button>
    </div>
  );
}
