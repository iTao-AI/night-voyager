"use client";

import type { AdvisorLedger as Ledger } from "../../lib/connected-demo/contracts";
import { presentCode } from "../../lib/presentation/codes";
import { usePresentation } from "../../lib/presentation/context";
import { formatIsoDate } from "../../lib/presentation/format";

export function EvidenceDisclosure({ evidence }: { evidence: Ledger["evidence"] }) {
  const { locale, copy } = usePresentation();
  if (!evidence?.length) return null;
  return (
    <section className="evidence-disclosure" aria-labelledby="evidence-summary-title">
      <p className="overline" id="evidence-summary-title">{copy("evidenceTitle")}</p>
      <p>{copy("evidenceOverline")}</p>
      <details className="technical-details">
        <summary>{copy("evidenceTitle")}</summary>
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
