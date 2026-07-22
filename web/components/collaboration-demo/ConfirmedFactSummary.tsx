"use client";

import type { ConfirmedFactProjection } from "../../lib/collaboration-demo/contracts";
import { usePresentation } from "../../lib/presentation/context";
import { formatCnyRange } from "../../lib/presentation/format";

function budget(value: unknown): value is { preferred_minor: number; hard_ceiling_minor: number; currency: "CNY" } {
  return typeof value === "object" && value !== null
    && "preferred_minor" in value && "hard_ceiling_minor" in value && "currency" in value
    && typeof value.preferred_minor === "number" && typeof value.hard_ceiling_minor === "number"
    && value.currency === "CNY";
}

export function ConfirmedFactSummary({ fact, caseRevision }: { fact: ConfirmedFactProjection; caseRevision: number }) {
  const { locale, copy } = usePresentation();
  const value = fact.fact_key === "family.budget" && budget(fact.value)
    ? formatCnyRange(locale, fact.value.preferred_minor, fact.value.hard_ceiling_minor, fact.value.currency)
    : copy("statusUnavailable");
  return (
    <section className="collaboration-panel confirmed-fact" aria-labelledby="confirmed-fact-title">
      <p className="overline">{copy("confirmedFactOverline")}</p>
      <h2 id="confirmed-fact-title">{copy("confirmedFactTitle")}</h2>
      <p><strong>{value}</strong> {copy("confirmedFactProjection")}</p>
      <dl className="collaboration-facts">
        <div><dt>{copy("factAuthorityLabel")}</dt><dd>{copy("factVersionLabel")} {fact.fact_version}</dd></div>
        <div><dt>{copy("caseAuthorityLabel")}</dt><dd>{copy("caseRevisionLabel")} {caseRevision}</dd></div>
        <div><dt>{copy("confirmedByLabel")}</dt><dd>{copy("assignedAdvisor")}</dd></div>
      </dl>
      {"reason" in fact ? <p className="advisor-reason"><strong>{copy("recordedReasonLabel")}:</strong> {fact.reason}</p> : null}
    </section>
  );
}
