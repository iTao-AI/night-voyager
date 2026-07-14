"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import { createConnectedDemoApi } from "./api";
import type { FamilyDecisionBody } from "./contracts";
import { idempotencyFor } from "./idempotency";
import { demoReducer, type DemoDisplayState } from "./reducer";
import { clearRecoveryMetadata, loadRecoveryMetadata, saveRecoveryMetadata } from "./session-storage";

const api = createConnectedDemoApi();
const initial: DemoDisplayState = { value: "bootstrapping" };

export function useConnectedDemo() {
  const [state, dispatch] = useReducer(demoReducer, initial);
  const [confirmed, setConfirmed] = useState(false);
  const recoveryStarted = useRef(false);

  const connectAdvisor = useCallback(async () => {
    try {
      const { csrf_token: bootstrapCsrf } = await api.bootstrap();
      const session = await api.mint("advisor", bootstrapCsrf);
      const caseId = "40000000-0000-0000-0000-000000000002";
      const ledger = await api.advisorLedger(caseId);
      saveRecoveryMetadata({ role: "advisor", csrf: session.csrf_token, caseId, taskId: null, briefId: null, cursor: 0 });
      dispatch({ type: "ADVISOR_SESSION_READY", ledger });
    } catch (error) {
      const code = error instanceof Error && error.message === "bff_session_recovery_required" ? "session_recovery_required" : "transport_failure";
      dispatch({ type: "RECOVERABLE_FAILURE", code });
    }
  }, []);

  const recover = useCallback(async () => {
    const metadata = loadRecoveryMetadata();
    if (!metadata) {
      dispatch({ type: "RECOVERABLE_FAILURE", code: "session_recovery_required" });
      return;
    }
    try {
      if (metadata.role === "parent") {
        dispatch({ type: "AUTHORITATIVE_RELOAD", brief: await api.currentBrief(metadata.caseId) });
      } else {
        dispatch({ type: "AUTHORITATIVE_RELOAD", ledger: await api.advisorLedger(metadata.caseId) });
      }
    } catch {
      clearRecoveryMetadata();
      dispatch({ type: "RECOVERABLE_FAILURE", code: "session_expired" });
    }
  }, []);

  useEffect(() => {
    if (recoveryStarted.current) return;
    recoveryStarted.current = true;
    if (loadRecoveryMetadata()) void recover();
  }, [recover]);

  useEffect(() => {
    if (state.value !== "task_streaming") return;
    const metadata = loadRecoveryMetadata();
    if (!metadata) {
      dispatch({ type: "RECOVERABLE_FAILURE", code: "session_recovery_required" });
      return;
    }
    const events = new EventSource(`/api/demo/tasks/${state.taskId}/events?after=${metadata.cursor}`);
    const refresh = async (event: Event) => {
      try {
        const message = event as MessageEvent;
        const after = Number(message.lastEventId || metadata.cursor);
        const ledger = await api.advisorLedger(metadata.caseId);
        saveRecoveryMetadata({ ...metadata, cursor: after, taskId: state.taskId });
        dispatch({ type: "TASK_REFRESHED", ledger, after });
      } catch {
        dispatch({ type: "RECOVERABLE_FAILURE", code: "transport_failure" });
      }
    };
    const eventCodes = [
      "queued", "lease_acquired", "execution_started", "heartbeat_recorded",
      "retry_scheduled", "lease_reclaimed", "waiting_review", "succeeded",
      "blocked", "timed_out", "failed", "cancelled",
    ];
    for (const code of eventCodes) events.addEventListener(code, refresh);
    return () => events.close();
  }, [state]);

  const createTask = useCallback(async () => {
    if (state.value !== "advisor_ready" || !state.ledger.canonical_task_inputs) return;
    const metadata = loadRecoveryMetadata();
    if (!metadata || metadata.role !== "advisor") return;
    dispatch({ type: "CREATE_TASK" });
    try {
      const inputs = state.ledger.canonical_task_inputs;
      const body = {
        schema_version: 1 as const,
        operation: inputs.operation,
        expected_case_revision: inputs.expected_case_revision,
        source_pack_id: inputs.source_pack_id,
        source_pack_version: inputs.source_pack_version,
        policy_version: inputs.policy_version,
      };
      const idempotency = await idempotencyFor(body);
      const task = await api.createTask(metadata.caseId, body, metadata.csrf, idempotency.idempotencyKey);
      saveRecoveryMetadata({ ...metadata, taskId: task.task_id, cursor: 0 });
      dispatch({ type: "TASK_ACCEPTED", taskId: task.task_id });
    } catch {
      dispatch({ type: "RECOVERABLE_FAILURE", code: "transport_failure" });
    }
  }, [state]);

  const rotateToParent = useCallback(async (caseId: string) => {
    const metadata = loadRecoveryMetadata();
    if (!metadata || metadata.role !== "advisor") {
      dispatch({ type: "RECOVERABLE_FAILURE", code: "session_recovery_required" });
      return;
    }
    try {
      await api.revoke(metadata.csrf);
      clearRecoveryMetadata();
      const bootstrap = await api.bootstrap();
      const parent = await api.mint("parent", bootstrap.csrf_token);
      const brief = await api.currentBrief(caseId);
      saveRecoveryMetadata({ role: "parent", csrf: parent.csrf_token, caseId, taskId: null, briefId: brief.brief_id, cursor: 0 });
      dispatch({ type: "PARENT_SESSION_READY", brief });
    } catch {
      dispatch({ type: "RECOVERABLE_FAILURE", code: "transport_failure" });
    }
  }, []);

  const approve = useCallback(async () => {
    if (state.value !== "advisor_review" || !state.ledger.review_inputs) return;
    const metadata = loadRecoveryMetadata();
    if (!metadata || metadata.role !== "advisor") return;
    dispatch({ type: "REVIEW_SUBMIT" });
    try {
      const review = state.ledger.review_inputs;
      const body = {
        schema_version: 1 as const,
        planning_run_id: review.planning_run_id,
        expected_case_revision: review.expected_case_revision,
        action: "approve_for_consultation" as const,
        eligible_route_ids: review.eligible_route_ids,
        risk_acceptances: review.risk_acceptance_options,
      };
      const idempotency = await idempotencyFor(body);
      await api.review(metadata.caseId, body, metadata.csrf, idempotency.idempotencyKey);
      dispatch({ type: "REVIEW_ACCEPTED", caseId: metadata.caseId });
      await rotateToParent(metadata.caseId);
    } catch {
      dispatch({ type: "RECOVERABLE_FAILURE", code: "transport_failure" });
    }
  }, [rotateToParent, state]);

  const decide = useCallback(async () => {
    if (state.value !== "family_review" || !confirmed) return;
    const metadata = loadRecoveryMetadata();
    if (!metadata || metadata.role !== "parent") return;
    const requirements = state.brief.decision_requirements;
    const body: FamilyDecisionBody = {
      schema_version: 1,
      expected_brief_version: state.brief.brief_version,
      selected_route_id: requirements.eligible_route_id,
      accepted_budget_min_minor: requirements.pinned_cost_minor,
      accepted_budget_max_minor: requirements.hard_ceiling_minor,
      currency: requirements.currency,
      accepted_trade_offs: requirements.required_trade_offs,
    };
    dispatch({ type: "DECISION_SUBMIT" });
    try {
      const idempotency = await idempotencyFor(body);
      await api.decide(state.brief.brief_id, body, metadata.csrf, idempotency.idempotencyKey);
      const brief = await api.currentBrief(metadata.caseId);
      dispatch({ type: "DECISION_ACCEPTED", brief });
    } catch {
      dispatch({ type: "RECOVERABLE_FAILURE", code: "stale_conflict" });
    }
  }, [confirmed, state]);

  return {
    state,
    confirmed,
    setConfirmed,
    connectAdvisor,
    recover,
    createTask,
    approve,
    rotateToParent,
    decide,
  };
}
