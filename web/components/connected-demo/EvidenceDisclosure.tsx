"use client";

import type { AdvisorLedger as Ledger } from "../../lib/connected-demo/contracts";
import { presentCode } from "../../lib/presentation/codes";
import { usePresentation } from "../../lib/presentation/context";
import { formatIsoDate } from "../../lib/presentation/format";

export function EvidenceDisclosure({ evidence }: { evidence: Ledger["evidence"] }) {
  const { locale, copy } = usePresentation();
  if (!evidence?.length) return null;
  return (
    <details className="evidence-disclosure technical-disclosure">
      <summary id="evidence-title">{copy("evidenceTitle")}</summary>
      <p className="overline">{copy("evidenceOverline")}</p>
      <ul className="evidence-list">
        {evidence.map((item, index) => (
          <li key={`${item.snapshot_date}-${index}`}>
            <strong>{presentCode(locale, "evidenceClaim", item.claim)}</strong>
            <span> · {copy("evidencePublisherLabel")}: {item.publisher}</span>
            <span> · {copy("evidenceLimitationLabel")}: {item.limitation}</span>
            <span> · {copy("evidenceSnapshotLabel")}: {formatIsoDate(locale, item.snapshot_date)}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}
