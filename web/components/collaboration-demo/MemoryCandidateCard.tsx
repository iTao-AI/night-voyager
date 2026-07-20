import type { BudgetValue, MemoryCandidateProjection } from "../../lib/collaboration-demo/contracts";

function budget(value: unknown): value is BudgetValue { return typeof value === "object" && value !== null && "currency" in value; }
function cny(minor: number): string { return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(minor / 100); }

export function MemoryCandidateCard({ candidate }: { candidate: MemoryCandidateProjection }) {
  if (candidate.fact_key !== "family.budget" || !budget(candidate.value) || candidate.value.preferred_minor === null || candidate.value.hard_ceiling_minor === null) throw new Error("unsupported proposal presentation");
  const status = candidate.state === "pending" ? "Pending advisor confirmation" : candidate.state === "confirmed" ? "Confirmed by assigned advisor" : candidate.state === "stale" ? "Needs a current Case revision" : candidate.state === "expired" ? "Proposal expired" : "Proposal rejected";
  const advisor = "candidate_id" in candidate ? candidate : null;
  return (
    <section className="collaboration-panel candidate-card" aria-labelledby="candidate-title">
      <p className="overline">Structured participant proposal</p>
      <h2 id="candidate-title">Budget proposal</h2>
      <p className={`status ${candidate.state === "confirmed" ? "trust" : ""}`}>{status}</p>
      <dl className="collaboration-facts">
        <div><dt>Program budget</dt><dd>{cny(candidate.value.preferred_minor)}–{cny(candidate.value.hard_ceiling_minor)} CNY</dd></div>
        <div><dt>Source</dt><dd>Parent-authored message{advisor ? ` ${advisor.source_message_sequence_no}` : ""}</dd></div>
        {advisor ? <div><dt>Pinned Case revision</dt><dd>{advisor.case_revision}</dd></div> : null}
      </dl>
      {advisor?.reason ? <p className="advisor-reason"><strong>Advisor reason:</strong> {advisor.reason}</p> : null}
    </section>
  );
}
