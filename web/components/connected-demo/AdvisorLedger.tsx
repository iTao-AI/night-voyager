import type { AdvisorLedger as Ledger } from "../../lib/connected-demo/contracts";
import { EvidenceDisclosure } from "./EvidenceDisclosure";
import { TaskProgress } from "./TaskProgress";

function actionLabel(phase: Ledger["phase"]): string {
  if (phase === "task-ready") return "Create planning task";
  if (phase === "review-required") return "Approve Australia for family review";
  if (phase === "family-review" || phase === "plan-ready") return "Continue as family";
  return "Task in progress";
}

export function AdvisorLedger({
  ledger,
  onPrimaryAction,
  busy = false,
}: {
  ledger: Ledger;
  onPrimaryAction: () => void;
  busy?: boolean;
}) {
  const routes = ledger.routes ?? [];
  const disabled = busy || ledger.phase === "active-task";
  return (
    <section className="advisor-ledger" aria-labelledby="advisor-ledger-title">
      <div className="section-heading">
        <p className="overline">Advisor Ledger × Global Journey</p>
        <h1 id="advisor-ledger-title">Advisor Ledger</h1>
        <p>Current lifecycle stage: <strong>{ledger.phase}</strong>. Authority comes from the backend projection.</p>
      </div>
      {routes.length ? (
        <div className="table-wrap">
          <table aria-label="Route evidence comparison">
            <thead><tr><th>Route</th><th>Outcome</th><th>Reason</th><th>Action</th></tr></thead>
            <tbody>
              {routes.map((route, index) => {
                const country = String(route.country);
                const blocked = route.eligible === false || route.outcome === "blocked";
                return (
                  <tr key={`${country}-${index}`}>
                    <th scope="row">{country}</th>
                    <td>{String(route.outcome)}</td>
                    <td>{String(route.reason_code)}</td>
                    <td><button type="button" disabled={blocked}>Choose {country[0]?.toUpperCase()}{country.slice(1)}</button></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
      <EvidenceDisclosure evidence={ledger.evidence ?? []} />
      <TaskProgress ledger={ledger} />
      <div className="current-stage">
        <div><h2>{actionLabel(ledger.phase)}</h2><p>One server-authorized primary action is available for this phase.</p></div>
        <button className="primary-action" type="button" disabled={disabled} onClick={onPrimaryAction}>{actionLabel(ledger.phase)}</button>
      </div>
    </section>
  );
}
