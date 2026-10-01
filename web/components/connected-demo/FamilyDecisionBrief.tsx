"use client";

import { suggestFamilyDecisionDraft, validateFamilyDecisionDraft, type FamilyDecisionDraft } from "../../lib/connected-demo/family-decision";
import type { CurrentDecisionBrief } from "../../lib/connected-demo/contracts";
import { presentCode, presentTradeOff } from "../../lib/presentation/codes";
import { usePresentation } from "../../lib/presentation/context";
import { formatCnyMinor } from "../../lib/presentation/format";

interface FamilyChoiceProps {
  brief: CurrentDecisionBrief;
  draft: FamilyDecisionDraft;
  onDraftChange: (draft: FamilyDecisionDraft) => void;
  confirmed: boolean;
  onConfirm: (confirmed: boolean) => void;
  onSubmit: () => void;
}

export function FamilyDecisionAction({ brief, draft, onDraftChange, confirmed, onConfirm, onSubmit }: FamilyChoiceProps) {
  const { locale, copy } = usePresentation();
  const valid = validateFamilyDecisionDraft(draft, brief).ok;
  const requirements = brief.decision_requirements;
  const suggested = suggestFamilyDecisionDraft(brief);
  return (
    <div className="family-decision-action" data-authority-action="true" data-brief-version={brief.brief_version}>
      <fieldset className="family-budget-fields">
        <legend>{copy("familyBudgetLegend")}</legend>
        <p>{copy("familyBudgetSuggestions").replace("{minimum}", suggested.minimumYuan).replace("{maximum}", suggested.maximumYuan)}</p>
        <div className="budget-input-grid">
          <label>{copy("familyMinimumLabel")}
            <input type="text" inputMode="numeric" value={draft.minimumYuan} onChange={(event) => onDraftChange({ ...draft, minimumYuan: event.target.value })} />
          </label>
          <label>{copy("familyMaximumLabel")}
            <input type="text" inputMode="numeric" value={draft.maximumYuan} onChange={(event) => onDraftChange({ ...draft, maximumYuan: event.target.value })} />
          </label>
        </div>
        <p>{copy("familyBudgetBounds")}</p>
      </fieldset>
      <fieldset className="family-trade-off-fields">
        <legend>{copy("requiredTradeOffLabel")}</legend>
        {requirements.required_trade_offs.map((item) => (
          <label key={item} className="confirmation-summary">
            <input type="checkbox" checked={draft.acknowledgedTradeOffs.includes(item)} onChange={(event) => onDraftChange({ ...draft, acknowledgedTradeOffs: event.target.checked ? [...draft.acknowledgedTradeOffs, item] : draft.acknowledgedTradeOffs.filter((selected) => selected !== item) })} />
            {copy("familyTradeOffAcceptance").replace("{tradeOff}", presentTradeOff(locale, item))}
          </label>
        ))}
      </fieldset>
      <label className="confirmation-summary">
        <input type="checkbox" checked={confirmed} onChange={(event) => onConfirm(event.target.checked)} />
        {copy("familyConfirmLabel")}
      </label>
      <button className="primary-action workspace-primary-action" data-primary-action="true" type="button" disabled={!confirmed || !valid} onClick={onSubmit}>{copy("continueFamilyDecisionAction")}</button>
      {!valid ? <p className="disabled-reason" role="status">{copy("familyChoicesRequired")}</p> : !confirmed ? <p className="disabled-reason">{copy("familyConfirmationRequired")}</p> : null}
    </div>
  );
}

export function FamilyDecisionBrief({
  brief,
  draft,
  onDraftChange,
  confirmed,
  onConfirm,
  onSubmit,
  renderAction = true,
}: FamilyChoiceProps & { renderAction?: boolean }) {
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
      {renderAction ? <FamilyDecisionAction brief={brief} draft={draft} onDraftChange={onDraftChange} confirmed={confirmed} onConfirm={onConfirm} onSubmit={onSubmit} /> : null}
    </article>
  );
}
