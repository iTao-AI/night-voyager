"use client";

import type { ConfirmedFactAdvisor } from "../../lib/collaboration-demo/contracts";
import { presentCode } from "../../lib/presentation/codes";
import { usePresentation } from "../../lib/presentation/context";
import { formatCnyRange } from "../../lib/presentation/format";

function budget(value: unknown): value is { preferred_minor: number; hard_ceiling_minor: number; currency: "CNY" } {
  return typeof value === "object" && value !== null
    && "preferred_minor" in value && "hard_ceiling_minor" in value && "currency" in value
    && typeof value.preferred_minor === "number" && typeof value.hard_ceiling_minor === "number"
    && value.currency === "CNY";
}

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
              <div><dt>{copy("currentValueLabel")}</dt><dd>{budget(fact.value) ? formatCnyRange(locale, fact.value.preferred_minor, fact.value.hard_ceiling_minor, fact.value.currency) : copy("statusUnavailable")}</dd></div>
              <div><dt>{copy("factAuthorityLabel")}</dt><dd>{copy("factVersionLabel")} {fact.fact_version}</dd></div>
              <div><dt>{copy("caseAuthorityLabel")}</dt><dd>{copy("caseRevisionLabel")} {caseRevision}</dd></div>
            </dl>
          ))}
        </div>
      )}
    </section>
  );
}
