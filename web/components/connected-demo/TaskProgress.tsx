import type { AdvisorLedger } from "../../lib/connected-demo/contracts";

export function TaskProgress({ ledger }: { ledger: AdvisorLedger }) {
  if (!ledger.task) return null;
  return (
    <details className="technical-details">
      <summary>Task trail</summary>
      <p aria-live="polite">
        Status: <strong>{ledger.task.status}</strong> · attempt {ledger.task.attempt_count}
      </p>
      {ledger.task.public_code ? <p>Public result: {ledger.task.public_code}</p> : null}
    </details>
  );
}
