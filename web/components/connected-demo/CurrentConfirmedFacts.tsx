"use client";

import type { ConfirmedFactAdvisor } from "../../lib/collaboration-demo/contracts";
import { presentCode } from "../../lib/presentation/codes";
import { usePresentation } from "../../lib/presentation/context";
import { presentConfirmedFactValue } from "../../lib/presentation/facts";

export function CurrentConfirmedFacts({
  facts,
  caseRevision,
}: {
  facts: readonly ConfirmedFactAdvisor[] | null;
  caseRevision: number;
}) {
  const { locale, copy } = usePresentation();
  return (
    <section className="collaboration-panel confirmed-fact" aria-labelledby="current-confirmed-facts-title">
      <p className="overline">{copy("currentFactsOverline")}</p>
      <h2 id="current-confirmed-facts-title">{copy("currentFactsTitle")}</h2>
      {facts === null ? <p>{copy("currentFactsUnavailable")}</p> : facts.length === 0 ? <p>{copy("currentFactsEmpty")}</p> : (
        <div className="current-confirmed-facts">
          {facts.map((fact) => (
            <dl className="collaboration-facts" key={`${fact.fact_key}-${fact.fact_version}`}>
              <div><dt>{copy("factLabel")}</dt><dd>{presentCode(locale, "factKey", fact.fact_key)}</dd></div>
              <div><dt>{copy("currentValueLabel")}</dt><dd>{presentConfirmedFactValue(locale, fact.fact_key, fact.value)}</dd></div>
              <div><dt>{copy("factAuthorityLabel")}</dt><dd>{copy("factVersionLabel")} {fact.fact_version}</dd></div>
              <div><dt>{copy("caseAuthorityLabel")}</dt><dd>{copy("caseRevisionLabel")} {caseRevision}</dd></div>
            </dl>
          ))}
        </div>
      )}
    </section>
  );
}
