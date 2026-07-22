"use client";

import type { BudgetValue, MemoryCandidateProjection } from "../../lib/collaboration-demo/contracts";
import { presentCode } from "../../lib/presentation/codes";
import { usePresentation } from "../../lib/presentation/context";
import { formatCnyRange } from "../../lib/presentation/format";

function budget(value: unknown): value is BudgetValue {
  return typeof value === "object" && value !== null && "currency" in value
    && "preferred_minor" in value && "hard_ceiling_minor" in value;
}

export function MemoryCandidateCard({ candidate }: { candidate: MemoryCandidateProjection }) {
  const { locale, copy } = usePresentation();
  const advisor = "candidate_id" in candidate ? candidate : null;
  const budgetValue = candidate.fact_key === "family.budget" && budget(candidate.value)
    ? formatCnyRange(locale, candidate.value.preferred_minor, candidate.value.hard_ceiling_minor, candidate.value.currency)
    : copy("statusUnavailable");
  return (
    <section className="collaboration-panel candidate-card" aria-labelledby="candidate-title">
      <p className="overline">{copy("candidateOverline")}</p>
      <h2 id="candidate-title">{copy("candidateTitle")}</h2>
      <p className={`status ${candidate.state === "confirmed" ? "trust" : ""}`}>{presentCode(locale, "candidateState", candidate.state)}</p>
      <dl className="collaboration-facts">
        <div><dt>{copy("candidateBudgetLabel")}</dt><dd>{budgetValue}</dd></div>
        <div><dt>{copy("candidateSourceLabel")}</dt><dd>{copy("candidateParentMessage")}{advisor ? ` ${advisor.source_message_sequence_no}` : ""}</dd></div>
        {advisor ? <div><dt>{copy("candidatePinnedRevision")}</dt><dd>{advisor.case_revision}</dd></div> : null}
      </dl>
      {advisor?.reason ? <p className="advisor-reason"><strong>{copy("candidateAdvisorReason")}:</strong> {advisor.reason}</p> : null}
    </section>
  );
}
