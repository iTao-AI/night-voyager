"use client";

import Link from "next/link";

import { usePresentation } from "../../lib/presentation/context";
import { PortfolioBackdrop } from "./PortfolioBackdrop";
import { PortfolioRouteAtlas } from "./PortfolioRouteAtlas";

export function PortfolioEntry() {
  const { copy } = usePresentation();

  return (
    <article className="portfolio-entry" aria-labelledby="portfolio-title">
      <section className="portfolio-hero-stage">
        <PortfolioBackdrop />
        <div className="portfolio-hero-grid">
          <div className="portfolio-hero-copy">
            <p className="portfolio-eyebrow">{copy("rootEyebrow")}</p>
            <h1 id="portfolio-title">
              <span>{copy("rootTitleLineOne")}</span>
              {" "}
              <span>{copy("rootTitleLineTwo")}</span>
            </h1>
            <p className="portfolio-hero-summary">{copy("rootSummary")}</p>
            <nav
              className="portfolio-hero-actions"
              aria-label={copy("rootNavigationLabel")}
            >
              <Link
                className="portfolio-button portfolio-button-primary"
                href="/demo/collaboration"
              >
                {copy("rootPrimaryAction")}
                <span aria-hidden="true">→</span>
              </Link>
              <a
                className="portfolio-button portfolio-button-secondary"
                href="#route-atlas"
              >
                {copy("rootSecondaryAction")}
              </a>
            </nav>
            <p className="portfolio-scroll-cue" aria-hidden="true">
              <span />
              {copy("rootScrollCue")}
            </p>
          </div>
          <PortfolioRouteAtlas />
        </div>
      </section>

      <details className="portfolio-disclosure">
        <summary>{copy("rootScopeTitle")}</summary>
        <p>{copy("rootScopeBody")}</p>
      </details>
    </article>
  );
}
