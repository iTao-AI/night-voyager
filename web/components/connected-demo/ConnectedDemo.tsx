"use client";

import Link from "next/link";

import { useConnectedDemo } from "../../lib/connected-demo/use-connected-demo";
import { AdvisorLedger } from "./AdvisorLedger";
import { DecisionReceiptTimeline } from "./DecisionReceiptTimeline";
import { FamilyDecisionBrief } from "./FamilyDecisionBrief";
import { RecoveryNotice } from "./RecoveryNotice";
import { JourneyConflictNotice } from "../demo-session/JourneyConflictNotice";
import { PlanningSkillInspector } from "../skill-inspector/PlanningSkillInspector";

export function ConnectedDemo() {
  const demo = useConnectedDemo();
  const { state } = demo;
  const advisorAction = () => {
    if (state.value !== "advisor_ready" && state.value !== "advisor_review") return;
    if (state.value === "advisor_review") void demo.approve();
    else if (state.ledger.phase === "task-ready") void demo.createTask();
    else if (state.ledger.current_brief_id) void demo.rotateToParent(state.ledger.case_id);
  };
  const inspectorVisible = ["advisor_ready", "task_creating", "task_streaming", "advisor_review", "review_submitting", "terminal_task_failure"].includes(state.value);
  return (
    <>
      <a className="skip-link" href="#demo-main">Skip to decision workflow</a>
      <header className="site-header"><Link className="wordmark" href="/">Night Voyager</Link><nav aria-label="Demo context"><span>Connected advisor-to-family demo</span><strong>Synthetic demo</strong></nav></header>
      <main id="demo-main" className="demo-shell">
        {demo.journeyConflict === "collaboration" ? <JourneyConflictNotice currentJourney="collaboration" returnHref="/demo/collaboration" onEnd={() => void demo.endConflictingJourney()} /> : null}
        {state.value === "bootstrapping" && !demo.journeyConflict ? (
          <section className="ledger-hero"><p className="overline">Local synthetic pilot</p><h1>Connected advisor-to-family demo</h1><p className="lede">Follow real session, task, review, family decision, receipt, and timeline boundaries.</p><button className="primary-action" type="button" onClick={() => void demo.connectAdvisor()}>Start advisor walkthrough</button></section>
        ) : null}
        {["advisor_ready", "advisor_review"].includes(state.value) && "ledger" in state ? <AdvisorLedger ledger={state.ledger} onPrimaryAction={advisorAction} /> : null}
        {["task_creating", "task_streaming", "review_submitting"].includes(state.value) && "ledger" in state ? <AdvisorLedger ledger={state.ledger} busy onPrimaryAction={() => undefined} /> : null}
        {demo.inspector && inspectorVisible ? <PlanningSkillInspector inspector={demo.inspector} /> : null}
        {state.value === "role_switching" ? <section className="ledger-hero" aria-live="polite"><h1>Switching to family</h1><p>Advisor session revoked. Establishing the parent session.</p></section> : null}
        {state.value === "family_review" ? <FamilyDecisionBrief brief={state.brief} confirmed={demo.confirmed} onConfirm={demo.setConfirmed} onSubmit={() => void demo.decide()} /> : null}
        {state.value === "decision_submitting" ? <section className="ledger-hero" aria-live="polite"><h1>Recording family decision</h1></section> : null}
        {state.value === "plan_ready" ? <DecisionReceiptTimeline brief={state.brief} /> : null}
        {state.value === "terminal_task_failure" ? <AdvisorLedger ledger={state.ledger} onPrimaryAction={() => undefined} /> : null}
        {state.value === "recoverable_error" ? <RecoveryNotice code={state.code} onReconnect={() => void demo.retry()} /> : null}
      </main>
      <footer><p>Night Voyager · local synthetic pilot · evidence before authority</p></footer>
    </>
  );
}
