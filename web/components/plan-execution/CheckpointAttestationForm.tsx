export function CheckpointAttestationForm({
  disabled,
  onProgress,
  onCompletion,
  labels,
}: {
  disabled: boolean;
  onProgress(): void;
  onCompletion(): void;
  labels: { group: string; progress: string; completion: string };
}) {
  return (
    <div aria-label={labels.group}>
      <button disabled={disabled} onClick={onProgress}>{labels.progress}</button>
      <button disabled={disabled} onClick={onCompletion}>{labels.completion}</button>
    </div>
  );
}
