"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import { CollaborationDemoApiError, createCollaborationDemoApi } from "../collaboration-demo/api";
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
} from "./contracts";
import { familyDraftFromIntent, familyIntentMatchesBrief, suggestFamilyDecisionDraft, validateFamilyDecisionDraft, type FamilyDecisionDraft, type SubmittedFamilyIntent } from "./family-decision";
import { idempotencyFor } from "./idempotency";
import { demoReducer, type DemoDisplayState, type RecoveryCode } from "./reducer";
import {
  pendingRevisionCandidate,
  revisionMessageBody,
  revisionProposalBody,
  validateRevisionIntent,
  validRevisionReason,
  type RevisionIntent,
  type RevisionFactKey,
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
  if ((error instanceof ConnectedDemoApiError || error instanceof CollaborationDemoApiError) && error.status === 401) return "session_expired";
  if ((error instanceof ConnectedDemoApiError || error instanceof CollaborationDemoApiError) && error.code === "bff_session_recovery_required") return "session_recovery_required";
  if ((error instanceof ConnectedDemoApiError || error instanceof CollaborationDemoApiError) && error.status === 409) return "stale_conflict";
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
    mutations: { ...current?.mutations },
    ...(current?.caseId === status.case_id && current.currentRevision === status.current_revision && current.retryIntent ? { retryIntent: current.retryIntent } : {}),
    ...(current?.caseId === status.case_id && current.currentRevision === status.current_revision && current.familyIntent ? { familyIntent: current.familyIntent } : {}),
    ...(current?.revisionIntent?.expectedCaseRevision === status.current_revision ? { revisionIntent: current.revisionIntent } : {}),
  };
}

function pendingRoleMetadata(
  current: RecoveryMetadata | null,
  status: ConnectedJourneyStatus,
  role: RecoveryMetadata["role"],
  csrf: string,
  targetRole = status.active_role,
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
    ...(retained?.revisionIntent?.expectedCaseRevision === status.current_revision ? { revisionIntent: retained.revisionIntent } : {}),
    pendingRole: targetRole,
  };
}

