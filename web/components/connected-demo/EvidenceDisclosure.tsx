"use client";

import type { AdvisorLedger as Ledger } from "../../lib/connected-demo/contracts";
import { presentCode } from "../../lib/presentation/codes";
import { usePresentation } from "../../lib/presentation/context";
import { formatIsoDate } from "../../lib/presentation/format";

export function EvidenceDisclosure({ evidence }: { evidence: Ledger["evidence"] }) {
  const { locale, copy } = usePresentation();
  if (!evidence?.length) return null;
  const sourceExample = evidence[0];
  const allEvidenceSummary = copy("evidenceAllSummary").replace(
    "{count}",
    String(evidence.length),
  );

  return (
    <section className="evidence-disclosure" aria-labelledby="evidence-summary-title">
      <p className="overline" id="evidence-summary-title">{copy("evidenceTitle")}</p>
      <p>{copy("evidenceOverline")}</p>
      <article
        className="evidence-source-example"
        aria-labelledby="evidence-source-example-title"
      >
        <p className="technical-label" id="evidence-source-example-title">
          {copy("evidenceSourceExample")}
        </p>
        <dl>
          <div>
            <dt>{copy("evidenceClaimLabel")}</dt>
            <dd>{presentCode(locale, "evidenceClaim", sourceExample.claim)}</dd>
          </div>
          <div>
            <dt>{copy("evidencePublisherLabel")}</dt>
            <dd>{sourceExample.publisher}</dd>
          </div>
          <div>
            <dt>{copy("evidenceSnapshotLabel")}</dt>
            <dd>{formatIsoDate(locale, sourceExample.snapshot_date)}</dd>
          </div>
          <div>
            <dt>{copy("evidenceLimitationLabel")}</dt>
            <dd className="evidence-raw-content">{sourceExample.limitation}</dd>
          </div>
        </dl>
      </article>
      <details className="technical-details">
        <summary>{allEvidenceSummary}</summary>
        <ul className="evidence-list">
          {evidence.map((item, index) => (
            <li key={`${item.snapshot_date}-${index}`}>
              <strong>{presentCode(locale, "evidenceClaim", item.claim)}</strong>
              <span> · {copy("evidencePublisherLabel")}: {item.publisher}</span>
              <span> · <span className="technical-label">{copy("evidenceLimitationLabel")}</span>: <span className="evidence-raw-content">{item.limitation}</span></span>
              <span> · {copy("evidenceSnapshotLabel")}: {formatIsoDate(locale, item.snapshot_date)}</span>
            </li>
          ))}
        </ul>
      </details>
    </section>
  );
}
