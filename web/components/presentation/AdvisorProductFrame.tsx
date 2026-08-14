import type { ReactNode } from "react";

export type AdvisorProductFrameProps = {
  topBand: ReactNode;
  workflow: ReactNode;
  context: ReactNode;
  currentWork: ReactNode;
  evidence?: ReactNode;
  authority: ReactNode;
  technical?: ReactNode;
  technicalLabel?: string;
  className?: string;
};

/**
 * A presentation-only product surface. Business state and callbacks stay in
 * the route that supplies these slots; this component only owns the reading
 * order and the 2 / 7 / 3 desktop composition.
 */
export function AdvisorProductFrame({
  topBand,
  workflow,
  context,
  currentWork,
  evidence,
  authority,
  technical,
  technicalLabel = "Technical evidence",
  className,
}: AdvisorProductFrameProps) {
  return (
    <article
      className={className ? `advisor-product-frame ${className}` : "advisor-product-frame"}
      data-product-frame
    >
      <div className="advisor-product-frame-top-band" data-frame-slot="top-band">
        {topBand}
      </div>
      <div className="advisor-product-frame-workflow" data-frame-slot="workflow">
        {workflow}
      </div>
      <div className={`advisor-product-frame-grid${evidence ? " has-evidence" : ""}`}>
        <aside className="advisor-product-frame-context" data-frame-slot="context" data-column-span="2">
          {context}
        </aside>
        <section className="advisor-product-frame-work" data-frame-slot="work" data-column-span="7">
          {currentWork}
        </section>
        {evidence ? (
          <section className="advisor-product-frame-evidence" data-frame-slot="evidence" data-column-span="7">
            {evidence}
          </section>
        ) : null}
        <aside className="advisor-product-frame-authority" data-frame-slot="authority" data-column-span="3">
          {authority}
        </aside>
      </div>
      <details className="advisor-product-frame-technical" data-frame-slot="technical">
        <summary>{technicalLabel}</summary>
        {technical ?? <p>No technical evidence is available.</p>}
      </details>
    </article>
  );
}
