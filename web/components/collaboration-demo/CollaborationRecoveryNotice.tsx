"use client";

import type { CollaborationErrorCategory } from "../../lib/collaboration-demo/reducer";
import { presentCode } from "../../lib/presentation/codes";
import { usePresentation } from "../../lib/presentation/context";

export function CollaborationRecoveryNotice({ category, onRetry, headingRef }: { category: CollaborationErrorCategory; onRetry: () => void; headingRef?: React.RefObject<HTMLHeadingElement | null> }) {
  const { locale, copy } = usePresentation();
  return (
    <section className="recovery-notice" data-recovery-record="true" role="alert" aria-labelledby="collaboration-recovery-title">
      <h2 id="collaboration-recovery-title" ref={headingRef} tabIndex={-1}>{copy("collaborationRecoveryTitle")}</h2>
      <p>{presentCode(locale, "collaborationError", category)}</p>
      <p>{copy("collaborationRecoveryBoundary")}</p>
      <button className="primary-action workspace-primary-action" data-primary-action="true" data-recovery-action="true" type="button" onClick={onRetry}>{copy("collaborationRecoveryAction")}</button>
    </section>
  );
}
