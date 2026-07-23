"use client";

import Link from "next/link";

import { usePresentation } from "../../lib/presentation/context";

const JOURNEY_STEPS = [
  {
    indexKey: "rootJourneyStepOneIndex",
    titleKey: "rootJourneyStepOneTitle",
    bodyKey: "rootJourneyStepOneBody",
  },
  {
    indexKey: "rootJourneyStepTwoIndex",
    titleKey: "rootJourneyStepTwoTitle",
    bodyKey: "rootJourneyStepTwoBody",
  },
  {
    indexKey: "rootJourneyStepThreeIndex",
    titleKey: "rootJourneyStepThreeTitle",
    bodyKey: "rootJourneyStepThreeBody",
  },
] as const;

export function PortfolioJourney() {
  const { copy } = usePresentation();

  return (
    <section
      id="journey"
      className="portfolio-journey"
      aria-labelledby="portfolio-journey-title"
    >
      <div className="portfolio-journey-header">
        <div>
          <p className="portfolio-journey-index">{copy("rootJourneyIndex")}</p>
          <h2 id="portfolio-journey-title">
            <span>{copy("rootJourneyTitleLineOne")}</span>
            {" "}
            <span>{copy("rootJourneyTitleLineTwo")}</span>
          </h2>
        </div>
        <p className="portfolio-journey-lead">{copy("rootJourneyLead")}</p>
      </div>

      <ol className="portfolio-journey-track">
        {JOURNEY_STEPS.map((step) => (
          <li key={step.indexKey}>
            <span className="portfolio-journey-node" aria-hidden="true" />
            <p className="portfolio-journey-step-index">
              {copy(step.indexKey)}
            </p>
            <h3>{copy(step.titleKey)}</h3>
            <p>{copy(step.bodyKey)}</p>
          </li>
        ))}
      </ol>

      <details className="portfolio-disclosure">
        <summary>{copy("rootScopeTitle")}</summary>
        <p>{copy("rootScopeBody")}</p>
        <Link href="/demo">{copy("rootNavEvidence")}</Link>
      </details>
    </section>
  );
}
