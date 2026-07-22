"use client";

import { useConnectedDemo } from "../../lib/connected-demo/use-connected-demo";
import { usePresentation } from "../../lib/presentation/context";
import { PresentationShell } from "../presentation/PresentationShell";
import { AdvisorLedger } from "./AdvisorLedger";
import { DecisionReceiptTimeline } from "./DecisionReceiptTimeline";
import { FamilyDecisionBrief } from "./FamilyDecisionBrief";
import { RecoveryNotice } from "./RecoveryNotice";
import { JourneyConflictNotice } from "../demo-session/JourneyConflictNotice";
import { PlanningSkillInspector } from "../skill-inspector/PlanningSkillInspector";

export function ConnectedDemo() {
  const demo = useConnectedDemo();
  const { copy } = usePresentation();
  const { state } = demo;
  const advisorAction = () => {
    if (state.value !== "advisor_ready" && state.value !== "advisor_review") return;
    if (state.value === "advisor_review") void demo.approve();
    else if (state.ledger.phase === "task-ready") void demo.createTask();
    else if (state.ledger.current_brief_id) void demo.rotateToParent(state.ledger.case_id);
  };
  const inspectorVisible = ["advisor_ready", "task_creating", "task_streaming", "advisor_review", "review_submitting", "terminal_task_failure"].includes(state.value);
  const confirmedFactsFor = (caseId: string, caseRevision: number) => demo.currentFacts?.caseId === caseId && demo.currentFacts.caseRevision === caseRevision ? demo.currentFacts.facts : null;

  return (
    <PresentationShell contextKey="contextAdvisorFamily" mainId="demo-main">
      <div className="demo-shell">
        {demo.journeyConflict === "collaboration" ? <JourneyConflictNotice currentJourney="collaboration" returnHref="/demo/collaboration" onEnd={() => void demo.endConflictingJourney()} /> : null}
        {state.value === "bootstrapping" && !demo.journeyConflict ? (
          <section className="ledger-hero"><p className="overline">{copy("demoStartOverline")}</p><h1>{copy("demoStartTitle")}</h1><p className="lede">{copy("demoStartBody")}</p><button className="primary-action" type="button" onClick={() => void demo.connectAdvisor()}>{copy("demoStartAction")}</button></section>
        ) : null}
        {["advisor_ready", "advisor_review"].includes(state.value) && "ledger" in state ? <AdvisorLedger ledger={state.ledger} confirmedFacts={confirmedFactsFor(state.ledger.case_id, state.ledger.case_revision)} onPrimaryAction={advisorAction} /> : null}
        {["task_creating", "task_streaming", "review_submitting"].includes(state.value) && "ledger" in state ? <AdvisorLedger ledger={state.ledger} confirmedFacts={confirmedFactsFor(state.ledger.case_id, state.ledger.case_revision)} busy onPrimaryAction={() => undefined} /> : null}
        {demo.inspector && inspectorVisible ? <PlanningSkillInspector inspector={demo.inspector} /> : null}
        {state.value === "role_switching" ? <section className="ledger-hero" aria-live="polite"><h1>{copy("demoSwitchingTitle")}</h1><p>{copy("demoSwitchingBody")}</p></section> : null}
        {state.value === "family_review" ? <FamilyDecisionBrief brief={state.brief} confirmed={demo.confirmed} onConfirm={demo.setConfirmed} onSubmit={() => void demo.decide()} /> : null}
        {state.value === "decision_submitting" ? <section className="ledger-hero" aria-live="polite"><h1>{copy("demoRecordingDecision")}</h1></section> : null}
        {state.value === "plan_ready" ? <DecisionReceiptTimeline brief={state.brief} /> : null}
        {state.value === "terminal_task_failure" ? <AdvisorLedger ledger={state.ledger} confirmedFacts={confirmedFactsFor(state.ledger.case_id, state.ledger.case_revision)} onPrimaryAction={() => undefined} /> : null}
        {state.value === "recoverable_error" ? <RecoveryNotice code={state.code} onReconnect={() => void demo.retry()} /> : null}
      </div>
    </PresentationShell>
  );
}
