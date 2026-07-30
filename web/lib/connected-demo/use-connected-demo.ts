"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import { createCollaborationDemoApi } from "../collaboration-demo/api";
import type {
  CollaborationMessage,
  CollaborationThread,
  ConfirmedFactAdvisor,
  ConfirmedFactParticipant,
  MemoryCandidateAdvisor,
  MemoryCandidateParticipant,
} from "../collaboration-demo/contracts";
import type { PlanningSkillInspector } from "../skill-inspector/contracts";
import { ConnectedDemoApiError, createConnectedDemoApi } from "./api";
import type {
  AdvisorLedger,
  ConnectedJourneyStatus,
  FamilyDecisionBody,
} from "./contracts";
import { idempotencyFor } from "./idempotency";
import { demoReducer, type DemoDisplayState, type RecoveryCode } from "./reducer";
import {
  pendingPreferredCountriesCandidate,
  REVISED_PREFERRED_COUNTRIES,
  REVISION_PROPOSAL_MESSAGE,
} from "./revision";
import {
  clearRecoveryMetadata,
  loadDemoJourneyEnvelope,
  loadRecoveryMetadata,
  saveRecoveryMetadata,
  withMutation,
  type MutationOperation,
  type RecoveryMetadata,
} from "./session-storage";

const api = createConnectedDemoApi();
const collaboration = createCollaborationDemoApi();
const initial: DemoDisplayState = { value: "bootstrapping" };
const CASE_ID = "40000000-0000-0000-0000-000000000002";

export interface CurrentFactsProjection {
  caseId: string;
  caseRevision: number;
  facts: readonly (ConfirmedFactAdvisor | ConfirmedFactParticipant)[];
}

export interface RevisionCollaborationProjection {
  caseId: string;
  caseRevision: number;
  thread: CollaborationThread;
  messages: readonly CollaborationMessage[];
  candidates: readonly (MemoryCandidateAdvisor | MemoryCandidateParticipant)[];
  facts: readonly (ConfirmedFactAdvisor | ConfirmedFactParticipant)[];
}

function failure(error: unknown): RecoveryCode {
  if (error instanceof ConnectedDemoApiError && error.status === 401) return "session_expired";
  if (error instanceof ConnectedDemoApiError && error.code === "bff_session_recovery_required") return "session_recovery_required";
  if (error instanceof ConnectedDemoApiError && error.status === 409) return "stale_conflict";
  return "transport_failure";
}

function ledgerIdentity(ledger: AdvisorLedger): Pick<RecoveryMetadata, "currentTaskId" | "predecessorRunId" | "currentRunId"> {
  return {
    currentTaskId: [
      "active_task",
      "review_required",
      "revision_task_active",
      "revision_review_required",
      "revision_blocked",
      "terminal_task_failure",
    ].includes(ledger.phase) ? ledger.task?.task_id ?? null : null,
    predecessorRunId: ledger.comparison?.previous_planning_run_id ?? null,
    currentRunId: ledger.planning_run?.planning_run_id ?? null,
  };
}

function metadataFor(
  current: RecoveryMetadata | null,
  status: ConnectedJourneyStatus,
  role: RecoveryMetadata["role"],
  csrf: string,
  ledger?: AdvisorLedger,
): RecoveryMetadata {
  const identity = ledger ? ledgerIdentity(ledger) : {
    currentTaskId: null,
    predecessorRunId: null,
    currentRunId: null,
  };
  const sameTask = current?.currentTaskId !== null && current?.currentTaskId === identity.currentTaskId;
  return {
    schema_version: 3,
    journey: "advisor-family",
    role,
    csrf,
    caseId: status.case_id,
    currentRevision: status.current_revision,
    ...identity,
    cursor: sameTask ? current.cursor : 0,
    phase: status.phase,
    mutations: current?.mutations ?? {},
  };
}

function pendingRoleMetadata(
  current: RecoveryMetadata | null,
  status: ConnectedJourneyStatus,
  role: RecoveryMetadata["role"],
  csrf: string,
): RecoveryMetadata {
  const retained = current?.caseId === status.case_id && current.role === role
    ? current
    : null;
  return {
    schema_version: 3,
    journey: "advisor-family",
    role,
    csrf,
    caseId: status.case_id,
    currentRevision: status.current_revision,
    currentTaskId: retained?.currentTaskId ?? null,
    predecessorRunId: retained?.predecessorRunId ?? null,
    currentRunId: retained?.currentRunId ?? null,
    cursor: retained?.cursor ?? 0,
    phase: status.phase,
    mutations: retained?.mutations ?? {},
    pendingRole: status.active_role,
  };
}

