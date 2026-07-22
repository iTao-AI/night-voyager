"use client";

import Link from "next/link";

import { usePresentation } from "../../lib/presentation/context";

export function JourneyConflictNotice({ currentJourney, returnHref, onEnd }: { currentJourney: "advisor-family" | "collaboration"; returnHref: "/demo" | "/demo/collaboration"; onEnd: () => void }) {
  const { copy } = usePresentation();
  return (
    <section className="recovery-notice" role="alert" aria-labelledby="journey-conflict-title">
      <h1 id="journey-conflict-title">{copy("journeyConflictTitle")}</h1>
      <p><strong>{copy(currentJourney === "advisor-family" ? "journeyAdvisorFamily" : "journeyCollaboration")}</strong> — {copy("journeyConflictBody")}</p>
      <div className="action-row">
        <Link href={returnHref}>{copy("journeyReturn")}</Link>
        <button type="button" onClick={onEnd}>{copy("journeyEnd")}</button>
      </div>
    </section>
  );
}
