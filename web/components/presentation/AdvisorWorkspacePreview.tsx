"use client";

import Link from "next/link";
import { useId } from "react";

import { usePresentation } from "../../lib/presentation/context";
import { presentCode } from "../../lib/presentation/codes";
import { formatCnyRange } from "../../lib/presentation/format";
import { PORTFOLIO_PREVIEW, PERSISTED_OUTCOME, type PortfolioPreviewGapCode, type PortfolioStoryScene } from "../../lib/presentation/portfolio";
import { AdvisorProductFrame } from "./AdvisorProductFrame";
import { WorkflowRail } from "./WorkflowRail";

type AdvisorWorkspacePreviewProps = {
  scene?: PortfolioStoryScene;
};

const COUNTRY_COPY = {
  australia: "countryAustralia",
  japan: "countryJapan",
  malaysia: "countryMalaysia",
} as const;

const GAP_COPY: Record<Exclude<PortfolioPreviewGapCode, null>, Parameters<ReturnType<typeof usePresentation>["copy"]>[0]> = {
  high_risk_alternative: "previewGapHighRisk",
  direct_program_fit: "previewGapDirectProgramFit",
};

export function AdvisorWorkspacePreview({ scene = "route" }: AdvisorWorkspacePreviewProps) {
  const { copy, locale } = usePresentation();
  const currentWorkTitleId = `portfolio-preview-current-work-title-${useId().replaceAll(":", "")}`;
  const budget = formatCnyRange(
    locale,
    PORTFOLIO_PREVIEW.budget.preferredMinor,
    PORTFOLIO_PREVIEW.budget.hardCeilingMinor,
    PORTFOLIO_PREVIEW.budget.currency,
  );
  const stage = scene === "confirmed" ? copy("rootPreviewConfirmedStage") : scene === "outcome" ? copy("rootPreviewOutcomeStage") : copy("rootPreviewStage");
  const status = scene === "outcome" ? copy("rootPreviewOutcomeStatus") : copy("rootPreviewStatus");
  const title = scene === "confirmed"
    ? copy("rootPreviewConfirmedTitle")
    : scene === "outcome"
      ? copy("rootPreviewOutcomeTitle")
      : scene === "reassessment"
        ? copy("rootPreviewReassessmentTitle")
        : scene === "loading"
          ? copy("statusUnavailable")
          : scene === "empty"
            ? copy("rootPreviewConfirmedTitle")
            : scene === "recoverable"
              ? copy("rootPreviewReassessmentTitle")
              : scene === "completed"
                ? copy("rootPreviewOutcomeTitle")
                : copy("rootPreviewComparisonTitle");

  return (
    <div className={`portfolio-product-preview advisor-workspace-preview portfolio-product-preview-${scene}`} data-preview-scene={scene}>
      <AdvisorProductFrame
        className="portfolio-product-frame"
        topBand={
          <div className="workspace-top-band-grid">
            <div>
              <span>{copy("rootOriginLabel")}</span>
              <strong>{copy("rootOriginBudget")}</strong>
            </div>
            <div>
              <span>{copy("workspaceCurrentStage")}</span>
              <strong>{stage}</strong>
            </div>
            <div>
              <span>{copy("workspaceCurrentStatus")}</span>
              <strong>{status}</strong>
            </div>
            <div>
              <span>{copy("rootPreviewBoundaryLabel")}</span>
              <strong>{copy("rootPreviewBoundary")}</strong>
            </div>
          </div>
        }
        workflow={<WorkflowRail currentStage="route_analysis" copy={copy} />}
        context={
          <div className="workspace-context-plane">
            <p className="workspace-context-label">{copy("rootPreviewConfirmedTitle")}</p>
            <p className="workspace-context-value">{copy("previewIntendedFieldValue")}</p>
            <p className="workspace-boundary">{copy("rootPreviewConfirmedBudget")}</p>
            <p className="workspace-context-budget">{budget}</p>
            <dl className="workspace-context-facts">
              <div>
                <dt>{copy("rootPreviewCurrentRoute")}</dt>
                <dd>{copy("rootPreviewOutcomeRoute")}</dd>
              </div>
              <div>
                <dt>{copy("rootPreviewBoundaryLabel")}</dt>
                <dd>{copy("rootPreviewBoundary")}</dd>
              </div>
            </dl>
          </div>
        }
        currentWork={
          <div className="workspace-current-work-content">
            <div className="workspace-route-heading">
              <p className="workspace-route-context">{copy("rootPreviewBoundaryLabel")}</p>
              <h2>{title}</h2>
              <p className="workspace-status">{status}</p>
            </div>
            <section className="workspace-current-work" aria-labelledby={currentWorkTitleId}>
              <h3 id={currentWorkTitleId}>{copy("workspaceCurrentWork")}</h3>
              {renderCurrentWork(scene, copy, locale, budget)}
            </section>
          </div>
        }
        evidence={renderEvidence(scene, copy, locale)}
        authority={renderAuthority(scene, copy)}
        technical={
          <ul>
            <li>{copy("rootPreviewRecordVersion")}</li>
            <li>{copy("rootPreviewFactVersion")}</li>
            <li>{copy("proofSegmentConnectedSameCase")}</li>
            <li>{copy("rootPreviewHandoffBody")}</li>
          </ul>
        }
        technicalLabel={copy("workspaceTechnicalEvidence")}
      />
    </div>
  );
}

