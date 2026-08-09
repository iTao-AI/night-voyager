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
    preferredMinor: 34_000_000;
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
    preferredMinor: 34_000_000,
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
