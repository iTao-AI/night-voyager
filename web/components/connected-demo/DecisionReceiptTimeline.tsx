import type { CurrentDecisionBrief } from "../../lib/connected-demo/contracts";

export function DecisionReceiptTimeline({ brief }: { brief: CurrentDecisionBrief }) {
  return (
    <article className="family-frame decided-frame" aria-labelledby="receipt-title">
      <p className="overline">Persistent decision trail</p>
      <h1 id="receipt-title">Decision Receipt</h1>
      <pre className="receipt-projection">{JSON.stringify(brief.receipt, null, 2)}</pre>
      <h2>Timeline Plan</h2>
      <pre className="receipt-projection">{JSON.stringify(brief.timeline, null, 2)}</pre>
    </article>
  );
}
