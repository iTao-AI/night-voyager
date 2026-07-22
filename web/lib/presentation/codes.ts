import { getPresentationCopy, type PresentationCopyKey } from "./catalog";
import type { PresentationLocale } from "./locales";

export const PRESENTATION_CODE_VALUES = {
  role: ["advisor", "student", "parent"],
  country: ["australia", "japan", "malaysia"],
  demoPhase: ["task-ready", "active-task", "review-required", "family-review", "plan-ready", "terminal-task-failure"],
  taskStatus: ["preparing", "needs_advisor_review", "ready", "needs_evidence", "timed_out", "failed", "cancelled", "outdated"],
  routeOutcome: ["recommended_with_condition", "conditional", "blocked"],
  routeReason: ["complete_cost_and_fx_within_boundary", "synthetic_high_risk_alternative", "direct_program_fit_evidence_absent"],
  tradeOff: ["budget_elasticity"],
  candidateState: ["pending", "stale", "expired", "confirmed", "rejected"],
  collaborationError: ["stale", "expired_or_terminal", "active_task_blocked", "unsafe_or_unsupported", "wrong_role_or_not_found", "session_recovery_required", "transport_unavailable_or_timeout"],
  skillPinStatus: ["not_created", "matched", "legacy_unpinned"],
  evidenceRisk: ["optional", "stale", "unverified"],
  riskTolerance: ["low", "medium", "high"],
  decisionSource: ["direct", "family_consultation"],
  recoveryCode: ["invalid_transition", "session_expired", "session_recovery_required", "stale_conflict", "transport_failure"],
  evidenceClaim: ["australia_program_fit", "japan_program_fit", "malaysia_program_fit", "australia_tuition", "australia_living_cost", "australia_fx", "australia_ranking", "japan_tuition", "japan_living_cost", "japan_fx", "japan_ranking", "malaysia_tuition", "malaysia_living_cost", "malaysia_fx", "malaysia_ranking"],
  knownGap: ["japan_gap", "malaysia_gap", "applicant_eligibility", "intake_availability"],
  milestone: ["documents", "application", "visa", "arrival"],
  factKey: ["family.budget", "student.intended_field", "student.preferred_countries", "student.intake", "family.risk_tolerance", "family.japan_risk_accepted"],
  publicCode: ["cancelled", "lease_expired", "required_evidence_gap", "deadline_exceeded", "transport_interrupted", "transient_unavailable"],
} as const;

export type PresentationCodeKind = keyof typeof PRESENTATION_CODE_VALUES;
type CodeValue<Kind extends PresentationCodeKind> =
  (typeof PRESENTATION_CODE_VALUES)[Kind][number];
type CodeCopyKeys = {
  [Kind in PresentationCodeKind]: Record<CodeValue<Kind>, PresentationCopyKey>;
};

