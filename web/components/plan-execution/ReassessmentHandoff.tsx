"use client";

import { useEffect, useRef, useState } from "react";
import type { ReassessmentHandoffSummary } from "../../lib/plan-execution/reassessment-handoff";
import { usePresentation } from "../../lib/presentation/context";

export function ReassessmentHandoff({ summary }: { summary: ReassessmentHandoffSummary }) {
  const { copy } = usePresentation();
  const [outcome, setOutcome] = useState<"idle" | "copying" | "copied" | "failed">("idle");
  const [identitiesOpen, setIdentitiesOpen] = useState(false);
  const alive = useRef(false);
  const copying = useRef(false);
  const fallback = useRef<HTMLTextAreaElement>(null);
  const feedback = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; };
  }, []);

  useEffect(() => {
    if (outcome === "failed") {
      fallback.current?.focus();
      fallback.current?.select();
    } else if (outcome === "copied") feedback.current?.focus();
  }, [outcome]);

  async function copySummary() {
    if (copying.current) return;
    copying.current = true;
    setOutcome("copying");
    try {
      if (!navigator.clipboard?.writeText) throw new Error("clipboard unavailable");
      await navigator.clipboard.writeText(summary.text);
      if (alive.current) setOutcome("copied");
    } catch {
      if (alive.current) setOutcome("failed");
    } finally {
      copying.current = false;
    }
  }

  return (
    <section className="reassessment-handoff" aria-labelledby="reassessment-handoff-title">
      <h3 id="reassessment-handoff-title">{copy("planExecutionHandoffTitle")}</h3>
      <p>{copy("planExecutionReassessmentStop")}</p>
      <p>{copy("planExecutionHandoffPending")}</p>
      <p>{copy("planExecutionWhoNext")}</p>
      <dl className="handoff-facts">
        {summary.facts.map(({ label, value }) => (
          <div key={label}><dt>{label}</dt><dd>{value}</dd></div>
        ))}
      </dl>
      <details className="handoff-identities"
        onToggle={(event) => setIdentitiesOpen(event.currentTarget.open)}>
        <summary>{copy("handoffIdentities")}</summary>
        {identitiesOpen && <>
          <dl className="handoff-facts">
            {summary.identities.map(({ label, value }) => (
              <div key={label}><dt>{label}</dt><dd>{value}</dd></div>
            ))}
          </dl>
          <p>{copy("handoffProjectionNote")}</p>
        </>}
      </details>
      <button type="button" disabled={outcome === "copying"}
        aria-describedby={outcome === "copied" || outcome === "failed" ? "handoff-copy-feedback" : undefined}
        onClick={() => void copySummary()}>
        {copy(outcome === "copying" ? "handoffCopying" : "handoffCopy")}
      </button>
      {(outcome === "copied" || outcome === "failed") && (
        <p ref={feedback} tabIndex={-1} id="handoff-copy-feedback">
          {copy(outcome === "copied" ? "handoffCopied" : "handoffCopyFailed")}
        </p>
      )}
      {outcome === "failed" && (
        <label className="handoff-fallback">
          {copy("handoffSelectableText")}
          <textarea ref={fallback} readOnly value={summary.text} rows={12}
            onFocus={(event) => event.currentTarget.select()} />
        </label>
      )}
    </section>
  );
}
