import type { CollaborationErrorCategory } from "../../lib/collaboration-demo/reducer";

const COPY: Record<CollaborationErrorCategory, string> = {
  stale: "The proposal no longer matches the current Case revision.",
  expired_or_terminal: "The proposal is expired or already has a terminal decision.",
  active_task_blocked: "An active planning task blocks publication of a new Case revision.",
  unsafe_or_unsupported: "The message, fact, or retry does not match the approved collaboration contract.",
  wrong_role_or_not_found: "This role cannot read the requested collaboration authority.",
  session_recovery_required: "The same-tab session must be re-established before continuing.",
  transport_unavailable_or_timeout: "The authoritative service is unavailable or did not respond before the bounded deadline.",
};

export function CollaborationRecoveryNotice({ category, onRetry, headingRef }: { category: CollaborationErrorCategory; onRetry: () => void; headingRef?: React.RefObject<HTMLHeadingElement | null> }) {
  return (
    <section className="recovery-notice" role="alert" aria-labelledby="collaboration-recovery-title">
      <h1 id="collaboration-recovery-title" ref={headingRef} tabIndex={-1}>Collaboration paused safely</h1>
      <p>{COPY[category]}</p>
      <p>No message, proposal, role, or Case authority was inferred locally.</p>
      <button type="button" onClick={onRetry}>Reload collaboration authority</button>
    </section>
  );
}
