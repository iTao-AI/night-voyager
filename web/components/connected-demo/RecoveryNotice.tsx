"use client";

import type { RecoveryCode } from "../../lib/connected-demo/reducer";
import { presentCode } from "../../lib/presentation/codes";
import { usePresentation } from "../../lib/presentation/context";

export function RecoveryNotice({ code, onReconnect, headingRef }: { code: RecoveryCode; onReconnect: () => void; headingRef?: React.RefObject<HTMLHeadingElement | null> }) {
  const { locale, copy } = usePresentation();
  return (
    <section className="recovery-notice" role="alert" aria-labelledby="recovery-title">
      <h3 id="recovery-title" ref={headingRef} tabIndex={-1}>{copy("recoveryTitle")}</h3>
      <p>{presentCode(locale, "recoveryCode", code)} {copy("recoveryBoundary")}</p>
      <button type="button" onClick={onReconnect}>{copy("recoveryReconnect")}</button>
    </section>
  );
}