function renderCurrentWork(
  scene: PortfolioStoryScene,
  copy: ReturnType<typeof usePresentation>["copy"],
  locale: Parameters<typeof presentCode>[0],
  budget: string,
) {
  if (scene === "confirmed") {
    return (
      <div className="portfolio-preview-confirmed-work">
        <p>{copy("rootPreviewHandoffBody")}</p>
        <dl className="portfolio-preview-value-list">
          <div><dt>{copy("previewIntendedField")}</dt><dd>{copy("previewIntendedFieldValue")}</dd></div>
          <div><dt>{copy("previewBudget")}</dt><dd>{budget}</dd></div>
        </dl>
      </div>
    );
  }

  if (scene === "outcome" || scene === "completed") {
    return (
      <div className="portfolio-preview-outcome-work">
        <p className="portfolio-preview-outcome-route">{copy("rootPreviewOutcomeRoute")}</p>
        <dl className="portfolio-preview-value-list">
          <div><dt>{copy("previewBudget")}</dt><dd>{copy("rootPreviewOutcomeBudget")}</dd></div>
          <div><dt>{copy("rootPreviewOutcomeTradeoff")}</dt><dd>{copy("rootPreviewOutcomeSource")}</dd></div>
          <div><dt>{locale === "zh-CN" ? "开始月份" : "Intake month"}</dt><dd>{PERSISTED_OUTCOME.intakeMonth}</dd></div>
        </dl>
      </div>
    );
  }

  if (scene === "reassessment" || scene === "recoverable") {
    return (
      <div className="portfolio-preview-reassessment-work">
        <p>{copy("rootPreviewReassessmentBody")}</p>
        <p className="portfolio-preview-safe-state">{copy("rootPreviewBoundary")}</p>
      </div>
    );
  }

  if (scene === "loading") {
    return <p>{copy("statusUnavailable")}</p>;
  }

  if (scene === "empty") {
    return <p>{copy("rootPreviewHandoffBody")}</p>;
  }

  return (
    <>
      <p className="portfolio-preview-route-description">{copy("rootRouteAtlasDescription")}</p>
      <ol className="portfolio-preview-route-list portfolio-route-list" aria-label={copy("rootRouteSummaryLabel")}>
        {PORTFOLIO_PREVIEW.routes.map((route, index) => (
          <li key={route.id} className={route.id === "australia" ? "is-dominant" : undefined} data-route-id={route.id}>
            <span className="portfolio-preview-route-index" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
            <div>
              <div className="portfolio-preview-route-heading">
                <h3>{copy(COUNTRY_COPY[route.id])}</h3>
                <span className={`workspace-status-pill workspace-status-${route.outcome}`}>
                  {presentCode(locale, "routeOutcome", route.outcome)}
                </span>
              </div>
              <p>{copy(route.id === "australia" ? "rootRouteAustraliaReason" : route.id === "japan" ? "rootRouteJapanReason" : "rootRouteMalaysiaReason")}</p>
              {route.unresolvedGap ? <p className="portfolio-preview-route-gap">{copy(GAP_COPY[route.unresolvedGap])}</p> : null}
            </div>
          </li>
        ))}
      </ol>
    </>
  );
}

function renderEvidence(
  scene: PortfolioStoryScene,
  copy: ReturnType<typeof usePresentation>["copy"],
  locale: Parameters<typeof presentCode>[0],
) {
  if (scene === "outcome" || scene === "completed") {
    return (
      <div className="workspace-supporting-evidence-content portfolio-preview-timeline">
        <h3>{copy("rootPreviewTimelineTitle")}</h3>
        <ol>
          {(["rootPreviewTimelineOne", "rootPreviewTimelineTwo", "rootPreviewTimelineThree", "rootPreviewTimelineFour"] as const).map((key) => (
            <li key={key}>{copy(key)}</li>
          ))}
        </ol>
      </div>
    );
  }

  if (scene === "confirmed") {
    return (
      <div className="workspace-supporting-evidence-content">
        <h3>{copy("rootPreviewEvidenceTitle")}</h3>
        <p>{copy("rootPreviewHandoffBody")}</p>
      </div>
    );
  }

  if (scene === "loading" || scene === "empty") {
    return (
      <div className="workspace-supporting-evidence-content">
        <h3>{copy("rootPreviewEvidenceTitle")}</h3>
        <p>{copy("statusUnavailable")}</p>
      </div>
    );
  }

  return (
    <div className="workspace-supporting-evidence-content portfolio-preview-evidence">
      <h3>{copy("rootPreviewEvidenceTitle")}</h3>
      <ul>
        {PORTFOLIO_PREVIEW.routes[0].acceptedEvidence.map((evidence) => (
          <li key={evidence}>{presentCode(locale, "evidenceClaim", evidence)}</li>
        ))}
      </ul>
    </div>
  );
}

function renderAuthority(
  scene: PortfolioStoryScene,
  copy: ReturnType<typeof usePresentation>["copy"],
) {
  const action = scene === "outcome" || scene === "completed"
    ? <Link data-primary-action="true" className="workspace-primary-action" href="/demo/plan">{copy("rootPreviewOutcomeAction")}</Link>
    : scene === "reassessment" || scene === "recoverable"
      ? <p className="workspace-authority-status">{copy("rootPreviewReassessmentBody")}</p>
      : <Link data-primary-action="true" className="workspace-primary-action" href="/demo">{copy("previewReviewRoutes")}</Link>;

  return (
    <div className="workspace-authority-plane">
      <p className="workspace-authority-label">{copy("workspaceHumanAuthority")}</p>
      <p className="workspace-authority-role">{copy("roleAdvisor")}</p>
      {action}
    </div>
  );
}
