import type { AdvisorLedger } from "../../lib/connected-demo/contracts";

export function TaskProgress({ ledger }: { ledger: AdvisorLedger }) {
  if (!ledger.task) return null;
  return (
    <div className="task-progress">
      <p role="status" aria-live="polite" aria-atomic="true">
        Status: <strong>{ledger.task.status}</strong> · attempt {ledger.task.attempt_count}
      </p>
      <details className="technical-details">
        <summary>Task trail</summary>
        {ledger.task.public_code ? <p>Public result: {ledger.task.public_code}</p> : <p>Durable task details remain available while processing.</p>}
      </details>
    </div>
  );
}
