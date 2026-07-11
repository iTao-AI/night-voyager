"use client";

import Link from "next/link";
import { useState } from "react";

const countryFixtures = {
  Japan: {
    evidenceStatus: "Japan · Conditional",
    annualCost: "¥2.8m–3.4m",
    languagePathway: "English program; Japanese plan advised",
    visaUncertainty: "Financial proof timing",
    nextAction: "Advisor reviews accepted evidence",
  },
  Malaysia: {
    evidenceStatus: "Malaysia · Blocked · Evidence gap",
    annualCost: "RM 72k–88k",
    languagePathway: "English program",
    visaUncertainty: "Scholarship renewal evidence unresolved",
    nextAction: "Obtain scholarship renewal terms",
  },
  Australia: {
    evidenceStatus: "Australia · Comparison",
    annualCost: "A$58k–66k",
    languagePathway: "English program",
    visaUncertainty: "Post-study assumptions separated",
    nextAction: "Confirm affordability ceiling",
  },
} as const;

type Country = keyof typeof countryFixtures;

const countries = Object.keys(countryFixtures) as Country[];

export default function DemoPage() {
  const [selectedCountry, setSelectedCountry] = useState<Country>("Japan");
  const projection = countryFixtures[selectedCountry];

  return (
    <>
      <a className="skip-link" href="#demo-main">Skip to decision workflow</a>
      <header className="site-header">
        <Link className="wordmark" href="/">Night Voyager</Link>
        <nav aria-label="Demo context">
          <span>Evidence-led decisions</span>
          <strong>Synthetic fixture proof mode</strong>
        </nav>
      </header>

      <main id="demo-main" className="demo-shell">
        <section className="ledger-hero" aria-labelledby="ledger-title">
          <div className="ledger-intro">
            <p className="overline">Advisor workspace · Case NV-SYN-024</p>
            <h1 id="ledger-title">Advisor Ledger</h1>
            <p className="lede">Turn a documented Evidence gap and a human review into a family-ready decision, receipt, and timeline.</p>
          </div>

          <div className="current-stage" data-testid="current-stage">
            <div>
              <p className="stage-label">Current lifecycle stage</p>
              <h2>Advisor approval required</h2>
              <p><strong>Evidence gap:</strong> Malaysia scholarship renewal terms are not accepted evidence.</p>
              <p className="required-decision">Required human decision: verify the conditional Japan route before releasing the brief.</p>
            </div>
            <a className="primary-action" href="#evidence">Review evidence</a>
          </div>
        </section>

        <section className="advisor-ledger" aria-labelledby="comparison-title">
          <div className="section-heading">
            <p className="overline">Conditional planning result</p>
            <h2 id="comparison-title">Route evidence comparison</h2>
            <p>Japan can proceed to advisor review. Australia remains a viable comparison. Malaysia is blocked by an unresolved Evidence gap.</p>
          </div>

          <div className="table-wrap">
            <table aria-label="Route evidence comparison">
              <thead><tr><th scope="col">Dimension</th><th scope="col">Japan</th><th scope="col">Malaysia</th><th scope="col">Australia</th></tr></thead>
              <tbody>
                <tr><th scope="row">Evidence status</th><td><span className="status trust">Conditional</span></td><td><span className="status danger">Blocked</span></td><td><span className="status">Comparison</span></td></tr>
                <tr><th scope="row">Annual-cost range</th><td>¥2.8m–3.4m</td><td>RM 72k–88k</td><td>A$58k–66k</td></tr>
                <tr><th scope="row">Language pathway</th><td>English program; Japanese plan advised</td><td>English program</td><td>English program</td></tr>
                <tr><th scope="row">Visa uncertainty</th><td>Financial proof timing</td><td>Scholarship renewal unresolved</td><td>Post-study assumptions separated</td></tr>
                <tr><th scope="row">Next human action</th><td>Advisor reviews accepted evidence</td><td>Obtain renewal terms</td><td>Confirm affordability ceiling</td></tr>
              </tbody>
            </table>
          </div>

          <fieldset className="country-switcher">
            <legend>Choose a country</legend>
            <div className="switcher-row">
              {countries.map((country) => (
                <button
                  key={country}
                  type="button"
                  aria-pressed={selectedCountry === country}
                  onClick={() => setSelectedCountry(country)}
                >
                  {country}
                </button>
              ))}
            </div>
            <dl className="mobile-dimensions" aria-live="polite">
              <div><dt>Evidence status</dt><dd>{projection.evidenceStatus}</dd></div>
              <div><dt>Annual-cost range</dt><dd>{projection.annualCost}</dd></div>
              <div><dt>Language pathway</dt><dd>{projection.languagePathway}</dd></div>
              <div><dt>Visa uncertainty</dt><dd>{projection.visaUncertainty}</dd></div>
              <div><dt>Next human action</dt><dd>{projection.nextAction}</dd></div>
            </dl>
          </fieldset>

          <div className="ledger-grid" id="evidence">
            <article>
              <p className="overline">Accepted EvidenceRef</p>
              <h3>Japan route is conditional, not guaranteed</h3>
              <ul className="evidence-list">
                <li><strong>E-014</strong> Synthetic university fee schedule · accepted fixture</li>
                <li><strong>E-019</strong> Synthetic visa checklist · accepted fixture</li>
                <li><strong>Assumption</strong> Exchange rates are comparison inputs, not evidence</li>
              </ul>
            </article>
            <aside className="review-note" aria-label="Advisor approval summary">
              <p className="overline">Approval summary</p>
              <h3>Release only the Japan brief</h3>
              <p>Advisor approval confirms evidence eligibility; it does not decide for the family.</p>
              <p className="fixture-note">Fixture frame only · no approval mutation occurs.</p>
            </aside>
          </div>

          <details className="technical-details">
            <summary>Fixture execution details</summary>
            <p>Illustrative task state: complete. No worker, lease, SSE stream, or external adapter is invoked by this page.</p>
          </details>
        </section>

        <section className="family-story" aria-labelledby="family-story-title">
          <div className="section-heading editorial-heading">
            <p className="overline">Advisor-to-family handoff</p>
            <h2 id="family-story-title">One brief, then a durable decision trail</h2>
          </div>

          <article className="family-frame" data-testid="frame-family-review">
            <div className="frame-marker"><span>Before</span><strong>family_review</strong></div>
            <p className="chapter">01 · Read together</p>
            <h3>Family Decision Brief</h3>
            <p className="editorial-lede">Japan is the recommended route for this synthetic case, conditional on the documented financial-proof timeline.</p>
            <div className="brief-columns">
              <div><h4>Why it leads</h4><p>Accepted fixture evidence covers tuition, language pathway, and the current visa checklist.</p></div>
              <div><h4>What remains uncertain</h4><p>Exchange rates and future policy remain assumptions. Australia stays visible as the affordability comparison.</p></div>
            </div>
            <div className="confirmation-summary"><strong>Confirmation summary</strong><p>Confirming Japan would preserve the reviewed brief, known trade-offs, and create a DecisionReceipt with a TimelinePlan.</p></div>
            <button type="button" disabled>Confirm Japan route</button>
            <p className="disabled-reason">Disabled until the family confirms in a future mutation-enabled milestone. M1 renders fixture states only.</p>
          </article>

          <article className="family-frame decided-frame" data-testid="frame-decided">
            <div className="frame-marker"><span>After</span><strong>decided</strong></div>
            <p className="chapter">02 · Keep the record</p>
            <h3>Decision Receipt</h3>
            <p className="receipt-id">Receipt NV-FIXTURE-024 · Japan route · synthetic</p>
            <ol className="timeline">
              <li><time dateTime="2026-07-14">14 Jul</time><div><strong>Evidence pack check</strong><p>Reconfirm accepted fixture references and unresolved assumptions.</p></div></li>
              <li><time dateTime="2026-07-21">21 Jul</time><div><strong>Family finance review</strong><p>Test the cost range against the agreed affordability ceiling.</p></div></li>
              <li><time dateTime="2026-08-04">04 Aug</time><div><strong>Route readiness review</strong><p>Decide whether the documented conditions are satisfied.</p></div></li>
            </ol>
            <p className="recovery-copy"><strong>Stale or disconnected?</strong> Refresh this fixture and reconnect safely. The receipt remains visible, and M1 sends no mutation.</p>
          </article>
        </section>

        <section className="blocked-path" data-testid="malaysia-blocked" aria-labelledby="blocked-title">
          <div><p className="overline">Negative path · malaysia_blocked</p><h2 id="blocked-title">Malaysia remains blocked</h2></div>
          <div><p><strong>Evidence gap:</strong> scholarship renewal terms lack an accepted, manifest-owned source.</p><button type="button" disabled>Choose Malaysia</button><p className="disabled-reason">Blocked until an advisor validates the missing EvidenceRef. No override is available.</p></div>
        </section>
      </main>

      <footer><p>Night Voyager · local synthetic pilot · evidence before authority</p></footer>
    </>
  );
}
