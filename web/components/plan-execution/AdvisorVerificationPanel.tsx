export function AdvisorVerificationPanel({
  disabled,
  onVerify,
  onRequestUpdate,
}: {
  disabled: boolean;
  onVerify(): void;
  onRequestUpdate(): void;
}) {
  return (
    <div aria-label="advisor verification">
      <button disabled={disabled} onClick={onVerify}>验证并继续</button>
      <button disabled={disabled} onClick={onRequestUpdate}>请求更新</button>
    </div>
  );
}