export function useConnectedDemo() {
  const [state, dispatch] = useReducer(demoReducer, initial);
  const [confirmed, setConfirmed] = useState(false);
  const [familyDraft, setFamilyDraftValue] = useState<FamilyDecisionDraft>({ minimumYuan: "", maximumYuan: "", acknowledgedTradeOffs: [] });
  const familyBriefIdentity = useRef<string | null>(null);
  const familyMutationBusy = useRef(false);
  const retryAction = useRef<null | (() => Promise<void>)>(null);
  const setFamilyDraft = useCallback((draft: FamilyDecisionDraft) => {
    setFamilyDraftValue(draft);
    setConfirmed(false);
    retryAction.current = null;
  }, []);
  const [inspector, setInspector] = useState<PlanningSkillInspector | null>(null);
  const [currentFacts, setCurrentFacts] = useState<CurrentFactsProjection | null>(null);
  const [revision, setRevision] = useState<RevisionCollaborationProjection | null>(null);
  const [journeyConflict, setJourneyConflict] = useState<"collaboration" | null>(() => {
    if (typeof window === "undefined") return null;
    return loadDemoJourneyEnvelope()?.journey === "collaboration" ? "collaboration" : null;
  });
  const [revisionIntent, setRevisionIntent] = useState<RevisionIntent | null>(() => typeof window === "undefined" ? null : loadRecoveryMetadata()?.revisionIntent ?? null);
  const [revisionSubmitting, setRevisionSubmitting] = useState(false);
  const revisionMutationBusy = useRef(false);
  const recoveryStarted = useRef(false);
  const terminalRetryBusy = useRef(false);
  const [retrySubmitting, setRetrySubmitting] = useState(false);
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
    role: "advisor" | "student" | "parent",
  ): Promise<RevisionCollaborationProjection> => {
    const detailReads = role === "advisor"
      ? Promise.all([
          collaboration.confirmedFacts(status.case_id, "advisor"),
          collaboration.candidates(status.case_id, "advisor"),
        ])
      : Promise.all([
          collaboration.confirmedFacts(status.case_id, role),
          collaboration.candidates(status.case_id, role),
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
    setRevisionIntent(current?.revisionIntent?.expectedCaseRevision === status.current_revision ? current.revisionIntent : null);
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
    if (role === "student" || (role === "parent" && status.phase === "revision_requested")) {
      if (status.phase !== "revision_requested") throw new Error("role projection mismatch");
      const projection = await loadRevisionProjection(status, role);
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
    const metadata = metadataFor(current, status, role, csrf);
    const identity = `${brief.brief_id}:${brief.brief_version}`;
    const intent = metadata.familyIntent;
    const matching = intent && familyIntentMatchesBrief(intent, brief);
    if (intent && !matching) {
      delete metadata.familyIntent;
      delete metadata.mutations["family-decision"];
    }
    if (familyBriefIdentity.current !== identity) {
      retryAction.current = null;
      if (familyBriefIdentity.current !== null) delete metadata.mutations["family-decision"];
      setFamilyDraftValue(matching ? familyDraftFromIntent(intent) : suggestFamilyDecisionDraft(brief));
      setConfirmed(false);
      familyBriefIdentity.current = identity;
    }
    saveRecoveryMetadata(metadata);
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
          if (status.case_id === current.caseId && status.phase === "revision_requested"
            && current.currentRevision !== status.current_revision) {
            retryAction.current = null;
            await loadAuthoritative(current.caseId, current.role, current.csrf);
            return;
          }
          const proposalRotation = status.phase === "revision_requested"
            && current.currentRevision === status.current_revision
            && ["student", "parent"].includes(target)
            && ["student", "parent"].includes(current.role);
          if (status.case_id !== current.caseId || (status.active_role !== target && !proposalRotation)) {
            throw new Error("role transition authority mismatch");
          }
          current = pendingRoleMetadata(current, status, current.role, current.csrf, target);
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

  const replayTerminalRetry = useCallback(async (metadata: RecoveryMetadata) => {
    const intent = metadata.retryIntent;
    const record = metadata.mutations["retry-task"];
    if (!intent || !record || metadata.role !== "advisor") throw new Error("retry consent unavailable");
    const task = await api.retryTask(intent.taskId, {
      schema_version: 1, expected_row_version: intent.expectedRowVersion,
      expected_case_revision: intent.expectedCaseRevision,
    }, metadata.csrf, record.idempotencyKey);
    if (task.task_id === intent.taskId) throw new Error("retry successor identity mismatch");
    await loadAuthoritative(metadata.caseId, "advisor", metadata.csrf);
    const loaded = loadRecoveryMetadata();
    if (loaded?.currentTaskId !== task.task_id) throw new Error("retry successor authority mismatch");
    delete loaded.retryIntent;
    saveRecoveryMetadata(loaded);
    retryAction.current = null;
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
      if (metadata.retryIntent) await replayTerminalRetry(metadata);
      else await loadAuthoritative(metadata.caseId, metadata.role, metadata.csrf);
    } catch (error) {
      const code = failure(error);
      if (code === "session_expired") clearRecoveryMetadata();
      if (code === "stale_conflict" && metadata.retryIntent) {
        delete metadata.retryIntent;
        delete metadata.mutations["retry-task"];
        saveRecoveryMetadata(metadata);
        await loadAuthoritative(metadata.caseId, metadata.role, metadata.csrf);
        return;
      }
      dispatch({ type: "RECOVERABLE_FAILURE", code });
    }
  }, [connectAdvisor, loadAuthoritative, replayTerminalRetry, transitionRole]);

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

  const retryTerminalTask = useCallback(async () => {
    if (terminalRetryBusy.current || state.value !== "terminal_task_failure" || !state.ledger.recovery?.retry_allowed || !state.ledger.canonical_task_inputs || !state.ledger.task) return;
    const metadata = loadRecoveryMetadata();
    if (!metadata || metadata.role !== "advisor" || metadata.caseId !== state.ledger.case_id || metadata.currentRevision !== state.ledger.case_revision) return;
    terminalRetryBusy.current = true;
    setRetrySubmitting(true);
    try {
      const intent = Object.freeze({ taskId: state.ledger.task.task_id, expectedRowVersion: state.ledger.task.row_version, expectedCaseRevision: state.ledger.case_revision });
      const record = await idempotencyFor(intent, metadata.retryIntent?.taskId === intent.taskId ? metadata.mutations["retry-task"] : undefined);
      const submitted = { ...withMutation(metadata, "retry-task", record), retryIntent: intent };
      saveRecoveryMetadata(submitted);
      const attempt = async () => {
        try { await replayTerminalRetry(loadRecoveryMetadata() ?? submitted); }
        catch (error) {
          if (failure(error) === "stale_conflict") {
            const current = loadRecoveryMetadata();
            if (current) { delete current.retryIntent; delete current.mutations["retry-task"]; saveRecoveryMetadata(current); }
          }
          await handleMutationFailure(error, "retry-task");
        }
      };
      retryAction.current = attempt;
      await attempt();
    } finally { terminalRetryBusy.current = false; setRetrySubmitting(false); }
  }, [handleMutationFailure, replayTerminalRetry, state]);

  const review = useCallback(async (action: "approve_for_consultation" | "request_revision") => {
    if (state.value !== "advisor_review" || !state.ledger.review_inputs) return;
    if (action === "request_revision" && state.status.phase !== "review_required") return;
    const metadata = loadRecoveryMetadata();
    if (!metadata || metadata.role !== "advisor") return;
    const input = state.ledger.review_inputs;
    const body = action === "request_revision"
      ? { schema_version: 1 as const, planning_run_id: input.planning_run_id, expected_case_revision: input.expected_case_revision, action, eligible_route_ids: [] as [], risk_acceptances: [] as [], reviewer_notes: "Please revise one supported planning fact for this synthetic journey." }
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

  const prepareRevisionFact = useCallback(async (factKey: RevisionFactKey) => {
    if (state.value !== "revision_requested" || revisionMutationBusy.current
      || !["student.preferred_countries", "family.budget"].includes(factKey)) return;
    const metadata = loadRecoveryMetadata();
    if (!metadata || !["student", "parent"].includes(metadata.role)
      || metadata.caseId !== state.status.case_id) return;
    if (metadata.currentRevision !== state.status.current_revision) { await recover(); return; }
    const targetRole = factKey === "family.budget" ? "parent" : "student";
    revisionMutationBusy.current = true;
    setRevisionSubmitting(true);
    try {
      // Preparation is explicit role consent, not a submitted fact or mutation key.
      if (metadata.role !== targetRole || metadata.pendingRole) {
        await transitionRole(metadata, targetRole);
      } else {
        const attempt = async () => {
          try { await loadAuthoritative(metadata.caseId, targetRole, metadata.csrf); }
          catch (error) { dispatch({ type: "RECOVERABLE_FAILURE", code: failure(error) }); }
        };
        retryAction.current = attempt;
        await attempt();
      }
    } finally {
      revisionMutationBusy.current = false;
      setRevisionSubmitting(false);
    }
  }, [loadAuthoritative, recover, state, transitionRole]);

  const submitRevision = useCallback(async (requested: RevisionIntent) => {
    if (state.value !== "revision_requested" || !revision || revisionMutationBusy.current) return;
    const metadata = loadRecoveryMetadata();
    if (!metadata || !["student", "parent"].includes(metadata.role) || metadata.caseId !== revision.caseId) return;
    const validated = validateRevisionIntent(requested, currentFacts);
    if (!validated.ok || requested.expectedCaseRevision !== state.status.current_revision) {
      if ((!validated.ok && validated.code === "stale") || requested.expectedCaseRevision !== state.status.current_revision) await recover();
      return;
    }
    const intent = validated.intent;
    const messageBody = revisionMessageBody(intent);
    const proposalBody = revisionProposalBody(intent);
    const attempt = async () => {
      if (revisionMutationBusy.current) return;
      revisionMutationBusy.current = true;
      setRevisionSubmitting(true);
      try {
        let current = loadRecoveryMetadata() ?? metadata;
        if (current.caseId !== revision.caseId || current.currentRevision !== intent.expectedCaseRevision) { await recover(); return; }
        const participantRole = intent.factKey === "family.budget" ? "parent" : "student";
        current = { ...current, revisionIntent: intent };
        saveRecoveryMetadata(current);
        setRevisionIntent(intent);
        // Bind both keys to the intention before any session rotation can fail.
        const preparedMessage = await mutationRecord(current, "fact-proposal-message", messageBody);
        const preparedProposal = await mutationRecord(preparedMessage.updated, "fact-proposal-candidate", proposalBody);
        current = preparedProposal.updated;
        if (current.role !== participantRole || current.pendingRole) {
          await transitionRole(current, participantRole);
          retryAction.current = attempt;
          const rotated = loadRecoveryMetadata();
          if (!rotated || rotated.role !== participantRole || rotated.pendingRole) return;
          current = rotated;
        }
        const authority = await api.journeyStatus(current.caseId);
        if (authority.current_revision !== intent.expectedCaseRevision) {
          throw new CollaborationDemoApiError(409, "stale_revision");
        }
        const facts = await collaboration.confirmedFacts(current.caseId, participantRole);
        const checked = validateRevisionIntent(intent, { caseId: current.caseId, caseRevision: authority.current_revision, facts: facts.current });
        if (!checked.ok || !["revision_requested", "revision_fact_pending"].includes(authority.phase)) {
          retryAction.current = null;
          await loadAuthoritative(current.caseId, participantRole, current.csrf);
          return;
        }
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
        if (failure(error) === "stale_conflict") {
          const current = loadRecoveryMetadata();
          if (current) {
            const updated = withMutation(withMutation(current, "fact-proposal-message", undefined), "fact-proposal-candidate", undefined);
            delete updated.revisionIntent;
            saveRecoveryMetadata(updated);
          }
          setRevisionIntent(null);
        }
        await handleMutationFailure(error, "fact-proposal-candidate");
      } finally {
        revisionMutationBusy.current = false;
        setRevisionSubmitting(false);
      }
    };
    retryAction.current = attempt;
    await attempt();
  }, [currentFacts, handleMutationFailure, loadAuthoritative, mutationRecord, recover, revision, state, transitionRole]);

  const confirmRevision = useCallback(async (reason: string) => {
    if (state.value !== "revision_fact_pending" || !revision || !validRevisionReason(reason) || revisionMutationBusy.current) return;
    const metadata = loadRecoveryMetadata();
    if (!metadata || metadata.role !== "advisor" || metadata.caseId !== revision.caseId) return;
    const displayed = pendingRevisionCandidate(revision.candidates.filter((candidate): candidate is MemoryCandidateAdvisor => "candidate_id" in candidate), state.status.current_revision);
    if (!displayed) return;
    const body = { schema_version: 1 as const, expected_case_revision: state.status.current_revision, decision: "confirm" as const, reason: reason.trim() };
    let submitted = false;
    const attempt = async () => {
      if (revisionMutationBusy.current) return;
      revisionMutationBusy.current = true;
      try {
        const current = loadRecoveryMetadata() ?? metadata;
        const candidates = await collaboration.candidates(current.caseId, "advisor");
        const replay = submitted ? candidates.find((candidate) => candidate.candidate_id === displayed.candidate_id && candidate.state === "confirmed" && candidate.case_revision === body.expected_case_revision) : null;
        const candidate = replay ?? pendingRevisionCandidate(candidates, body.expected_case_revision);
        if (!candidate || candidate.candidate_id !== displayed.candidate_id || JSON.stringify(candidate.value) !== JSON.stringify(displayed.value)) {
          retryAction.current = null;
          await loadAuthoritative(current.caseId, "advisor", current.csrf);
          return;
        }
        const { record } = await mutationRecord(current, "fact-confirmation", { candidateId: displayed.candidate_id, body });
        submitted = true;
        await collaboration.verifyCandidate(displayed.candidate_id, body, current.csrf, record.idempotencyKey);
        await loadAuthoritative(current.caseId, "advisor", current.csrf);
        retryAction.current = null;
      } catch (error) {
        await handleMutationFailure(error, "fact-confirmation");
      } finally {
        revisionMutationBusy.current = false;
      }
    };
    retryAction.current = attempt;
    dispatch({ type: "REVIEW_SUBMIT" });
    await attempt();
  }, [handleMutationFailure, loadAuthoritative, mutationRecord, revision, state]);

  const decide = useCallback(async () => {
    if (state.value !== "family_review" || !confirmed || familyMutationBusy.current) return;
    const metadata = loadRecoveryMetadata();
    if (!metadata || metadata.role !== "parent" || metadata.pendingRole || metadata.caseId !== state.brief.case_id) return;
    const validated = validateFamilyDecisionDraft(familyDraft, state.brief);
    if (!validated.ok) return;
    const intent: SubmittedFamilyIntent = { schema_version: 1, briefId: state.brief.brief_id, body: validated.body };
    const attempt = async () => {
      if (familyMutationBusy.current) return;
      familyMutationBusy.current = true;
      try {
        const current = loadRecoveryMetadata();
        if (!current || current.role !== "parent" || current.pendingRole || current.caseId !== metadata.caseId || current.currentRevision !== metadata.currentRevision) return;
        const record = await idempotencyFor(intent.body, current.mutations["family-decision"]);
        saveRecoveryMetadata({ ...withMutation(current, "family-decision", record), familyIntent: intent });
        await api.decide(intent.briefId, intent.body, current.csrf, record.idempotencyKey);
        await loadAuthoritative(current.caseId, "parent", current.csrf);
        retryAction.current = null;
      } catch (error) {
        setConfirmed(false);
        if (failure(error) === "stale_conflict") {
          const current = loadRecoveryMetadata();
          if (current) {
            delete current.familyIntent;
            saveRecoveryMetadata(withMutation(current, "family-decision", undefined));
          }
          familyBriefIdentity.current = null;
        }
        await handleMutationFailure(error, "family-decision");
      } finally {
        familyMutationBusy.current = false;
      }
    };
    retryAction.current = attempt;
    dispatch({ type: "DECISION_SUBMIT" });
    await attempt();
  }, [confirmed, familyDraft, handleMutationFailure, loadAuthoritative, state]);

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
    familyDraft,
    setFamilyDraft,
    inspector,
    currentFacts,
    revision,
    journeyConflict,
    endConflictingJourney,
    connectAdvisor,
    recover,
    retry,
    createTask,
    retryTerminalTask,
    retrySubmitting,
    createRevisionTask: createTask,
    approve: () => review("approve_for_consultation"),
    requestRevision: () => review("request_revision"),
    rotateToStudent: (caseId: string) => rotate(caseId, "student"),
    submitRevision,
    prepareRevisionFact,
    revisionIntent,
    revisionSubmitting,
    rotateToAdvisor: (caseId: string) => rotate(caseId, "advisor"),
    confirmRevision,
    approveRevision: () => review("approve_for_consultation"),
    rotateToParent: (caseId: string) => rotate(caseId, "parent"),
    decide,
  };
}
