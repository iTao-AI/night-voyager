export const SHOWCASE_ASSET_NAMES = [
  "advisor-workspace-overview.png",
  "advisor-normal-path.png",
  "advisor-blocked-recovery.png",
  "advisor-workspace-mobile.png",
] as const;

export type ShowcaseAssetName = (typeof SHOWCASE_ASSET_NAMES)[number];

export const SHOWCASE_ASSET_CONTRACT: Record<ShowcaseAssetName, {
  route: "/" | "/demo" | "/demo/plan?scenario=blocked";
  state: "route_analysis_preview" | "persisted_receipt_timeline" | "blocked_reassessment";
  locale: "zh-CN";
  proofSegment: "connected_same_case" | "independent_execution_scenario";
  viewport: { width: number; height: number };
}> = {
  "advisor-workspace-overview.png": {
    route: "/",
    state: "route_analysis_preview",
    locale: "zh-CN",
    proofSegment: "connected_same_case",
    viewport: { width: 1600, height: 1000 },
  },
  "advisor-normal-path.png": {
    route: "/demo",
    state: "persisted_receipt_timeline",
    locale: "zh-CN",
    proofSegment: "connected_same_case",
    viewport: { width: 1600, height: 1000 },
  },
  "advisor-blocked-recovery.png": {
    route: "/demo/plan?scenario=blocked",
    state: "blocked_reassessment",
    locale: "zh-CN",
    proofSegment: "independent_execution_scenario",
    viewport: { width: 1600, height: 1000 },
  },
  "advisor-workspace-mobile.png": {
    route: "/",
    state: "route_analysis_preview",
    locale: "zh-CN",
    proofSegment: "connected_same_case",
    viewport: { width: 390, height: 844 },
  },
};
