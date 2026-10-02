import { parseWholeYuan } from "../collaboration-demo/budget";
import type { CurrentDecisionBrief, FamilyDecisionBody } from "./contracts";

export interface FamilyDecisionDraft {
  minimumYuan: string;
  maximumYuan: string;
  acknowledgedTradeOffs: "budget_elasticity"[];
}

/** A submitted, explicitly acknowledged body; never an unsubmitted draft or authority. */
export interface SubmittedFamilyIntent {
  schema_version: 1;
  briefId: string;
  body: FamilyDecisionBody;
}

export function suggestFamilyDecisionDraft(brief: CurrentDecisionBrief): FamilyDecisionDraft {
  return {
    minimumYuan: String(Math.floor(brief.decision_requirements.pinned_cost_minor / 100)),
    maximumYuan: String(Math.floor(brief.decision_requirements.hard_ceiling_minor / 100)),
    acknowledgedTradeOffs: [],
  };
}

export function validateFamilyDecisionDraft(
  draft: FamilyDecisionDraft,
  brief: CurrentDecisionBrief,
): { ok: true; body: FamilyDecisionBody } | { ok: false } {
  const minimum = parseWholeYuan(draft.minimumYuan, "preferred");
  const maximum = parseWholeYuan(draft.maximumYuan, "hard_ceiling");
  const requirements = brief.decision_requirements;
  if (!minimum.ok || !maximum.ok || requirements.currency !== "CNY"
    || minimum.minor > maximum.minor || minimum.minor > requirements.pinned_cost_minor
    || maximum.minor < requirements.pinned_cost_minor || maximum.minor > requirements.hard_ceiling_minor
    || draft.acknowledgedTradeOffs.length !== requirements.required_trade_offs.length
    || !requirements.required_trade_offs.every((item) => draft.acknowledgedTradeOffs.includes(item))) return { ok: false };
  return { ok: true, body: {
    schema_version: 1,
    expected_brief_version: brief.brief_version,
    selected_route_id: requirements.eligible_route_id,
    accepted_budget_min_minor: minimum.minor,
    accepted_budget_max_minor: maximum.minor,
    currency: requirements.currency,
    accepted_trade_offs: [draft.acknowledgedTradeOffs[0]],
  } };
}

export function familyDraftFromIntent(intent: SubmittedFamilyIntent): FamilyDecisionDraft {
  return {
    minimumYuan: String(intent.body.accepted_budget_min_minor / 100),
    maximumYuan: String(intent.body.accepted_budget_max_minor / 100),
    acknowledgedTradeOffs: [...intent.body.accepted_trade_offs],
  };
}

export function familyIntentMatchesBrief(intent: SubmittedFamilyIntent, brief: CurrentDecisionBrief): boolean {
  const validated = validateFamilyDecisionDraft(familyDraftFromIntent(intent), brief);
  return intent.briefId === brief.brief_id && intent.body.expected_brief_version === brief.brief_version
    && validated.ok && intent.body.selected_route_id === validated.body.selected_route_id
    && intent.body.currency === validated.body.currency;
}

export function isSubmittedFamilyIntent(value: unknown): value is SubmittedFamilyIntent {
  const object = (item: unknown): item is Record<string, unknown> => typeof item === "object" && item !== null && !Array.isArray(item);
  const exact = (item: Record<string, unknown>, keys: string[]) => Object.keys(item).length === keys.length && keys.every((key) => Object.hasOwn(item, key));
  const uuid = (item: unknown) => typeof item === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(item);
  const positive = (item: unknown): item is number => Number.isSafeInteger(item) && Number(item) > 0;
  if (!object(value) || !exact(value, ["schema_version", "briefId", "body"]) || value.schema_version !== 1 || !uuid(value.briefId) || !object(value.body)) return false;
  const body = value.body;
  return exact(body, ["schema_version", "expected_brief_version", "selected_route_id", "accepted_budget_min_minor", "accepted_budget_max_minor", "currency", "accepted_trade_offs"])
    && body.schema_version === 1 && positive(body.expected_brief_version) && uuid(body.selected_route_id)
    && positive(body.accepted_budget_min_minor) && positive(body.accepted_budget_max_minor)
    && body.accepted_budget_min_minor % 100 === 0 && body.accepted_budget_max_minor % 100 === 0
    && body.accepted_budget_min_minor <= body.accepted_budget_max_minor && body.currency === "CNY"
    && JSON.stringify(body.accepted_trade_offs) === '["budget_elasticity"]';
}