const CODE_COPY_KEYS = {
  role: { advisor: "roleAdvisor", student: "roleStudent", parent: "roleParent" },
  country: { australia: "countryAustralia", japan: "countryJapan", malaysia: "countryMalaysia" },
  demoPhase: {
    "task-ready": "phaseTaskReady",
    "active-task": "phaseActiveTask",
    "review-required": "phaseReviewRequired",
    "family-review": "phaseFamilyReview",
    "plan-ready": "phasePlanReady",
    "terminal-task-failure": "phaseTerminalTaskFailure",
  },
  taskStatus: {
    preparing: "taskPreparing",
    needs_advisor_review: "taskNeedsAdvisorReview",
    ready: "taskReady",
    needs_evidence: "taskNeedsEvidence",
    timed_out: "taskTimedOut",
    failed: "taskFailed",
    cancelled: "taskCancelled",
    outdated: "taskOutdated",
  },
  routeOutcome: {
    recommended_with_condition: "routeRecommendedWithCondition",
    conditional: "routeConditional",
    blocked: "routeBlocked",
  },
  routeReason: {
    complete_cost_and_fx_within_boundary: "reasonCompleteCostAndFx",
    synthetic_high_risk_alternative: "reasonSyntheticHighRisk",
    direct_program_fit_evidence_absent: "reasonProgramFitAbsent",
  },
  tradeOff: { budget_elasticity: "tradeOffBudgetElasticity" },
  candidateState: {
    pending: "candidatePending",
    stale: "candidateStale",
    expired: "candidateExpired",
    confirmed: "candidateConfirmed",
    rejected: "candidateRejected",
  },
  collaborationError: {
    stale: "errorStale",
    expired_or_terminal: "errorExpiredOrTerminal",
    active_task_blocked: "errorActiveTaskBlocked",
    unsafe_or_unsupported: "errorUnsafeOrUnsupported",
    wrong_role_or_not_found: "errorWrongRoleOrNotFound",
    session_recovery_required: "errorSessionRecoveryRequired",
    transport_unavailable_or_timeout: "errorTransportUnavailable",
  },
  skillPinStatus: {
    not_created: "pinNotCreated",
    matched: "pinMatched",
    legacy_unpinned: "pinLegacyUnpinned",
  },
  evidenceRisk: { optional: "riskOptional", stale: "riskStale", unverified: "riskUnverified" },
  riskTolerance: { low: "factValueRiskLow", medium: "factValueRiskMedium", high: "factValueRiskHigh" },
  decisionSource: { direct: "sourceDirect", family_consultation: "sourceFamilyConsultation" },
  recoveryCode: {
    invalid_transition: "recoveryInvalidTransition",
    session_expired: "recoverySessionExpired",
    session_recovery_required: "recoverySessionRequired",
    stale_conflict: "recoveryStaleConflict",
    transport_failure: "recoveryTransportFailure",
  },
  evidenceClaim: {
    australia_program_fit: "claimAustraliaProgramFit",
    japan_program_fit: "claimJapanProgramFit",
    malaysia_program_fit: "claimMalaysiaProgramFit",
    australia_tuition: "claimAustraliaTuition",
    australia_living_cost: "claimAustraliaLivingCost",
    australia_fx: "claimAustraliaFx",
    australia_ranking: "claimAustraliaRanking",
    japan_tuition: "claimJapanTuition",
    japan_living_cost: "claimJapanLivingCost",
    japan_fx: "claimJapanFx",
    japan_ranking: "claimJapanRanking",
    malaysia_tuition: "claimMalaysiaTuition",
    malaysia_living_cost: "claimMalaysiaLivingCost",
    malaysia_fx: "claimMalaysiaFx",
    malaysia_ranking: "claimMalaysiaRanking",
  },
  knownGap: {
    japan_gap: "gapJapanProgramFit",
    malaysia_gap: "gapMalaysiaProgramFit",
    applicant_eligibility: "gapApplicantEligibility",
    intake_availability: "gapIntakeAvailability",
  },
  milestone: {
    documents: "milestoneDocuments",
    application: "milestoneApplication",
    visa: "milestoneVisa",
    arrival: "milestoneArrival",
  },
  factKey: {
    "family.budget": "factFamilyBudget",
    "student.intended_field": "factStudentField",
    "student.preferred_countries": "factPreferredCountries",
    "student.intake": "factStudentIntake",
    "family.risk_tolerance": "factRiskTolerance",
    "family.japan_risk_accepted": "factJapanRiskAccepted",
  },
  publicCode: {
    cancelled: "publicCancelled",
    lease_expired: "publicLeaseExpired",
    required_evidence_gap: "publicEvidenceGap",
    deadline_exceeded: "publicDeadlineExceeded",
    transport_interrupted: "publicTransportInterrupted",
    transient_unavailable: "publicTransientUnavailable",
  },
} satisfies CodeCopyKeys;

export function presentCode(
  locale: PresentationLocale,
  kind: PresentationCodeKind,
  value: unknown,
): string {
  if (typeof value !== "string") return getPresentationCopy(locale, "statusUnavailable");
  const map = CODE_COPY_KEYS[kind] as Readonly<Record<string, PresentationCopyKey>>;
  if (!Object.prototype.hasOwnProperty.call(map, value)) {
    return getPresentationCopy(locale, "statusUnavailable");
  }
  return getPresentationCopy(locale, map[value]);
}

export function presentRouteOutcome(locale: PresentationLocale, value: unknown): string {
  return presentCode(locale, "routeOutcome", value);
}

export function presentRouteReason(locale: PresentationLocale, value: unknown): string {
  return presentCode(locale, "routeReason", value);
}

export function presentTradeOff(locale: PresentationLocale, value: unknown): string {
  return presentCode(locale, "tradeOff", value);
}
