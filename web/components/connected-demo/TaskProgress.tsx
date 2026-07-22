"use client";

import type { AdvisorLedger } from "../../lib/connected-demo/contracts";
import { presentCode } from "../../lib/presentation/codes";
import { usePresentation } from "../../lib/presentation/context";

export function TaskProgress({ ledger }: { ledger: AdvisorLedger }) {
  const { locale, copy } = usePresentation();
  if (!ledger.task) return null;
  return (
    <div className="task-progress">
      <p role="status" aria-live="polite" aria-atomic="true">
        {copy("taskStatusLabel")}: <strong>{presentCode(locale, "taskStatus", ledger.task.status)}</strong> · {copy("taskAttemptLabel")} {ledger.task.attempt_count}
      </p>
      <details className="technical-details">
        <summary>{copy("taskTrailSummary")}</summary>
        {ledger.task.public_code
          ? <p>{copy("taskPublicResult")}: {presentCode(locale, "publicCode", ledger.task.public_code)}</p>
          : <p>{copy("taskDurablePending")}</p>}
      </details>
    </div>
  );
}
