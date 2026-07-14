import type { CurrentDecisionBrief } from "../../lib/connected-demo/contracts";
import { formatCnyMinor, presentTradeOff } from "../../lib/connected-demo/presentation";

export function FamilyDecisionBrief({
  brief,
  confirmed,
  onConfirm,
  onSubmit,
}: {
  brief: CurrentDecisionBrief;
  confirmed: boolean;
  onConfirm: (confirmed: boolean) => void;
  onSubmit: () => void;
}) {
  const requirements = brief.decision_requirements;
  return (
    <article className="family-frame" aria-labelledby="family-brief-title">
      <p className="overline">Family-safe persisted projection</p>
      <h1 id="family-brief-title">Family Decision Brief</h1>
      <p>Australia is the eligible route selected by the reviewed Brief.</p>
      <dl className="decision-requirements">
        <div><dt>Pinned Australia cost</dt><dd>{formatCnyMinor(requirements.pinned_cost_minor, requirements.currency)}</dd></div>
        <div><dt>Hard ceiling</dt><dd>{formatCnyMinor(requirements.hard_ceiling_minor, requirements.currency)}</dd></div>
        <div><dt>Required trade-off</dt><dd>{requirements.required_trade_offs.map(presentTradeOff).join(", ")}</dd></div>
      </dl>
      <label className="confirmation-summary">
        <input type="checkbox" checked={confirmed} onChange={(event) => onConfirm(event.target.checked)} />
        I confirm this server-derived CNY range and Budget flexibility trade-off.
      </label>
      <button type="button" disabled={!confirmed} onClick={onSubmit}>Confirm Australia route</button>
      {!confirmed ? <p className="disabled-reason">Explicit family confirmation is required.</p> : null}
    </article>
  );
}
