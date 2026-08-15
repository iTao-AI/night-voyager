"use client";

import Link from "next/link";

import { usePresentation } from "../../lib/presentation/context";
import { PortfolioStory } from "./PortfolioStory";
import { AdvisorWorkspacePreview } from "./AdvisorWorkspacePreview";

export function PortfolioEntry() {
  const { copy } = usePresentation();

  return (
    <article className="portfolio-entry" aria-labelledby="portfolio-title">
      <section className="portfolio-hero" aria-labelledby="portfolio-title">
        <div className="portfolio-hero-copy">
          <p className="portfolio-eyebrow">{copy("rootEyebrow")}</p>
          <h1 id="portfolio-title" aria-label={copy("rootTitle")}>
            <span>{copy("rootTitleLineOne")}</span>
            <span>{copy("rootTitleLineTwo")}</span>
          </h1>
          <p className="portfolio-hero-summary">{copy("rootSummary")}</p>
          <nav className="portfolio-hero-actions" aria-label={copy("rootNextLabel")}>
            <a className="portfolio-primary-action" href="#product">
              {copy("rootPrimaryAction")}
            </a>
            <a
              className="portfolio-secondary-action"
              href="https://github.com/iTao-AI/night-voyager"
              rel="noreferrer"
              target="_blank"
            >
              {copy("rootSecondaryAction")}
            </a>
          </nav>
        </div>
        <div className="portfolio-hero-product" aria-label={copy("rootPreviewTitle")}>
          <AdvisorWorkspacePreview scene="route" />
        </div>
      </section>

      <PortfolioStory />

      <section className="portfolio-section portfolio-reassessment" aria-labelledby="portfolio-reassessment-title">
        <div className="portfolio-section-heading">
          <p className="portfolio-section-index">04 / {copy("rootNavRoutes")}</p>
          <h2 id="portfolio-reassessment-title">{copy("rootChapterReassessmentTitle")}</h2>
          <p>{copy("rootChapterReassessmentBody")}</p>
        </div>
        <div className="portfolio-reassessment-panel">
          <div>
            <p className="portfolio-panel-label">{copy("rootOutcomeLabel")}</p>
            <p>{copy("rootPreviewReassessmentBody")}</p>
          </div>
          <div className="portfolio-reassessment-status">
            <span aria-hidden="true" />
            <strong>{copy("workspaceHumanAuthority")}</strong>
            <p>{copy("rootPreviewReassessmentBody")}</p>
          </div>
        </div>
      </section>

      <section className="portfolio-section portfolio-trust" aria-labelledby="portfolio-trust-title">
        <div className="portfolio-section-heading">
          <p className="portfolio-section-index">05 / {copy("rootNavRoutes")}</p>
          <h2 id="portfolio-trust-title">{copy("rootTrustTitle")}</h2>
        </div>
        <ul className="portfolio-trust-list">
          <li>{copy("rootTrustItemOne")}</li>
          <li>{copy("rootTrustItemTwo")}</li>
          <li>{copy("rootTrustItemThree")}</li>
        </ul>
      </section>

      <section id="engineering" className="portfolio-section portfolio-engineering" aria-labelledby="portfolio-engineering-title">
        <div className="portfolio-section-heading">
          <p className="portfolio-section-index">{copy("rootNavEvidence")}</p>
          <h2 id="portfolio-engineering-title">{copy("rootAuthorityTitle")}</h2>
          <p>{copy("rootClosingBody")}</p>
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

      <section className="portfolio-closing" aria-labelledby="portfolio-closing-title">
        <div>
          <p className="portfolio-section-index">{copy("rootOutcomeLabel")}</p>
          <h2 id="portfolio-closing-title">{copy("rootClosingTitle")}</h2>
          <p>{copy("rootClosingBody")}</p>
        </div>
        <nav className="portfolio-closing-actions" aria-label={copy("rootNextLabel")}>
          <Link className="portfolio-primary-action" href="/demo/collaboration">
            {copy("rootClosingPrimaryAction")}
          </Link>
          <Link className="portfolio-secondary-action" href="/demo">
            {copy("rootClosingSecondaryAction")}
          </Link>
        </nav>
      </section>

      <p className="portfolio-public-boundary">{copy("publicBoundary")}</p>
    </article>
  );
}
