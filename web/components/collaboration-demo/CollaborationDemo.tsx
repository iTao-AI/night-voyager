"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";

import { useCollaborationDemo } from "../../lib/collaboration-demo/use-collaboration-demo";
import { JourneyConflictNotice } from "../demo-session/JourneyConflictNotice";
import { CollaborationRecoveryNotice } from "./CollaborationRecoveryNotice";
import { ConfirmedFactSummary } from "./ConfirmedFactSummary";
import { MemoryCandidateCard } from "./MemoryCandidateCard";
import { SharedThread } from "./SharedThread";
import { PlanningSkillInspector } from "../skill-inspector/PlanningSkillInspector";

export function CollaborationDemo() {
  const demo = useCollaborationDemo();
  const { state } = demo;
  const phaseHeading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (["advisor_reviewing", "replan_required", "handoff_validating", "recoverable_error"].includes(state.value)) phaseHeading.current?.focus();
  }, [state.value]);

  const context = state.context;
  const busy = state.value === "message_submitting" || state.value === "confirmation_submitting" || state.value === "switching_to_advisor";
  const advisorCandidate = context.candidate && "candidate_id" in context.candidate ? context.candidate : null;
  const canConfirm = state.value === "advisor_reviewing" && advisorCandidate?.state === "pending" && advisorCandidate.case_revision === context.caseRevision;

  return (
    <>
      <a className="skip-link" href="#collaboration-main">Skip to collaboration workflow</a>
      <header className="site-header">
        <Link className="wordmark" href="/">Night Voyager</Link>
        <nav aria-label="Demo context"><Link href="/demo">Primary demo</Link><span>Governed collaboration</span><strong>Synthetic demo</strong></nav>
      </header>
      <main id="collaboration-main" className="demo-shell collaboration-shell">
        {demo.journeyConflict === "advisor-family" ? <JourneyConflictNotice currentJourney="advisor-family" returnHref="/demo" onEnd={() => void demo.endConflictingJourney()} /> : null}
        {!demo.journeyConflict ? (
          <>
            <section className="ledger-hero collaboration-hero" aria-labelledby="collaboration-title">
              <p className="overline">Local synthetic pilot · secondary walkthrough</p>
              <h1 id="collaboration-title">Governed collaboration walkthrough</h1>
              <p className="lede">A parent message becomes a typed proposal only after an explicit action, and becomes a Case fact only after assigned-advisor confirmation.</p>
              <p className="role-status" role="status">Role: {context.role === "parent" ? "Parent" : "Advisor"}</p>
              <ol className="authority-steps" aria-label="Collaboration authority path">
                <li>Shared message</li><li>Typed proposal</li><li>Advisor review</li><li>Confirmed fact</li><li>Case revision</li><li>Re-plan required</li>
              </ol>
              {state.value === "bootstrapping_parent" ? <button className="primary-action" type="button" onClick={() => void demo.connectParent()}>Start parent walkthrough</button> : null}
            </section>

            {context.thread ? <SharedThread messages={context.messages} loading={busy && context.messages.length === 0} /> : null}

            {state.value === "thread_ready" ? (
              <section className="collaboration-action" aria-labelledby="parent-action-title">
                <h2 id="parent-action-title">{context.messages.length ? "Propose one typed family fact" : "Add the family’s confirmed budget"}</h2>
                <p>{context.messages.length ? "The proposal stays pending until the assigned advisor reviews it." : "This message remains communication and does not change the Case."}</p>
                <button type="button" onClick={() => void (context.messages.length ? demo.proposeBudget() : demo.appendMessage())}>{context.messages.length ? "Propose this budget for advisor review" : "Add confirmed budget message"}</button>
              </section>
            ) : null}

            {state.value === "message_submitting" ? <section className="collaboration-action" aria-live="polite"><h2>Recording parent message</h2><button type="button" disabled>Recording message…</button></section> : null}

            {context.candidate ? <MemoryCandidateCard candidate={context.candidate} /> : null}
            {context.role === "advisor" && demo.inspector ? <PlanningSkillInspector inspector={demo.inspector} /> : null}

            {state.value === "proposal_pending" ? (
              <section className="collaboration-action" aria-labelledby="switch-title"><h2 id="switch-title">Move to advisor review</h2><p>The parent session must be revoked before an advisor session is minted.</p><button type="button" onClick={() => void demo.switchToAdvisor()}>Continue as assigned advisor</button></section>
            ) : null}

            {state.value === "switching_to_advisor" ? <section className="collaboration-action" aria-live="polite"><h2>Switching authority</h2><p>Revoking the parent session and loading the advisor projection.</p><button type="button" disabled>Switching role…</button></section> : null}

            {state.value === "advisor_reviewing" ? (
              <section className="collaboration-action" aria-labelledby="advisor-confirmation-title"><h2 id="advisor-confirmation-title" ref={phaseHeading} tabIndex={-1}>Advisor confirmation</h2><p>The candidate revision and current Case revision must agree before confirmation.</p><button type="button" disabled={!canConfirm} onClick={() => void demo.confirmCandidate()}>Confirm family budget</button>{!canConfirm ? <p className="disabled-reason">Reload current Case and candidate authority before confirming.</p> : null}</section>
            ) : null}

            {state.value === "confirmation_submitting" ? <section className="collaboration-action" aria-live="polite"><h2>Publishing confirmed authority</h2><button type="button" disabled>Confirming fact and Case revision…</button></section> : null}

            {["replan_required", "handoff_validating"].includes(state.value) && context.fact ? <ConfirmedFactSummary fact={context.fact} caseRevision={context.caseRevision} /> : null}

            {state.value === "replan_required" && context.fact ? (
              <section className="collaboration-action replan-boundary" aria-labelledby="replan-title"><h2 id="replan-title" ref={phaseHeading} tabIndex={-1}>Re-plan required</h2><p>The Case revision changed. This walkthrough creates no task; the destination will reload current authority before the advisor can explicitly start planning.</p><button className="primary-action" type="button" onClick={() => void demo.continueToPlanning()}>Continue to governed planning</button></section>
            ) : null}

            {state.value === "handoff_validating" && context.fact ? (
              <section className="collaboration-action replan-boundary" aria-labelledby="handoff-title" aria-live="polite"><h2 id="handoff-title" ref={phaseHeading} tabIndex={-1}>Validating planning authority</h2><p>Reloading current candidate, fact, Case revision, and advisor ledger before navigation.</p><button className="primary-action" type="button" disabled>Validating authority…</button></section>
            ) : null}

            {state.value === "recoverable_error" ? <CollaborationRecoveryNotice category={state.category} onRetry={() => void demo.retry()} headingRef={phaseHeading} /> : null}
          </>
        ) : null}
      </main>
      <footer><p>Night Voyager · local synthetic pilot · message is not authority</p></footer>
    </>
  );
}
