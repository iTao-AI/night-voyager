import type { AdvisorLedger as Ledger } from "../../lib/connected-demo/contracts";

export function EvidenceDisclosure({ evidence }: { evidence: Ledger["evidence"] }) {
  if (!evidence?.length) return null;
  return (
    <section className="evidence-disclosure" aria-labelledby="evidence-title">
      <p className="overline">Evidence disclosure</p>
      <h3 id="evidence-title">Accepted synthetic evidence and limitations</h3>
      <ul className="evidence-list">
        {evidence.map((item, index) => (
          <li key={`${String(item.claim)}-${index}`}>
            <strong>{String(item.claim)}</strong> · {String(item.publisher)} · {String(item.limitation)}
          </li>
        ))}
      </ul>
    </section>
  );
}
