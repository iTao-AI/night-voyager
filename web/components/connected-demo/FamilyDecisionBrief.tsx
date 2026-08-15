"use client";

import type { CurrentDecisionBrief } from "../../lib/connected-demo/contracts";
import { presentCode, presentTradeOff } from "../../lib/presentation/codes";
import { usePresentation } from "../../lib/presentation/context";
import { formatCnyMinor } from "../../lib/presentation/format";

export function FamilyDecisionAction({
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
  const { copy } = usePresentation();
  return (
    <div className="family-decision-action" data-authority-action="true" data-brief-version={brief.brief_version}>
      <label className="confirmation-summary">
        <input type="checkbox" checked={confirmed} onChange={(event) => onConfirm(event.target.checked)} />
        {copy("familyConfirmLabel")}
      </label>
      <button className="primary-action workspace-primary-action" data-primary-action="true" type="button" disabled={!confirmed} onClick={onSubmit}>{copy("continueFamilyDecisionAction")}</button>
      {!confirmed ? <p className="disabled-reason">{copy("familyConfirmationRequired")}</p> : null}
    </div>
  );
}

export function FamilyDecisionBrief({
  brief,
  confirmed,
  onConfirm,
  onSubmit,
  renderAction = true,
}: {
  brief: CurrentDecisionBrief;
  confirmed: boolean;
  onConfirm: (confirmed: boolean) => void;
  onSubmit: () => void;
  renderAction?: boolean;
}) {
  const { locale, copy } = usePresentation();
  const requirements = brief.decision_requirements;
  return (
    <article className="family-frame" aria-labelledby="family-brief-title">
      <p className="overline">{copy("familyBriefOverline")}</p>
      <h3 id="family-brief-title">{copy("familyBriefTitle")}</h3>
      <p className="role-status">{copy("activeRoleLabel")}: {presentCode(locale, "role", "parent")}</p>
      <p>{copy("parentRoleAuthority")}</p>
      <p>{copy("familyBriefOutcome")}</p>
      <p className="family-revision-context">
        <strong>{copy("currentCaseRevisionLabel")} {brief.revision_context.current_case_revision}</strong>
        <span>
          {copy(brief.revision_context.planning_version === "revised"
            ? "familyRevisionVersionRevised"
            : "familyRevisionVersionInitial")}
        </span>
        <span>
          {copy(brief.revision_context.advisor_authorization === "renewed_for_current_revision"
            ? "familyAuthorizationRenewed"
            : "familyAuthorizationInitial")}
        </span>
      </p>
      <dl className="decision-requirements">
        <div><dt>{copy("pinnedCostLabel")}</dt><dd>{formatCnyMinor(locale, requirements.pinned_cost_minor, requirements.currency)}</dd></div>
        <div><dt>{copy("hardCeilingLabel")}</dt><dd>{formatCnyMinor(locale, requirements.hard_ceiling_minor, requirements.currency)}</dd></div>
        <div><dt>{copy("requiredTradeOffLabel")}</dt><dd>{requirements.required_trade_offs.map((item) => presentTradeOff(locale, item)).join(", ")}</dd></div>
      </dl>
      {renderAction ? <FamilyDecisionAction brief={brief} confirmed={confirmed} onConfirm={onConfirm} onSubmit={onSubmit} /> : null}
    </article>
  );
}
