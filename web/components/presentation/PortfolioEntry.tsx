"use client";

import Link from "next/link";

import { usePresentation } from "../../lib/presentation/context";
import { presentCode } from "../../lib/presentation/codes";
import { formatCnyRange } from "../../lib/presentation/format";
import { WORKFLOW_STAGES, type WorkflowStage } from "../../lib/presentation/journey";
import { PORTFOLIO_PREVIEW } from "../../lib/presentation/portfolio";
import { AdvisorWorkspacePreview } from "./AdvisorWorkspacePreview";

const WORKFLOW_COPY: Record<WorkflowStage, Parameters<ReturnType<typeof usePresentation>["copy"]>[0]> = {
  consultation_intake: "workflowStageConsultationIntake",
  client_fact_review: "workflowStageClientFactReview",
  route_analysis: "workflowStageRouteAnalysis",
  client_confirmation: "workflowStageClientConfirmation",
  execution_followup: "workflowStageExecutionFollowup",
};

const GAP_COPY = {
  high_risk_alternative: "previewGapHighRisk",
  direct_program_fit: "previewGapDirectProgramFit",
} as const;

export function PortfolioEntry() {
  const { copy, locale } = usePresentation();
  const budget = formatCnyRange(
    locale,
    PORTFOLIO_PREVIEW.budget.preferredMinor,
    PORTFOLIO_PREVIEW.budget.hardCeilingMinor,
    PORTFOLIO_PREVIEW.budget.currency,
  );

  return (
    <article className="portfolio-entry" aria-labelledby="portfolio-title">
      <section className="portfolio-hero" aria-labelledby="portfolio-title">
        <div className="portfolio-hero-copy">
          <p className="portfolio-eyebrow">{copy("rootEyebrow")}</p>
          <h1 id="portfolio-title">{copy("rootTitle")}</h1>
          <p className="portfolio-hero-summary">{copy("rootSummary")}</p>
          <nav className="portfolio-hero-actions" aria-label={copy("rootNextLabel")}>
            <Link className="portfolio-primary-action" href="/demo/collaboration">
              {copy("rootPrimaryAction")}
            </Link>
            <Link className="portfolio-secondary-action" href="/demo">
              {copy("rootSecondaryAction")}
            </Link>
          </nav>
        </div>
        <AdvisorWorkspacePreview />
      </section>

      <section id="journey" className="portfolio-section portfolio-workflow" aria-labelledby="portfolio-workflow-title">
        <div className="portfolio-section-heading">
          <p className="portfolio-section-index">{copy("rootJourneyIndex")}</p>
          <h2 id="portfolio-workflow-title">{copy("rootWorkflowTitle")}</h2>
          <p>{copy("rootWorkflowBody")}</p>
        </div>
        <ol className="portfolio-workflow-list">
          {WORKFLOW_STAGES.map((stage, index) => (
            <li key={stage} data-stage={stage}>
              <span aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
              <strong>{copy(WORKFLOW_COPY[stage])}</strong>
            </li>
          ))}
        </ol>
        <p className="portfolio-scenario-boundary">{copy("separateExecutionScenario")}</p>
      </section>

      <section id="route-atlas" className="portfolio-section portfolio-route-analysis" aria-labelledby="portfolio-route-analysis-title">
        <div className="portfolio-section-heading">
          <p className="portfolio-section-index">{copy("rootNavRoutes")}</p>
          <h2 id="portfolio-route-analysis-title">{copy("rootRouteAtlasTitle")}</h2>
          <p>{copy("rootRouteAtlasDescription")}</p>
        </div>
        <dl className="portfolio-case-facts">
          <div><dt>{copy("previewIntendedField")}</dt><dd>{PORTFOLIO_PREVIEW.intendedField}</dd></div>
          <div><dt>{copy("previewBudget")}</dt><dd>{budget}</dd></div>
        </dl>
        <ol className="portfolio-route-list" aria-label={copy("rootRouteSummaryLabel")}>
          {PORTFOLIO_PREVIEW.routes.map((route, index) => (
            <li key={route.id} data-route-id={route.id}>
              <span className="portfolio-route-number" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
              <div>
                <div className="portfolio-route-heading">
                  <h3>{copy(COUNTRY_COPY[route.id])}</h3>
                  <span>{presentCode(locale, "routeOutcome", route.outcome)}</span>
                </div>
                <p>{copy(route.unresolvedGap ? GAP_COPY[route.unresolvedGap] : "previewNoKnownGap")}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="portfolio-section portfolio-responsibility" aria-labelledby="portfolio-responsibility-title">
        <div className="portfolio-section-heading">
          <p className="portfolio-section-index">{copy("rootReasonLabel")}</p>
          <h2 id="portfolio-responsibility-title">{copy("rootResponsibilityTitle")}</h2>
        </div>
        <div className="portfolio-responsibility-grid">
          <article>
            <h3>{copy("rootResponsibilityAiTitle")}</h3>
            <p>{copy("rootResponsibilityAiBody")}</p>
          </article>
          <article>
            <h3>{copy("rootResponsibilityHumanTitle")}</h3>
            <p>{copy("rootResponsibilityHumanBody")}</p>
          </article>
        </div>
      </section>

      <section className="portfolio-section portfolio-engineering" aria-labelledby="portfolio-engineering-title">
        <div className="portfolio-section-heading">
          <p className="portfolio-section-index">{copy("rootNavEvidence")}</p>
          <h2 id="portfolio-engineering-title">{copy("rootEngineeringTitle")}</h2>
          <p>{copy("rootEngineeringBody")}</p>
        </div>
        <details className="portfolio-technical-disclosure">
          <summary>{copy("workspaceTechnicalEvidence")}</summary>
          <ul>
            <li>{copy("rootEvidenceItemGates")}</li>
            <li>{copy("rootEvidenceItemHumanReview")}</li>
            <li>{copy("rootEvidenceItemDurable")}</li>
          </ul>
        </details>
      </section>
    </article>
  );
}

const COUNTRY_COPY = {
  australia: "countryAustralia",
  japan: "countryJapan",
  malaysia: "countryMalaysia",
} as const;
