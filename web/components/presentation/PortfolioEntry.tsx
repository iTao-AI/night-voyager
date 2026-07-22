"use client";

import Link from "next/link";

import { usePresentation } from "../../lib/presentation/context";

export function PortfolioEntry() {
  const { copy } = usePresentation();
  const beats = [
    ["rootBeatMessageTitle", "rootBeatMessageBody"],
    ["rootBeatFactTitle", "rootBeatFactBody"],
    ["rootBeatPlanTitle", "rootBeatPlanBody"],
  ] as const;

  return (
    <article className="portfolio-entry" aria-labelledby="portfolio-title">
      <div className="portfolio-hero">
        <p className="eyebrow">{copy("rootKicker")}</p>
        <h1 id="portfolio-title">{copy("productPromise")}</h1>
        <p className="portfolio-summary">{copy("rootSummary")}</p>
      </div>

      <section className="outcome-ledger" aria-label={copy("rootOutcomeLabel")}>
        <div>
          <p className="field-label">{copy("rootOutcomeLabel")}</p>
          <p>{copy("rootOutcome")}</p>
        </div>
        <div>
          <p className="field-label">{copy("rootReasonLabel")}</p>
          <p>{copy("rootReason")}</p>
        </div>
        <div>
          <p className="field-label">{copy("rootNextLabel")}</p>
          <p>{copy("rootNext")}</p>
        </div>
      </section>

      <nav className="portfolio-actions" aria-label={copy("rootNextLabel")}>
        <Link className="primary-action" href="/demo/collaboration">
          {copy("rootPrimaryAction")}
        </Link>
        <Link className="secondary-action" href="/demo">
          {copy("rootSecondaryAction")}
        </Link>
      </nav>

      <section className="authority-route" aria-labelledby="authority-title">
        <h2 id="authority-title">{copy("rootAuthorityTitle")}</h2>
        <ol>
          {beats.map(([title, body]) => (
            <li key={title}>
              <h3>{copy(title)}</h3>
              <p>{copy(body)}</p>
            </li>
          ))}
        </ol>
      </section>

      <details className="technical-disclosure">
        <summary>{copy("rootScopeTitle")}</summary>
        <p>{copy("rootScopeBody")}</p>
      </details>
    </article>
  );
}
