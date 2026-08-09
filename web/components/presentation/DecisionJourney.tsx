import type { PresentationCopyKey } from "../../lib/presentation/catalog";
import { JOURNEY_STAGES, type JourneyStage } from "../../lib/presentation/journey";

type DecisionJourneyProps = {
  currentStage: JourneyStage;
  copy: (key: PresentationCopyKey) => string;
};

const STAGE_COPY: Record<JourneyStage, { label: PresentationCopyKey; body: PresentationCopyKey }> = {
  family_input: { label: "journeyStageFamilyInput", body: "journeyStageFamilyInputBody" },
  advisor_confirmation: { label: "journeyStageAdvisorConfirmation", body: "journeyStageAdvisorConfirmationBody" },
  route_review: { label: "journeyStageRouteReview", body: "journeyStageRouteReviewBody" },
  family_decision: { label: "journeyStageFamilyDecision", body: "journeyStageFamilyDecisionBody" },
  plan_execution: { label: "journeyStagePlanExecution", body: "journeyStagePlanExecutionBody" },
};

export function DecisionJourney({ currentStage, copy }: DecisionJourneyProps) {
  const currentIndex = JOURNEY_STAGES.indexOf(currentStage);

  return (
    <section className="decision-journey" data-testid="decision-journey" data-current-stage={currentStage} aria-labelledby="decision-journey-title">
      <header className="decision-journey-header">
        <div>
          <p className="overline">{copy("journeyOverline")}</p>
          <h2 id="decision-journey-title">{copy("journeyTitle")}</h2>
          <p>{copy("journeyDescription")}</p>
        </div>
        <p className="decision-journey-current">
          {copy("journeyCurrentLabel")}{copy("journeyCurrentSeparator")}<strong>{copy(STAGE_COPY[currentStage].label)}</strong>
        </p>
      </header>
      <ol className="decision-journey-track">
        {JOURNEY_STAGES.map((stage, index) => {
          const state = index < currentIndex ? "complete" : index === currentIndex ? "current" : "upcoming";
          const stageCopy = STAGE_COPY[stage];
          return (
            <li data-stage={stage} data-state={state} key={stage} aria-current={state === "current" ? "step" : undefined}>
              <span className="decision-journey-number" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
              <strong>{copy(stageCopy.label)}</strong>
              <span>{copy(stageCopy.body)}</span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
