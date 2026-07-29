export function CheckpointAttestationForm({
  disabled,
  onProgress,
  onCompletion,
}: {
  disabled: boolean;
  onProgress(): void;
  onCompletion(): void;
}) {
  return (
    <div aria-label="checkpoint attestation">
      <button disabled={disabled} onClick={onProgress}>记录进行中</button>
      <button disabled={disabled} onClick={onCompletion}>提交完成状态给顾问</button>
    </div>
  );
}