export function useConnectedDemo() {
  const [state, dispatch] = useReducer(demoReducer, initial);
  const [confirmed, setConfirmed] = useState(false);
  const [inspector, setInspector] = useState<PlanningSkillInspector | null>(null);
  const [currentFacts, setCurrentFacts] = useState<CurrentFactsProjection | null>(null);
  const [revision, setRevision] = useState<RevisionCollaborationProjection | null>(null);
  const [journeyConflict, setJourneyConflict] = useState<"collaboration" | null>(() => {
    if (typeof window === "undefined") return null;
    return loadDemoJourneyEnvelope()?.journey === "collaboration" ? "collaboration" : null;
  });
  const recoveryStarted = useRef(false);
  const retryAction = useRef<null | (() => Promise<void>)>(null);
  const inspectorGeneration = useRef(0);

  const refreshInspector = useCallback(async (caseId: string) => {
    const generation = inspectorGeneration.current + 1;
    inspectorGeneration.current = generation;
    setInspector(null);
    try {
      const projection = await collaboration.planningSkillInspector(caseId);
      if (inspectorGeneration.current === generation) setInspector(projection);
    } catch {
      if (inspectorGeneration.current === generation) setInspector(null);
    }
  }, []);

  const loadRevisionProjection = useCallback(async (
    status: ConnectedJourneyStatus,
    role: "advisor" | "student",
  ): Promise<RevisionCollaborationProjection> => {
    const detailReads = role === "advisor"
      ? Promise.all([
          collaboration.confirmedFacts(status.case_id, "advisor"),
          collaboration.candidates(status.case_id, "advisor"),
        ])
      : Promise.all([
          collaboration.confirmedFacts(status.case_id, "student"),
          collaboration.candidates(status.case_id, "student"),
        ]);
    const [thread, [facts, candidates]] = await Promise.all([
      collaboration.thread(status.case_id),
      detailReads,
    ]);
    if (thread.case_id !== status.case_id) throw new Error("projection identity mismatch");
    const messages = await collaboration.messages(thread.thread_id);
    if (messages.items.some((message) => message.case_id !== status.case_id || message.thread_id !== thread.thread_id)) throw new Error("projection identity mismatch");
    return {
      caseId: status.case_id,
      caseRevision: status.current_revision,
      thread,
      messages: messages.items,
      candidates,
      facts: facts.current,
    };
  }, []);

  const loadAuthoritative = useCallback(async (
    caseId: string,
    role: RecoveryMetadata["role"],
    csrf: string,
    recoveryHint?: RecoveryMetadata,
  ) => {
    const status = await api.journeyStatus(caseId);
    if (status.case_id !== caseId) throw new Error("projection identity mismatch");
    const current = recoveryHint ?? loadRecoveryMetadata();
    if (status.active_role !== role) {
      saveRecoveryMetadata(pendingRoleMetadata(current, status, role, csrf));
      dispatch({ type: "ROLE_SWITCH", caseId, targetRole: status.active_role });
      return false;
    }
    if (role === "advisor") {
      const ledger = await api.advisorLedger(caseId);
      if (ledger.case_id !== caseId || ledger.case_revision !== status.current_revision || ledger.phase !== status.phase) throw new Error("projection identity mismatch");
      const facts = await collaboration.confirmedFacts(caseId, "advisor").catch(() => null);
      setCurrentFacts(facts ? { caseId, caseRevision: status.current_revision, facts: facts.current } : null);
      if (["revision_fact_pending", "replan_required", "revision_review_required", "revision_blocked"].includes(status.phase)) {
        setRevision(await loadRevisionProjection(status, "advisor"));
      } else {
        setRevision(null);
      }
      const metadata = metadataFor(current, status, role, csrf, ledger);
      saveRecoveryMetadata(metadata);
      dispatch({ type: "STATUS_RELOADED", status, ledger });
      if (!["active_task", "revision_task_active"].includes(status.phase)) void refreshInspector(caseId);
      return true;
    }
    setInspector(null);
    if (role === "student") {
      if (status.phase !== "revision_requested") throw new Error("role projection mismatch");
      const projection = await loadRevisionProjection(status, "student");
      setRevision(projection);
      setCurrentFacts({ caseId, caseRevision: status.current_revision, facts: projection.facts });
      saveRecoveryMetadata(metadataFor(current, status, role, csrf));
      dispatch({ type: "STATUS_RELOADED", status });
      return true;
    }
    setRevision(null);
    setCurrentFacts(null);
    const brief = await api.currentBrief(caseId);
    if (brief.case_id !== caseId || brief.phase !== status.phase || brief.revision_context.current_case_revision !== status.current_revision) throw new Error("projection identity mismatch");
    saveRecoveryMetadata(metadataFor(current, status, role, csrf));
    dispatch({ type: "STATUS_RELOADED", status, brief });
    return true;
  }, [loadRevisionProjection, refreshInspector]);

  const transitionRole = useCallback(async (
    metadata: RecoveryMetadata,
    target: RecoveryMetadata["role"],
  ) => {
    const attempt = async () => {
      let current = loadRecoveryMetadata() ?? metadata;
      try {
        if (current.caseId !== metadata.caseId) {
          throw new Error("role transition identity mismatch");
        }
        if (current.pendingRole !== target) {
          const status = await api.journeyStatus(current.caseId);
          if (status.case_id !== current.caseId || status.active_role !== target) {
            throw new Error("role transition authority mismatch");
          }
          current = pendingRoleMetadata(current, status, current.role, current.csrf);
          saveRecoveryMetadata(current);
        }
        try {
          await api.revoke(current.csrf);
        } catch (error) {
          if (!(error instanceof ConnectedDemoApiError) || error.status !== 401) throw error;
        }
        const bootstrap = await api.bootstrap();
        const session = await api.mint(target, bootstrap.csrf_token);
        const loaded = await loadAuthoritative(current.caseId, target, session.csrf_token, current);
        if (!loaded) throw new Error("role transition authority mismatch");
        retryAction.current = null;
      } catch (error) {
        dispatch({ type: "RECOVERABLE_FAILURE", code: failure(error) });
      }
    };
    retryAction.current = attempt;
    await attempt();
  }, [loadAuthoritative]);

  const connectAdvisor = useCallback(async () => {
    const existing = loadDemoJourneyEnvelope();
    if (existing?.journey === "collaboration") {
      setJourneyConflict("collaboration");
      return;
    }
    try {
      const bootstrap = await api.bootstrap();
      const session = await api.mint("advisor", bootstrap.csrf_token);
      await loadAuthoritative(CASE_ID, "advisor", session.csrf_token);
    } catch (error) {
      dispatch({ type: "RECOVERABLE_FAILURE", code: failure(error) });
    }
  }, [loadAuthoritative]);

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
    if (metadata.pendingRole) {
      await transitionRole(metadata, metadata.pendingRole);
      return;
    }
    try {
      await loadAuthoritative(metadata.caseId, metadata.role, metadata.csrf);
    } catch (error) {
      const code = failure(error);
      if (code === "session_expired") clearRecoveryMetadata();
      dispatch({ type: "RECOVERABLE_FAILURE", code });
    }
  }, [connectAdvisor, loadAuthoritative, transitionRole]);

  useEffect(() => {
    if (recoveryStarted.current) return;
    recoveryStarted.current = true;
    if (loadDemoJourneyEnvelope()?.journey === "advisor-family") queueMicrotask(() => { void recover(); });
  }, [recover]);

  const streamingTaskId = state.value === "task_streaming" ? state.taskId : null;
  useEffect(() => {
    if (!streamingTaskId) return;
    const metadata = loadRecoveryMetadata();
    if (!metadata || metadata.role !== "advisor" || metadata.currentTaskId !== streamingTaskId) {
      dispatch({ type: "RECOVERABLE_FAILURE", code: "session_recovery_required" });
      return;
    }
    let cursor = metadata.cursor;
    let refreshing = false;
    let pending = false;
    let closed = false;
    const events = new EventSource(`/api/demo/tasks/${streamingTaskId}/events?after=${cursor}`);
    const readConsistentAuthority = async (caseId: string, taskId: string) => {
      for (let attempt = 0; attempt < 3; attempt += 1) {
        const status = await api.journeyStatus(caseId);
        if (closed) return null;
        const ledger = await api.advisorLedger(caseId);
        if (
          status.case_id === caseId
          && ledger.case_id === caseId
          && ledger.case_revision === status.current_revision
          && ledger.phase === status.phase
          && ledger.task?.task_id === taskId
        ) {
          return { status, ledger };
        }
      }
      throw new Error("projection identity mismatch");
    };
    const runRefresh = async () => {
      if (refreshing || closed) { pending = true; return; }
      refreshing = true;
      try {
        do {
          pending = false;
          const current = loadRecoveryMetadata();
          if (!current || current.role !== "advisor" || current.currentTaskId !== streamingTaskId) throw new Error("projection identity mismatch");
          const authority = await readConsistentAuthority(current.caseId, streamingTaskId);
          if (!authority || closed) return;
          const { status, ledger } = authority;
          const next = metadataFor(current, status, "advisor", current.csrf, ledger);
          saveRecoveryMetadata({ ...next, cursor: Math.max(next.cursor, cursor) });
          dispatch({ type: "TASK_REFRESHED", status, ledger, taskId: streamingTaskId, after: cursor });
          if (!["active_task", "revision_task_active"].includes(status.phase)) {
            await loadAuthoritative(current.caseId, "advisor", current.csrf);
          }
        } while (pending && !closed);
      } catch (error) {
        if (!closed) dispatch({ type: "RECOVERABLE_FAILURE", code: failure(error) });
      } finally {
        refreshing = false;
      }
    };
    const refresh = (event: Event) => {
      const sequence = Number((event as MessageEvent).lastEventId);
      if (Number.isSafeInteger(sequence) && sequence >= 0) cursor = Math.max(cursor, sequence);
      void runRefresh();
    };
    for (const code of ["queued", "lease_acquired", "execution_started", "heartbeat_recorded", "retry_scheduled", "lease_reclaimed", "waiting_review", "succeeded", "blocked", "timed_out", "failed", "cancelled"]) events.addEventListener(code, refresh);
    return () => { closed = true; events.close(); };
  }, [loadAuthoritative, streamingTaskId]);

  const mutationRecord = useCallback(async (metadata: RecoveryMetadata, operation: MutationOperation, body: unknown) => {
    const record = await idempotencyFor(body, metadata.mutations[operation]);
    const updated = withMutation(metadata, operation, record);
    saveRecoveryMetadata(updated);
    return { record, updated };
  }, []);

  const handleMutationFailure = useCallback(async (
    error: unknown,
    operation: MutationOperation,
    preserveOnStale = false,
  ) => {
    const code = failure(error);
    if (code === "session_expired") {
      retryAction.current = null;
      clearRecoveryMetadata();
    } else if (code === "stale_conflict") {
      retryAction.current = null;
      const current = loadRecoveryMetadata();
      if (current && !preserveOnStale) {
        saveRecoveryMetadata(withMutation(current, operation, undefined));
      }
      await recover();
      return;
    }
    dispatch({ type: "RECOVERABLE_FAILURE", code });
  }, [recover]);

  const createTask = useCallback(async () => {
    if (!["advisor_ready", "replan_required"].includes(state.value) || !("ledger" in state) || !state.ledger.canonical_task_inputs) return;
    const metadata = loadRecoveryMetadata();
    if (!metadata || metadata.role !== "advisor") return;
    const inputs = state.ledger.canonical_task_inputs;
    const body = { schema_version: 1 as const, operation: inputs.operation, expected_case_revision: inputs.expected_case_revision, source_pack_id: inputs.source_pack_id, source_pack_version: inputs.source_pack_version, policy_version: inputs.policy_version };
    const attempt = async () => {
      try {
        const current = loadRecoveryMetadata() ?? metadata;
        const { record } = await mutationRecord(current, "create-task", body);
        const task = await api.createTask(current.caseId, body, current.csrf, record.idempotencyKey);
        const status = await api.journeyStatus(current.caseId);
        if (status.active_role !== "advisor") throw new Error("role projection mismatch");
        const ledger = await api.advisorLedger(current.caseId);
        if (ledger.task?.task_id !== task.task_id || ledger.phase !== status.phase) throw new Error("projection identity mismatch");
        saveRecoveryMetadata(metadataFor(loadRecoveryMetadata(), status, "advisor", current.csrf, ledger));
        retryAction.current = null;
        dispatch({ type: "STATUS_RELOADED", status, ledger });
        void refreshInspector(current.caseId);
      } catch (error) {
        await handleMutationFailure(error, "create-task");
      }
    };
    retryAction.current = attempt;
    dispatch({ type: "CREATE_TASK" });
    await attempt();
  }, [handleMutationFailure, mutationRecord, refreshInspector, state]);

  const review = useCallback(async (action: "approve_for_consultation" | "request_revision") => {
    if (state.value !== "advisor_review" || !state.ledger.review_inputs) return;
    if (action === "request_revision" && state.status.phase !== "review_required") return;
    const metadata = loadRecoveryMetadata();
    if (!metadata || metadata.role !== "advisor") return;
    const input = state.ledger.review_inputs;
    const body = action === "request_revision"
      ? { schema_version: 1 as const, planning_run_id: input.planning_run_id, expected_case_revision: input.expected_case_revision, action, eligible_route_ids: [] as [], risk_acceptances: [] as [], reviewer_notes: "Please revise the preferred-country scope for this synthetic journey." }
      : { schema_version: 1 as const, planning_run_id: input.planning_run_id, expected_case_revision: input.expected_case_revision, action, eligible_route_ids: input.eligible_route_ids, risk_acceptances: input.risk_acceptance_options };
    const operation: MutationOperation = action === "request_revision" ? "request-revision" : "new-review";
    const attempt = async () => {
      try {
        const current = loadRecoveryMetadata() ?? metadata;
        const { record } = await mutationRecord(current, operation, body);
        await api.review(current.caseId, body, current.csrf, record.idempotencyKey);
        const status = await api.journeyStatus(current.caseId);
        retryAction.current = null;
        if (status.active_role === "advisor") {
          await loadAuthoritative(current.caseId, "advisor", current.csrf);
        } else {
          dispatch({ type: "ROLE_SWITCH", caseId: current.caseId, targetRole: status.active_role });
        }
      } catch (error) {
        await handleMutationFailure(error, operation);
      }
    };
    retryAction.current = attempt;
    dispatch({ type: "REVIEW_SUBMIT" });
    await attempt();
  }, [handleMutationFailure, loadAuthoritative, mutationRecord, state]);

  const rotate = useCallback(async (caseId: string, target: "advisor" | "student" | "parent") => {
    const metadata = loadRecoveryMetadata();
    if (!metadata || metadata.caseId !== caseId || metadata.role === target) return;
    await transitionRole(metadata, target);
  }, [transitionRole]);

  const submitPreferredCountries = useCallback(async () => {
    if (state.value !== "revision_requested" || !revision) return;
    const metadata = loadRecoveryMetadata();
    if (!metadata || metadata.role !== "student") return;
    const messageBody = { schema_version: 1 as const, body: REVISION_PROPOSAL_MESSAGE };
    const proposalBody = { schema_version: 1 as const, case_revision: state.status.current_revision, proposal: { schema_version: 1 as const, fact_key: "student.preferred_countries", value: REVISED_PREFERRED_COUNTRIES } };
    const attempt = async () => {
      try {
        let current = loadRecoveryMetadata() ?? metadata;
        const messageMutation = await mutationRecord(current, "fact-proposal-message", messageBody);
        const message = await collaboration.appendMessage(revision.thread.thread_id, messageBody, current.csrf, messageMutation.record.idempotencyKey);
        current = loadRecoveryMetadata() ?? messageMutation.updated;
        const proposalMutation = await mutationRecord(current, "fact-proposal-candidate", proposalBody);
        await collaboration.proposeCandidate(message.message_event_id, proposalBody, current.csrf, proposalMutation.record.idempotencyKey);
        const status = await api.journeyStatus(current.caseId);
        if (status.phase !== "revision_fact_pending" || status.active_role !== "advisor") throw new Error("projection identity mismatch");
        retryAction.current = null;
        dispatch({ type: "ROLE_SWITCH", caseId: current.caseId, targetRole: "advisor" });
      } catch (error) {
        await handleMutationFailure(error, "fact-proposal-candidate", true);
      }
    };
    retryAction.current = attempt;
    await attempt();
  }, [handleMutationFailure, mutationRecord, revision, state]);

  const confirmPreferredCountries = useCallback(async () => {
    if (state.value !== "revision_fact_pending") return;
    const metadata = loadRecoveryMetadata();
    if (!metadata || metadata.role !== "advisor") return;
    const candidates = await collaboration.candidates(metadata.caseId, "advisor").catch(() => null);
    const candidate = candidates ? pendingPreferredCountriesCandidate(candidates) : null;
    if (!candidate || !("candidate_id" in candidate) || typeof candidate.candidate_id !== "string") {
      dispatch({ type: "RECOVERABLE_FAILURE", code: "transport_failure" });
      return;
    }
    const candidateId = candidate.candidate_id;
    const body = { schema_version: 1 as const, expected_case_revision: state.status.current_revision, decision: "confirm" as const, reason: "Confirmed the bounded synthetic preferred-country revision." };
    const attempt = async () => {
      try {
        const current = loadRecoveryMetadata() ?? metadata;
        const { record } = await mutationRecord(current, "fact-confirmation", body);
        await collaboration.verifyCandidate(candidateId, body, current.csrf, record.idempotencyKey);
        await loadAuthoritative(current.caseId, "advisor", current.csrf);
        retryAction.current = null;
      } catch (error) {
        await handleMutationFailure(error, "fact-confirmation");
      }
    };
    retryAction.current = attempt;
    dispatch({ type: "REVIEW_SUBMIT" });
    await attempt();
  }, [handleMutationFailure, loadAuthoritative, mutationRecord, state]);

  const decide = useCallback(async () => {
    if (state.value !== "family_review" || !confirmed) return;
    const metadata = loadRecoveryMetadata();
    if (!metadata || metadata.role !== "parent") return;
    const requirements = state.brief.decision_requirements;
    const body: FamilyDecisionBody = { schema_version: 1, expected_brief_version: state.brief.brief_version, selected_route_id: requirements.eligible_route_id, accepted_budget_min_minor: requirements.pinned_cost_minor, accepted_budget_max_minor: requirements.hard_ceiling_minor, currency: requirements.currency, accepted_trade_offs: requirements.required_trade_offs };
    const attempt = async () => {
      try {
        const current = loadRecoveryMetadata() ?? metadata;
        const { record } = await mutationRecord(current, "family-decision", body);
        await api.decide(state.brief.brief_id, body, current.csrf, record.idempotencyKey);
        await loadAuthoritative(current.caseId, "parent", current.csrf);
        retryAction.current = null;
      } catch (error) {
        setConfirmed(false);
        await handleMutationFailure(error, "family-decision");
      }
    };
    retryAction.current = attempt;
    dispatch({ type: "DECISION_SUBMIT" });
    await attempt();
  }, [confirmed, handleMutationFailure, loadAuthoritative, mutationRecord, state]);

  const retry = useCallback(async () => {
    if (retryAction.current) await retryAction.current();
    else await recover();
  }, [recover]);

  const endConflictingJourney = useCallback(async () => {
    const existing = loadDemoJourneyEnvelope();
    if (!existing || existing.journey !== "collaboration") {
      setJourneyConflict(null);
      return;
    }
    try {
      await api.revoke(existing.csrf);
    } catch (error) {
      if (!(error instanceof ConnectedDemoApiError) || error.status !== 401) {
        dispatch({ type: "RECOVERABLE_FAILURE", code: failure(error) });
        return;
      }
    }
    clearRecoveryMetadata();
    setJourneyConflict(null);
    await connectAdvisor();
  }, [connectAdvisor]);

  return {
    state,
    confirmed,
    setConfirmed,
    inspector,
    currentFacts,
    revision,
    journeyConflict,
    endConflictingJourney,
    connectAdvisor,
    recover,
    retry,
    createTask,
    createRevisionTask: createTask,
    approve: () => review("approve_for_consultation"),
    requestRevision: () => review("request_revision"),
    rotateToStudent: (caseId: string) => rotate(caseId, "student"),
    submitPreferredCountries,
    rotateToAdvisor: (caseId: string) => rotate(caseId, "advisor"),
    confirmPreferredCountries,
    approveRevision: () => review("approve_for_consultation"),
    rotateToParent: (caseId: string) => rotate(caseId, "parent"),
    decide,
  };
}
