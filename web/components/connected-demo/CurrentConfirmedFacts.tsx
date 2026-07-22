import type { ConfirmedFactAdvisor } from "../../lib/collaboration-demo/contracts";
import { presentConfirmedFactValue } from "../collaboration-demo/ConfirmedFactSummary";

export function CurrentConfirmedFacts({
  facts,
  caseRevision,
}: {
  facts: readonly ConfirmedFactAdvisor[] | null;
  caseRevision: number;
}) {
  return (
    <section className="collaboration-panel confirmed-fact" aria-labelledby="current-confirmed-facts-title">
      <p className="overline">Current server-owned Case authority</p>
      <h2 id="current-confirmed-facts-title">Current confirmed Case facts</h2>
      {facts === null ? <p>Current confirmed facts are unavailable until the server projection is refreshed.</p> : facts.length === 0 ? <p>No current confirmed facts are projected for this Case revision.</p> : (
        <div className="current-confirmed-facts">
          {facts.map((fact) => (
            <dl className="collaboration-facts" key={`${fact.fact_key}-${fact.fact_version}`}>
              <div><dt>Fact</dt><dd>{fact.fact_key}</dd></div>
              <div><dt>Current value</dt><dd>{presentConfirmedFactValue(fact)}</dd></div>
              <div><dt>Fact authority</dt><dd>Fact version {fact.fact_version}</dd></div>
              <div><dt>Case authority</dt><dd>Case revision {caseRevision}</dd></div>
            </dl>
          ))}
        </div>
      )}
    </section>
  );
}
