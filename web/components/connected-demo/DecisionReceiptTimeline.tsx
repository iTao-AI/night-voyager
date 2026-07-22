"use client";

import type { CurrentDecisionBrief } from "../../lib/connected-demo/contracts";
import { presentCode, presentTradeOff } from "../../lib/presentation/codes";
import { usePresentation } from "../../lib/presentation/context";
import { formatCnyRange, formatIsoDate } from "../../lib/presentation/format";

export function DecisionReceiptTimeline({ brief }: { brief: CurrentDecisionBrief }) {
  const { locale, copy } = usePresentation();
  const receipt = brief.receipt;
  const timeline = brief.timeline;
  if (receipt === null || timeline === null) return null;

  return (
    <article className="family-frame decided-frame" aria-labelledby="receipt-title">
      <p className="overline">{copy("receiptOverline")}</p>
      <h1 id="receipt-title">{copy("receiptTitle")}</h1>
      <p>{copy("receiptSummary")}</p>
      <dl className="decision-requirements">
        <div><dt>{copy("acceptedBudgetLabel")}</dt><dd>{formatCnyRange(locale, receipt.accepted_budget_min_minor, receipt.accepted_budget_max_minor, receipt.currency)}</dd></div>
        <div><dt>{copy("acceptedTradeOffLabel")}</dt><dd>{receipt.accepted_trade_offs.map((item) => presentTradeOff(locale, item)).join(", ")}</dd></div>
        <div><dt>{copy("decisionSourceLabel")}</dt><dd>{presentCode(locale, "decisionSource", receipt.source)}</dd></div>
      </dl>
      <h2>{copy("timelineTitle")}</h2>
      <p>{presentCode(locale, "country", timeline.country)} · {timeline.intake} {copy("intakeLabel")}</p>
      <ol className="timeline">
        {timeline.milestones.map((milestone) => (
          <li key={`${milestone.key}-${milestone.due_date}`}>
            <strong>{presentCode(locale, "milestone", milestone.key)}</strong>
            <span>{formatIsoDate(locale, milestone.due_date)}</span>
          </li>
        ))}
      </ol>
    </article>
  );
}
