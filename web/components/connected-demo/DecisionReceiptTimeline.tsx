import type { CurrentDecisionBrief } from "../../lib/connected-demo/contracts";

const amount = new Intl.NumberFormat("en-US");

function record(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function label(value: unknown): string {
  return String(value ?? "").replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());
}

export function DecisionReceiptTimeline({ brief }: { brief: CurrentDecisionBrief }) {
  const receipt = record(brief.receipt);
  const timeline = record(brief.timeline);
  const milestones = Array.isArray(timeline.milestones) ? timeline.milestones.map(record) : [];
  const budgetMin = Number(receipt.accepted_budget_min_minor);
  const budgetMax = Number(receipt.accepted_budget_max_minor);
  const tradeOffs = Array.isArray(receipt.accepted_trade_offs) ? receipt.accepted_trade_offs : [];

  return (
    <article className="family-frame decided-frame" aria-labelledby="receipt-title">
      <p className="overline">Persistent decision trail</p>
      <h1 id="receipt-title">Decision Receipt</h1>
      <p>The family confirmed the Australia route from the reviewed, persisted Brief.</p>
      <dl className="decision-requirements">
        <div><dt>Accepted budget</dt><dd>{amount.format(budgetMin)}–{amount.format(budgetMax)} {String(receipt.currency)}</dd></div>
        <div><dt>Accepted trade-off</dt><dd>{tradeOffs.map(label).join(", ")}</dd></div>
        <div><dt>Decision source</dt><dd>Direct family confirmation</dd></div>
      </dl>
      <h2>Timeline Plan</h2>
      <p>{label(timeline.country)} · {String(timeline.intake)} intake</p>
      <ol className="timeline">
        {milestones.map((milestone) => (
          <li key={`${String(milestone.key)}-${String(milestone.due_date)}`}>
            <strong>{label(milestone.key)}</strong><span>{String(milestone.due_date)}</span>
          </li>
        ))}
      </ol>
    </article>
  );
}
