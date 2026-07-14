import type { CurrentDecisionBrief } from "../../lib/connected-demo/contracts";
import { formatCnyRange, presentTradeOff } from "../../lib/connected-demo/presentation";

const COUNTRY_COPY = new Map<string, string>([
  ["australia", "Australia"],
  ["japan", "Japan"],
  ["malaysia", "Malaysia"],
]);

const MILESTONE_COPY = new Map<string, string>([
  ["documents", "Documents"],
  ["application", "Application"],
  ["visa", "Visa"],
  ["arrival", "Arrival"],
]);

function presentClosed(code: unknown, copy: ReadonlyMap<string, string>): string {
  if (typeof code !== "string") throw new Error("unsupported_presentation_code");
  const value = copy.get(code);
  if (value === undefined) throw new Error("unsupported_presentation_code");
  return value;
}

export function DecisionReceiptTimeline({ brief }: { brief: CurrentDecisionBrief }) {
  const receipt = brief.receipt;
  const timeline = brief.timeline;
  if (receipt === null || timeline === null) throw new Error("unsupported_presentation_code");

  return (
    <article className="family-frame decided-frame" aria-labelledby="receipt-title">
      <p className="overline">Persistent decision trail</p>
      <h1 id="receipt-title">Decision Receipt</h1>
      <p>The family confirmed the Australia route from the reviewed, persisted Brief.</p>
      <dl className="decision-requirements">
        <div><dt>Accepted budget</dt><dd>{formatCnyRange(receipt.accepted_budget_min_minor, receipt.accepted_budget_max_minor, receipt.currency)}</dd></div>
        <div><dt>Accepted trade-off</dt><dd>{receipt.accepted_trade_offs.map(presentTradeOff).join(", ")}</dd></div>
        <div><dt>Decision source</dt><dd>Direct family confirmation</dd></div>
      </dl>
      <h2>Timeline Plan</h2>
      <p>{presentClosed(timeline.country, COUNTRY_COPY)} · {timeline.intake} intake</p>
      <ol className="timeline">
        {timeline.milestones.map((milestone) => (
          <li key={`${milestone.key}-${milestone.due_date}`}>
            <strong>{presentClosed(milestone.key, MILESTONE_COPY)}</strong><span>{milestone.due_date}</span>
          </li>
        ))}
      </ol>
    </article>
  );
}
