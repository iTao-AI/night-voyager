export type PortfolioPreviewOutcome =
  | "recommended_with_condition"
  | "conditional"
  | "blocked";

export type PortfolioPreviewEvidenceCode =
  | "australia_program_fit"
  | "australia_tuition"
  | "australia_living_cost"
  | "australia_fx"
  | "australia_ranking"
  | "japan_program_fit"
  | "malaysia_context";

export type PortfolioPreviewGapCode =
  | "high_risk_alternative"
  | "direct_program_fit"
  | null;

export type PortfolioStoryScene =
  | "confirmed"
  | "route"
  | "outcome"
  | "reassessment"
  | "loading"
  | "empty"
  | "recoverable"
  | "completed";

export type PortfolioPersistedOutcome = {
  route: "australia";
  budget: "¥305,500–400,000";
  tradeoff: "预算弹性";
  source: "客户直接确认";
  intakeMonth: "2027-02";
  timeline: readonly [
    "文件准备 · 2026-09-01 · 学生",
    "提交申请 · 2026-10-15 · 学生",
    "签证准备 · 2026-12-15 · 学生",
    "抵达准备 · 2027-01-20 · 家长",
  ];
};

export type PortfolioPreviewRoute = {
  id: "australia" | "japan" | "malaysia";
  outcome: PortfolioPreviewOutcome;
  evidenceSufficiency: "complete" | "partial";
  acceptedEvidence: readonly PortfolioPreviewEvidenceCode[];
  unresolvedGap: PortfolioPreviewGapCode;
};

export type PortfolioPreviewProjection = {
  proofSegment: "connected_same_case";
  syntheticBoundary: true;
  intendedField: "computing";
  budget: {
    currency: "CNY";
    preferredMinor: 30_000_000;
    hardCeilingMinor: 40_000_000;
  };
  routes: readonly PortfolioPreviewRoute[];
  nextAction: "review_routes";
};

export const PORTFOLIO_PREVIEW: PortfolioPreviewProjection = {
  proofSegment: "connected_same_case",
  syntheticBoundary: true,
  intendedField: "computing",
  budget: {
    currency: "CNY",
    preferredMinor: 30_000_000,
    hardCeilingMinor: 40_000_000,
  },
  routes: [
    {
      id: "australia",
      outcome: "recommended_with_condition",
      evidenceSufficiency: "complete",
      acceptedEvidence: [
        "australia_program_fit",
        "australia_tuition",
        "australia_living_cost",
        "australia_fx",
        "australia_ranking",
      ],
      unresolvedGap: null,
    },
    {
      id: "japan",
      outcome: "conditional",
      evidenceSufficiency: "partial",
      acceptedEvidence: ["japan_program_fit"],
      unresolvedGap: "high_risk_alternative",
    },
    {
      id: "malaysia",
      outcome: "blocked",
      evidenceSufficiency: "partial",
      acceptedEvidence: ["malaysia_context"],
      unresolvedGap: "direct_program_fit",
    },
  ],
  nextAction: "review_routes",
};

export const PERSISTED_OUTCOME: PortfolioPersistedOutcome = {
  route: "australia",
  budget: "¥305,500–400,000",
  tradeoff: "预算弹性",
  source: "客户直接确认",
  intakeMonth: "2027-02",
  timeline: [
    "文件准备 · 2026-09-01 · 学生",
    "提交申请 · 2026-10-15 · 学生",
    "签证准备 · 2026-12-15 · 学生",
    "抵达准备 · 2027-01-20 · 家长",
  ],
};
