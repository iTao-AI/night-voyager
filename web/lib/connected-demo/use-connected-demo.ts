"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import { ConnectedDemoApiError, createConnectedDemoApi } from "./api";
import type { FamilyDecisionBody } from "./contracts";
import { idempotencyFor } from "./idempotency";
import { demoReducer, type DemoDisplayState, type RecoveryCode } from "./reducer";
import {
  clearRecoveryMetadata, loadDemoJourneyEnvelope, loadRecoveryMetadata, saveRecoveryMetadata, withMutation,
  type MutationOperation, type RecoveryMetadata,
} from "./session-storage";

const api = createConnectedDemoApi();
const initial: DemoDisplayState = { value: "bootstrapping" };
const CASE_ID = "40000000-0000-0000-0000-000000000002";

function failure(error: unknown): RecoveryCode {
  if (error instanceof ConnectedDemoApiError && error.status === 401) return "session_expired";
  if (error instanceof ConnectedDemoApiError && error.code === "bff_session_recovery_required") return "session_recovery_required";
  if (error instanceof ConnectedDemoApiError && error.status === 409) return "stale_conflict";
  return "transport_failure";
}

export function useConnectedDemo() {
  const [state, dispatch] = useReducer(demoReducer, initial);
  const [confirmed, setConfirmed] = useState(false);
  const [journeyConflict, setJourneyConflict] = useState<"collaboration" | null>(() => {
    if (typeof window === "undefined") return null;
    return loadDemoJourneyEnvelope()?.journey === "collaboration" ? "collaboration" : null;
  });
  const recoveryStarted = useRef(false);
  const retryAction = useRef<null | (() => Promise<void>)>(null);

  const connectAdvisor = useCallback(async () => {
    const existing = loadDemoJourneyEnvelope();
    if (existing?.journey === "collaboration") {
      setJourneyConflict("collaboration");
      return;
    }
    try {
      const { csrf_token: bootstrapCsrf } = await api.bootstrap();
      const session = await api.mint("advisor", bootstrapCsrf);
      const ledger = await api.advisorLedger(CASE_ID);
      if (ledger.case_id !== CASE_ID) throw new Error("invalid response");
      const taskId = ["active-task", "review-required", "terminal-task-failure"].includes(ledger.phase)
        ? ledger.task?.task_id ?? null
        : null;
      saveRecoveryMetadata({ schema_version: 2, journey: "advisor-family", role: "advisor", csrf: session.csrf_token, caseId: CASE_ID, taskId, briefId: null, cursor: 0, mutations: {} });
      dispatch({ type: "AUTHORITATIVE_RELOAD", ledger });
    } catch (error) {
      dispatch({ type: "RECOVERABLE_FAILURE", code: failure(error) });
    }
  }, []);

  const recover = useCallback(async () => {
    const journey = loadDemoJourneyEnvelope();
    if (journey?.journey === "collaboration") {
      setJourneyConflict("collaboration");
      return;
    }
    const metadata = loadRecoveryMetadata();
    if (!metadata) {
      await connectAdvisor();
      return;
    }
    try {
      if (metadata.role === "parent") {
        try {
          await api.advisorLedger(metadata.caseId);
          throw new Error("role projection mismatch");
        } catch (error) {
          if (!(error instanceof ConnectedDemoApiError) || error.status !== 404) throw error;
        }
        const brief = await api.currentBrief(metadata.caseId);
        if (brief.case_id !== metadata.caseId || brief.brief_id !== metadata.briefId) throw new Error("projection identity mismatch");
        dispatch({ type: "AUTHORITATIVE_RELOAD", brief });
      } else {
        const ledger = await api.advisorLedger(metadata.caseId);
        if (ledger.case_id !== metadata.caseId) throw new Error("projection identity mismatch");
        const projectedTaskId = ledger.task?.task_id ?? null;
        const taskPhase = ["active-task", "review-required", "terminal-task-failure"].includes(ledger.phase);
        if ((taskPhase && metadata.taskId !== projectedTaskId) || (!taskPhase && metadata.taskId !== null && projectedTaskId !== metadata.taskId)) throw new Error("projection identity mismatch");
        dispatch({ type: "AUTHORITATIVE_RELOAD", ledger });
      }
    } catch (error) {
      const code = failure(error);
      if (code === "session_expired") clearRecoveryMetadata();
      dispatch({ type: "RECOVERABLE_FAILURE", code });
    }
  }, [connectAdvisor]);

  useEffect(() => {
    if (recoveryStarted.current) return;
    recoveryStarted.current = true;
    const journey = loadDemoJourneyEnvelope();
    if (journey?.journey === "advisor-family") queueMicrotask(() => { void recover(); });
  }, [recover]);

  const streamingTaskId = state.value === "task_streaming" ? state.taskId : null;
  useEffect(() => {
    if (!streamingTaskId) return;
    const metadata = loadRecoveryMetadata();
    if (!metadata || metadata.role !== "advisor" || metadata.taskId !== streamingTaskId) {
      dispatch({ type: "RECOVERABLE_FAILURE", code: "session_recovery_required" });
      return;
    }
    let cursor = metadata.cursor;
    let refreshing = false;
    let pending = false;
    let closed = false;
    const events = new EventSource(`/api/demo/tasks/${streamingTaskId}/events?after=${cursor}`);
    const runRefresh = async () => {
      if (refreshing || closed) { pending = true; return; }
      refreshing = true;
      try {
        do {
          pending = false;
          const ledger = await api.advisorLedger(metadata.caseId);
          if (closed) return;
          const current = loadRecoveryMetadata();
          if (!current || current.taskId !== streamingTaskId) throw new Error("projection identity mismatch");
          saveRecoveryMetadata({ ...current, cursor: Math.max(current.cursor, cursor) });
          dispatch({ type: "TASK_REFRESHED", ledger, after: cursor });
        } while (pending && !closed);
      } catch (error) {
        if (!closed) dispatch({ type: "RECOVERABLE_FAILURE", code: failure(error) });
      } finally { refreshing = false; }
    };
    const refresh = (event: Event) => {
      const sequence = Number((event as MessageEvent).lastEventId);
      if (Number.isSafeInteger(sequence) && sequence >= 0) cursor = Math.max(cursor, sequence);
      void runRefresh();
    };
    for (const code of ["queued", "lease_acquired", "execution_started", "heartbeat_recorded", "retry_scheduled", "lease_reclaimed", "waiting_review", "succeeded", "blocked", "timed_out", "failed", "cancelled"]) events.addEventListener(code, refresh);
    return () => { closed = true; events.close(); };
  }, [streamingTaskId]);

  const mutationRecord = useCallback(async (metadata: RecoveryMetadata, operation: MutationOperation, body: unknown) => {
    const record = await idempotencyFor(body, metadata.mutations[operation]);
    const updated = withMutation(metadata, operation, record);
    saveRecoveryMetadata(updated);
    return { record, updated };
  }, []);

  const createTask = useCallback(async () => {
    if (state.value !== "advisor_ready" || !state.ledger.canonical_task_inputs) return;
    const metadata = loadRecoveryMetadata();
    if (!metadata || metadata.role !== "advisor") return;
    const inputs = state.ledger.canonical_task_inputs;
    const body = { schema_version: 1 as const, operation: inputs.operation, expected_case_revision: inputs.expected_case_revision, source_pack_id: inputs.source_pack_id, source_pack_version: inputs.source_pack_version, policy_version: inputs.policy_version };
    const attempt = async () => {
      try {
        const current = loadRecoveryMetadata() ?? metadata;
        const { record, updated } = await mutationRecord(current, "create-task", body);
        const task = await api.createTask(current.caseId, body, current.csrf, record.idempotencyKey);
        saveRecoveryMetadata({ ...updated, taskId: task.task_id, cursor: 0 });
        retryAction.current = null;
        dispatch({ type: "TASK_ACCEPTED", taskId: task.task_id });
      } catch (error) {
        const code = failure(error);
        if (code === "session_expired") { retryAction.current = null; clearRecoveryMetadata(); }
        if (code === "stale_conflict") { retryAction.current = null; await recover(); } else dispatch({ type: "RECOVERABLE_FAILURE", code });
      }
    };
    retryAction.current = attempt;
    dispatch({ type: "CREATE_TASK" });
    await attempt();
  }, [mutationRecord, recover, state]);

  const rotateToParent = useCallback(async (caseId: string) => {
    const metadata = loadRecoveryMetadata();
    if (!metadata || metadata.role !== "advisor" || metadata.caseId !== caseId) { dispatch({ type: "RECOVERABLE_FAILURE", code: "session_recovery_required" }); return; }
    try {
      await api.revoke(metadata.csrf);
      clearRecoveryMetadata();
      const bootstrap = await api.bootstrap();
      const parent = await api.mint("parent", bootstrap.csrf_token);
      const brief = await api.currentBrief(caseId);
      if (brief.case_id !== caseId) throw new Error("projection identity mismatch");
      saveRecoveryMetadata({ schema_version: 2, journey: "advisor-family", role: "parent", csrf: parent.csrf_token, caseId, taskId: null, briefId: brief.brief_id, cursor: 0, mutations: {} });
      dispatch({ type: "PARENT_SESSION_READY", brief });
    } catch (error) { dispatch({ type: "RECOVERABLE_FAILURE", code: failure(error) }); }
  }, []);

  const approve = useCallback(async () => {
    if (state.value !== "advisor_review" || !state.ledger.review_inputs) return;
    const metadata = loadRecoveryMetadata();
    if (!metadata || metadata.role !== "advisor") return;
    const review = state.ledger.review_inputs;
    const body = { schema_version: 1 as const, planning_run_id: review.planning_run_id, expected_case_revision: review.expected_case_revision, action: "approve_for_consultation" as const, eligible_route_ids: review.eligible_route_ids, risk_acceptances: review.risk_acceptance_options };
    const attempt = async () => {
      try {
        const current = loadRecoveryMetadata() ?? metadata;
        const { record } = await mutationRecord(current, "advisor-review", body);
        await api.review(current.caseId, body, current.csrf, record.idempotencyKey);
        retryAction.current = null;
        dispatch({ type: "REVIEW_ACCEPTED", caseId: current.caseId });
        await rotateToParent(current.caseId);
      } catch (error) {
        const code = failure(error);
        if (code === "session_expired") { retryAction.current = null; clearRecoveryMetadata(); }
        if (code === "stale_conflict") { retryAction.current = null; await recover(); } else dispatch({ type: "RECOVERABLE_FAILURE", code });
      }
    };
    retryAction.current = attempt;
    dispatch({ type: "REVIEW_SUBMIT" });
    await attempt();
  }, [mutationRecord, recover, rotateToParent, state]);

  const decide = useCallback(async () => {
    if (state.value !== "family_review" || !confirmed) return;
    const metadata = loadRecoveryMetadata();
    if (!metadata || metadata.role !== "parent" || metadata.briefId !== state.brief.brief_id) return;
    const requirements = state.brief.decision_requirements;
    const body: FamilyDecisionBody = { schema_version: 1, expected_brief_version: state.brief.brief_version, selected_route_id: requirements.eligible_route_id, accepted_budget_min_minor: requirements.pinned_cost_minor, accepted_budget_max_minor: requirements.hard_ceiling_minor, currency: requirements.currency, accepted_trade_offs: requirements.required_trade_offs };
    const attempt = async () => {
      try {
        const current = loadRecoveryMetadata() ?? metadata;
        const { record } = await mutationRecord(current, "family-decision", body);
        await api.decide(state.brief.brief_id, body, current.csrf, record.idempotencyKey);
        const brief = await api.currentBrief(current.caseId);
        retryAction.current = null;
        dispatch({ type: "DECISION_ACCEPTED", brief });
      } catch (error) {
        const code = failure(error);
        if (code === "session_expired") { retryAction.current = null; clearRecoveryMetadata(); }
        if (code === "stale_conflict") {
          retryAction.current = null;
          setConfirmed(false);
          const current = loadRecoveryMetadata();
          if (current) saveRecoveryMetadata(withMutation(current, "family-decision", undefined));
          try { dispatch({ type: "AUTHORITATIVE_RELOAD", brief: await api.currentBrief(metadata.caseId) }); }
          catch (refreshError) { dispatch({ type: "RECOVERABLE_FAILURE", code: failure(refreshError) }); }
        } else dispatch({ type: "RECOVERABLE_FAILURE", code });
      }
    };
    retryAction.current = attempt;
    dispatch({ type: "DECISION_SUBMIT" });
    await attempt();
  }, [confirmed, mutationRecord, state]);

  const retry = useCallback(async () => {
    if (retryAction.current) await retryAction.current();
    else await recover();
  }, [recover]);

  const endConflictingJourney = useCallback(async () => {
    const existing = loadDemoJourneyEnvelope();
    if (!existing || existing.journey !== "collaboration") { setJourneyConflict(null); return; }
    try {
      await api.revoke(existing.csrf);
      clearRecoveryMetadata();
      setJourneyConflict(null);
      await connectAdvisor();
    } catch (error) {
      if (error instanceof ConnectedDemoApiError && error.status === 401) {
        clearRecoveryMetadata();
        setJourneyConflict(null);
        await connectAdvisor();
      } else {
        setJourneyConflict("collaboration");
        dispatch({ type: "RECOVERABLE_FAILURE", code: failure(error) });
      }
    }
  }, [connectAdvisor]);

  return { state, confirmed, setConfirmed, journeyConflict, endConflictingJourney, connectAdvisor, recover, retry, createTask, approve, rotateToParent, decide };
}
