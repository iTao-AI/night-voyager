import type { ConfirmedFactProjection } from "../../lib/collaboration-demo/contracts";

function budget(value: unknown): value is { preferred_minor: number | null; hard_ceiling_minor: number | null } { return typeof value === "object" && value !== null && "preferred_minor" in value && "hard_ceiling_minor" in value; }
function cny(minor: number): string { return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(minor / 100); }

export function presentConfirmedFactValue(fact: ConfirmedFactProjection): string {
  if (fact.fact_key === "family.budget" && budget(fact.value) && fact.value.preferred_minor !== null && fact.value.hard_ceiling_minor !== null) {
    return `${cny(fact.value.preferred_minor)}–${cny(fact.value.hard_ceiling_minor)} CNY`;
  }
  if (Array.isArray(fact.value)) return fact.value.map((item) => `${item[0]?.toUpperCase()}${item.slice(1)}`).join(", ");
  if (typeof fact.value === "boolean") return fact.value ? "Yes" : "No";
  if (typeof fact.value === "string") return fact.value;
  return "Current fact unavailable";
}

export function ConfirmedFactSummary({ fact, caseRevision }: { fact: ConfirmedFactProjection; caseRevision: number }) {
  if (fact.fact_key !== "family.budget" || !budget(fact.value) || fact.value.preferred_minor === null || fact.value.hard_ceiling_minor === null) throw new Error("unsupported fact presentation");
  return (
    <section className="collaboration-panel confirmed-fact" aria-labelledby="confirmed-fact-title">
      <p className="overline">Authoritative Case provenance</p>
      <h2 id="confirmed-fact-title">Confirmed family fact</h2>
      <p>{presentConfirmedFactValue(fact)} is now part of the current Case projection.</p>
      <dl className="collaboration-facts">
        <div><dt>Fact authority</dt><dd>Fact version {fact.fact_version}</dd></div>
        <div><dt>Case authority</dt><dd>Case revision {caseRevision}</dd></div>
        <div><dt>Confirmed by</dt><dd>Assigned advisor</dd></div>
      </dl>
      {"reason" in fact ? <p className="advisor-reason"><strong>Recorded reason:</strong> {fact.reason}</p> : null}
    </section>
  );
}
