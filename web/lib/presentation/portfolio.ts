import type { PresentationCopyKey } from "./catalog";

export type PortfolioRouteEmphasis = "primary" | "secondary" | "muted";

export interface PortfolioRouteStop {
  id: "australia" | "japan" | "malaysia";
  countryKey: PresentationCopyKey;
  statusKey: PresentationCopyKey;
  reasonKey: PresentationCopyKey;
  emphasis: PortfolioRouteEmphasis;
}

export const PORTFOLIO_ROUTE_STOPS = [
  {
    id: "australia",
    countryKey: "countryAustralia",
    statusKey: "rootRouteRecommended",
    reasonKey: "rootRouteAustraliaReason",
    emphasis: "primary",
  },
  {
    id: "japan",
    countryKey: "countryJapan",
    statusKey: "rootRouteReserve",
    reasonKey: "rootRouteJapanReason",
    emphasis: "secondary",
  },
  {
    id: "malaysia",
    countryKey: "countryMalaysia",
    statusKey: "rootRouteNotRecommended",
    reasonKey: "rootRouteMalaysiaReason",
    emphasis: "muted",
  },
] as const satisfies readonly PortfolioRouteStop[];
