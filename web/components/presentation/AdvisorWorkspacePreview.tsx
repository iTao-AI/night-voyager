"use client";

import Link from "next/link";

import { usePresentation } from "../../lib/presentation/context";
import { presentCode } from "../../lib/presentation/codes";
import { formatCnyRange } from "../../lib/presentation/format";
import {
  PORTFOLIO_PREVIEW,
  type PortfolioPreviewEvidenceCode,
  type PortfolioPreviewGapCode,
} from "../../lib/presentation/portfolio";

const EVIDENCE_COPY: Record<PortfolioPreviewEvidenceCode, Parameters<ReturnType<typeof usePresentation>["copy"]>[0]> = {
  australia_program_fit: "claimAustraliaProgramFit",
  australia_tuition: "claimAustraliaTuition",
  australia_living_cost: "claimAustraliaLivingCost",
  australia_fx: "claimAustraliaFx",
  australia_ranking: "claimAustraliaRanking",
  japan_program_fit: "claimJapanProgramFit",
  malaysia_context: "previewEvidenceMalaysiaContext",
};

const GAP_COPY: Record<Exclude<PortfolioPreviewGapCode, null>, Parameters<ReturnType<typeof usePresentation>["copy"]>[0]> = {
  high_risk_alternative: "previewGapHighRisk",
  direct_program_fit: "previewGapDirectProgramFit",
};

export function AdvisorWorkspacePreview() {
  const { copy, locale } = usePresentation();
  const budget = formatCnyRange(
    locale,
    PORTFOLIO_PREVIEW.budget.preferredMinor,
    PORTFOLIO_PREVIEW.budget.hardCeilingMinor,
    PORTFOLIO_PREVIEW.budget.currency,
  );

  return (
    <section className="advisor-workspace-preview" aria-labelledby="advisor-preview-title">
      <div className="advisor-workspace-preview-heading">
        <div>
          <p className="workspace-preview-boundary">{copy("rootPreviewBoundary")}</p>
          <h2 id="advisor-preview-title">{copy("rootPreviewTitle")}</h2>
        </div>
        <span className="workspace-proof-chip">{copy("proofSegmentConnectedSameCase")}</span>
      </div>
      <dl className="workspace-preview-facts">
        <div>
          <dt>{copy("previewIntendedField")}</dt>
          <dd>{PORTFOLIO_PREVIEW.intendedField}</dd>
        </div>
        <div>
          <dt>{copy("previewBudget")}</dt>
          <dd>{budget}</dd>
        </div>
      </dl>
      <ol className="workspace-route-list" aria-label={copy("rootRouteSummaryLabel")}>
        {PORTFOLIO_PREVIEW.routes.map((route, index) => (
          <li key={route.id} className="workspace-route-row" data-route-id={route.id}>
            <div className="workspace-route-index" aria-hidden="true">{String(index + 1).padStart(2, "0")}</div>
            <div className="workspace-route-main">
              <div className="workspace-route-title-row">
                <h3>{copy(COUNTRY_COPY[route.id])}</h3>
                <span className={`workspace-status-pill workspace-status-${route.outcome}`}>
                  {presentCode(locale, "routeOutcome", route.outcome)}
                </span>
              </div>
              <dl className="workspace-route-details">
                <div>
                  <dt>{copy("previewEvidenceSufficiency")}</dt>
                  <dd>{copy(route.evidenceSufficiency === "complete" ? "previewEvidenceComplete" : "previewEvidencePartial")}</dd>
                </div>
                <div>
                  <dt>{copy("previewUnresolvedGap")}</dt>
                  <dd>{route.unresolvedGap ? copy(GAP_COPY[route.unresolvedGap]) : copy("previewNoKnownGap")}</dd>
                </div>
              </dl>
              <ul className="workspace-evidence-tags" aria-label={copy("previewEvidenceSufficiency")}>
                {route.acceptedEvidence.map((evidence) => (
                  <li key={evidence}>{presentCodeOrCopy(locale, copy, evidence)}</li>
                ))}
              </ul>
            </div>
          </li>
        ))}
      </ol>
      <div className="workspace-preview-next">
        <div>
          <p className="workspace-preview-label">{copy("previewNextAction")}</p>
          <p>{copy("previewReviewRoutes")}</p>
        </div>
        <Link data-primary-action="true" className="workspace-primary-action" href="/demo">
          {copy("previewReviewRoutes")}
        </Link>
      </div>
    </section>
  );
}

const COUNTRY_COPY = {
  australia: "countryAustralia",
  japan: "countryJapan",
  malaysia: "countryMalaysia",
} as const;

function presentCodeOrCopy(
  locale: Parameters<typeof presentCode>[0],
  copy: ReturnType<typeof usePresentation>["copy"],
  evidence: PortfolioPreviewEvidenceCode,
): string {
  if (evidence === "malaysia_context") return copy(EVIDENCE_COPY[evidence]);
  return presentCode(locale, "evidenceClaim", evidence);
}
