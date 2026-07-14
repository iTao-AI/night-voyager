import type { RecoveryCode } from "../../lib/connected-demo/reducer";

export function RecoveryNotice({ code, onReconnect }: { code: RecoveryCode; onReconnect: () => void }) {
  return (
    <section className="recovery-notice" role="alert" aria-labelledby="recovery-title">
      <h1 id="recovery-title">Recovery required</h1>
      <p>The demo stopped safely ({code}). No mutation or role assumption was made.</p>
      <button type="button" onClick={onReconnect}>Reconnect advisor walkthrough</button>
    </section>
  );
}
