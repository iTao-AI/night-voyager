"use client";

import type { RecoveryCode } from "../../lib/connected-demo/reducer";
import { presentCode } from "../../lib/presentation/codes";
import { usePresentation } from "../../lib/presentation/context";

export function RecoveryAction({ onReconnect }: { onReconnect: () => void }) {
  const { copy } = usePresentation();
  return <button className="primary-action workspace-primary-action" data-primary-action="true" data-recovery-action="true" type="button" onClick={onReconnect}>{copy("recoveryReconnect")}</button>;
}

export function RecoveryNotice({ code, onReconnect, headingRef, renderAction = true }: { code: RecoveryCode; onReconnect: () => void; headingRef?: React.RefObject<HTMLHeadingElement | null>; renderAction?: boolean }) {
  const { locale, copy } = usePresentation();
  return (
    <section className="recovery-notice" data-recovery-record="true" role="alert" aria-labelledby="recovery-title">
      <h3 id="recovery-title" ref={headingRef} tabIndex={-1}>{copy("recoveryTitle")}</h3>
      <p>{presentCode(locale, "recoveryCode", code)} {copy("recoveryBoundary")}</p>
      {renderAction ? <RecoveryAction onReconnect={onReconnect} /> : null}
    </section>
  );
}
