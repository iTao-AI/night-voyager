"use client";

import type { CurrentDecisionBrief } from "../../lib/connected-demo/contracts";
import { presentTradeOff } from "../../lib/presentation/codes";
import { usePresentation } from "../../lib/presentation/context";
import { formatCnyMinor } from "../../lib/presentation/format";

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
  const { locale, copy } = usePresentation();
  const requirements = brief.decision_requirements;
  return (
    <article className="family-frame" aria-labelledby="family-brief-title">
      <p className="overline">{copy("familyBriefOverline")}</p>
      <h1 id="family-brief-title">{copy("familyBriefTitle")}</h1>
      <p>{copy("familyBriefOutcome")}</p>
      <dl className="decision-requirements">
        <div><dt>{copy("pinnedCostLabel")}</dt><dd>{formatCnyMinor(locale, requirements.pinned_cost_minor, requirements.currency)}</dd></div>
        <div><dt>{copy("hardCeilingLabel")}</dt><dd>{formatCnyMinor(locale, requirements.hard_ceiling_minor, requirements.currency)}</dd></div>
        <div><dt>{copy("requiredTradeOffLabel")}</dt><dd>{requirements.required_trade_offs.map((item) => presentTradeOff(locale, item)).join(", ")}</dd></div>
      </dl>
      <label className="confirmation-summary">
        <input type="checkbox" checked={confirmed} onChange={(event) => onConfirm(event.target.checked)} />
        {copy("familyConfirmLabel")}
      </label>
      <button type="button" disabled={!confirmed} onClick={onSubmit}>{copy("familyConfirmAction")}</button>
      {!confirmed ? <p className="disabled-reason">{copy("familyConfirmationRequired")}</p> : null}
    </article>
  );
}
