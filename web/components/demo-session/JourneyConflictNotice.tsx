import Link from "next/link";

export function JourneyConflictNotice({ currentJourney, returnHref, onEnd }: { currentJourney: "advisor-family" | "collaboration"; returnHref: "/demo" | "/demo/collaboration"; onEnd: () => void }) {
  const label = currentJourney === "advisor-family" ? "advisor-family walkthrough" : "collaboration walkthrough";
  return (
    <section className="recovery-notice" role="alert" aria-labelledby="journey-conflict-title">
      <h1 id="journey-conflict-title">Another walkthrough is active</h1>
      <p>The same-tab {label} remains authoritative. End it through the server before starting a different journey.</p>
      <div className="action-row">
        <Link href={returnHref}>Return to current walkthrough</Link>
        <button type="button" onClick={onEnd}>End current walkthrough and continue</button>
      </div>
    </section>
  );
}
