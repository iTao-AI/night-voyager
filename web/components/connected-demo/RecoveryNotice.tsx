"use client";

import type { RecoveryCode } from "../../lib/connected-demo/reducer";
import { presentCode } from "../../lib/presentation/codes";
import { usePresentation } from "../../lib/presentation/context";

export function RecoveryNotice({ code, onReconnect }: { code: RecoveryCode; onReconnect: () => void }) {
  const { locale, copy } = usePresentation();
  return (
    <section className="recovery-notice" role="alert" aria-labelledby="recovery-title">
      <h1 id="recovery-title">{copy("recoveryTitle")}</h1>
      <p>{presentCode(locale, "recoveryCode", code)} {copy("recoveryBoundary")}</p>
      <button type="button" onClick={onReconnect}>{copy("recoveryReconnect")}</button>
    </section>
  );
}
