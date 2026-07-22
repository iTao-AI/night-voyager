"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import type { PlanningSkillInspector } from "../skill-inspector/contracts";

import { ConnectedDemoApiError, createConnectedDemoApi } from "../connected-demo/api";
import { idempotencyFor } from "../connected-demo/idempotency";
import {
  clearDemoJourneyEnvelope,
  continueCollaborationAsAdvisorFamily,
  loadDemoJourneyEnvelope,
  saveCollaborationJourney,
  saveRecoveryMetadata,
  withCollaborationMutation,
  type CollaborationJourneyEnvelopeV2,
  type CollaborationMutationKind,
  type CollaborationPersistedPhase,
} from "../connected-demo/session-storage";
import { CollaborationDemoApiError, createCollaborationDemoApi, type VerificationBody } from "./api";
import type { ConfirmedFactAdvisor, MemoryCandidateAdvisor, MemoryCandidateParticipant } from "./contracts";
import { classifyCollaborationProblem, collaborationReducer, initialCollaborationState, type CollaborationContext, type CollaborationErrorCategory } from "./reducer";

export const COLLABORATION_CASE_ID = "41000000-0000-0000-0000-000000000001";
const MESSAGE_BODY = "Our confirmed program budget is 300,000 to 400,000 CNY.";
const BUDGET = { schema_version: 1 as const, currency: "CNY" as const, period: "program_total" as const, preferred_minor: 30_000_000, hard_ceiling_minor: 40_000_000, elasticity_bps: 1000, refused: false };
const VERIFICATION_REASON = "The family confirmed this bounded program budget.";
const MESSAGE_REQUEST = { schema_version: 1 as const, body: MESSAGE_BODY };
const PROPOSAL_REQUEST = { schema_version: 1 as const, case_revision: 1, proposal: { schema_version: 1 as const, fact_key: "family.budget", value: BUDGET } };
const identity = createConnectedDemoApi();
const api = createCollaborationDemoApi();

export const collaborationNavigation = {
  toPlanning(): void {
    window.location.assign("/demo");
  },
};

class HandoffValidationError extends Error {
  constructor(readonly category: CollaborationErrorCategory) {
    super("handoff authority validation failed");
  }
}

function advisorCandidate(value: unknown): value is MemoryCandidateAdvisor { return typeof value === "object" && value !== null && "candidate_id" in value; }
function advisorFact(value: unknown): value is ConfirmedFactAdvisor { return typeof value === "object" && value !== null && "confirmed_fact_id" in value; }
function findAdvisorFact(items: readonly unknown[], candidateId: string | null): ConfirmedFactAdvisor | null {
  for (const item of items) if (advisorFact(item) && item.candidate_id === candidateId) return item;
  return null;
}
function category(error: unknown): CollaborationErrorCategory {
  if (error instanceof CollaborationDemoApiError) {
    if (error.status === 401) return "session_recovery_required";
    return classifyCollaborationProblem(error.code);
  }
  if (error instanceof ConnectedDemoApiError) {
    if (error.status === 401) return "session_recovery_required";
    return classifyCollaborationProblem(error.code);
  }
  return "transport_unavailable_or_timeout";
}
function conflict(error: unknown): boolean { return error instanceof CollaborationDemoApiError && error.status === 409; }
function verificationBody(caseRevision: number): VerificationBody {
  return { schema_version: 1, expected_case_revision: caseRevision, decision: "confirm", reason: VERIFICATION_REASON };
}
function participantBudget(items: readonly MemoryCandidateParticipant[]): MemoryCandidateParticipant | null {
  return items.find((item) => item.fact_key === "family.budget") ?? null;
}
function matchingMessage(messages: CollaborationContext["messages"], messageId: string | null) {
  return messages.find((item) => item.message_event_id === messageId || (messageId === null && item.actor_role === "parent" && item.body === MESSAGE_BODY)) ?? null;
}

function handoffFailure(error: unknown): CollaborationErrorCategory {
  return error instanceof HandoffValidationError ? error.category : category(error);
}

function requireHandoff(value: unknown, category: CollaborationErrorCategory = "stale"): asserts value {
  if (!value) throw new HandoffValidationError(category);
}

function envelope(context: CollaborationContext, csrf: string, phase: CollaborationPersistedPhase, mutations: CollaborationJourneyEnvelopeV2["mutations"], ids?: { messageId?: string | null; candidateId?: string | null }): CollaborationJourneyEnvelopeV2 {
  return {
    schema_version: 2,
    journey: "collaboration",
    role: context.role,
    csrf,
    caseId: context.caseId,
    threadId: context.thread?.thread_id ?? null,
    messageId: ids?.messageId ?? context.messages.at(-1)?.message_event_id ?? null,
    candidateId: context.role === "advisor" ? (ids?.candidateId ?? (advisorCandidate(context.candidate) ? context.candidate.candidate_id : null)) : null,
    phase,
    mutations,
  };
}

export function useCollaborationDemo() {
  const [state, dispatch] = useReducer(collaborationReducer, COLLABORATION_CASE_ID, initialCollaborationState);
  const [journeyConflict, setJourneyConflict] = useState<"advisor-family" | null>(() => {
    if (typeof window === "undefined") return null;
    return loadDemoJourneyEnvelope()?.journey === "advisor-family" ? "advisor-family" : null;
  });
  const [inspector, setInspector] = useState<PlanningSkillInspector | null>(null);
  const recoveryStarted = useRef(false);
  const retryAction = useRef<null | (() => Promise<void>)>(null);
  const recoverRef = useRef<(conflictError?: CollaborationDemoApiError) => Promise<void>>(async () => undefined);
  const handoffInFlight = useRef(false);

  const fail = useCallback((error: unknown) => {
    const mapped = category(error);
    if ((error instanceof CollaborationDemoApiError || error instanceof ConnectedDemoApiError) && error.status === 401) {
      retryAction.current = null;
      clearDemoJourneyEnvelope();
    }
    dispatch({ type: "FAILURE", category: mapped });
  }, []);

  const connectParent = useCallback(async () => {
    const existing = loadDemoJourneyEnvelope();
    if (existing?.journey === "advisor-family") { setJourneyConflict("advisor-family"); return; }
    try {
      setInspector(null);
      const bootstrap = await identity.bootstrap();
      const session = await identity.mint("parent", bootstrap.csrf_token);
      saveCollaborationJourney({
        schema_version: 2,
        journey: "collaboration",
        role: "parent",
        csrf: session.csrf_token,
        caseId: COLLABORATION_CASE_ID,
        threadId: null,
        messageId: null,
        candidateId: null,
        phase: "bootstrapping_parent",
        mutations: {},
      });
      const thread = await api.thread(COLLABORATION_CASE_ID);
      const messages = await api.messages(thread.thread_id);
      const context: CollaborationContext = { role: "parent", caseId: COLLABORATION_CASE_ID, thread, messages: messages.items, candidate: null, fact: null, caseRevision: 1 };
      saveCollaborationJourney(envelope(context, session.csrf_token, "thread_ready", {}));
      dispatch({ type: "PARENT_RELOADED", context });
    } catch (error) { fail(error); }
  }, [fail]);

  const recover = useCallback(async (conflictError?: CollaborationDemoApiError) => {
    const stored = loadDemoJourneyEnvelope();
    if (!stored) {
      const reset = initialCollaborationState(COLLABORATION_CASE_ID);
      setInspector(null);
      dispatch({ type: "HYDRATE", phase: "bootstrapping_parent", context: reset.context });
      await connectParent();
      return;
    }
    if (stored.journey === "advisor-family") { setJourneyConflict("advisor-family"); return; }
    try {
      if (stored.phase === "bootstrapping_parent") {
        const thread = await api.thread(stored.caseId);
        const messages = await api.messages(thread.thread_id);
        const context: CollaborationContext = { role: "parent", caseId: stored.caseId, thread, messages: messages.items, candidate: null, fact: null, caseRevision: 1 };
        saveCollaborationJourney(envelope(context, stored.csrf, "thread_ready", {}));
        retryAction.current = null;
        dispatch({ type: "PARENT_RELOADED", context });
        return;
      }
      const thread = await api.thread(stored.caseId);
      if (thread.thread_id !== stored.threadId) throw new Error("projection identity mismatch");
      const messages = await api.messages(thread.thread_id);
      const baseContext: CollaborationContext = { role: stored.role, caseId: stored.caseId, thread, messages: messages.items, candidate: null, fact: null, caseRevision: 1 };

      if (stored.phase === "switching_to_advisor") {
        try {
          const participants = await api.candidates(stored.caseId, "parent");
          const candidate = participantBudget(participants);
          if (!candidate || !matchingMessage(messages.items, stored.messageId)) throw new Error("projection identity mismatch");
          const context = { ...baseContext, role: "parent" as const, candidate };
          const stable = withCollaborationMutation({ ...stored, role: "parent", phase: "proposal_pending" }, "propose-memory-candidate", undefined);
          saveCollaborationJourney(stable);
          retryAction.current = null;
          dispatch({ type: "HYDRATE", phase: "proposal_pending", context });
          return;
        } catch (parentError) {
          try {
            const advisors = await api.candidates(stored.caseId, "advisor");
            const candidate = advisors.find((item) => item.message_event_id === stored.messageId) ?? null;
            if (!candidate) throw new Error("projection identity mismatch");
            if (stored.role !== "advisor") {
              retryAction.current = null;
              clearDemoJourneyEnvelope();
              dispatch({ type: "HYDRATE", phase: "switching_to_advisor", context: baseContext });
              dispatch({ type: "FAILURE", category: "session_recovery_required" });
              return;
            }
            const ledger = await identity.advisorLedger(stored.caseId);
            if (ledger.case_revision !== candidate.case_revision) throw new Error("candidate revision mismatch");
            const context: CollaborationContext = { ...baseContext, role: "advisor", candidate, caseRevision: ledger.case_revision };
            setInspector(await api.planningSkillInspector(stored.caseId).catch(() => null));
            saveCollaborationJourney(envelope(context, stored.csrf, "advisor_reviewing", {}, { messageId: stored.messageId, candidateId: candidate.candidate_id }));
            retryAction.current = null;
            dispatch({ type: "HYDRATE", phase: "advisor_reviewing", context });
            return;
          } catch {
            throw parentError;
          }
        }
      }

      if (stored.role === "parent") {
        const projectedMessage = matchingMessage(messages.items, stored.messageId);
        const participants = projectedMessage ? await api.candidates(stored.caseId, "parent") : [];
        const candidate = participantBudget(participants);
        const context: CollaborationContext = { ...baseContext, role: "parent", candidate };

        if (stored.phase === "message_submitting") {
          if (projectedMessage) {
            const stable = withCollaborationMutation({ ...stored, messageId: projectedMessage.message_event_id, phase: "thread_ready" }, "append-message", undefined);
            saveCollaborationJourney(stable);
            retryAction.current = null;
            dispatch({ type: "HYDRATE", phase: "thread_ready", context });
            return;
          }
          const record = stored.mutations["append-message"];
          if (!record) throw new Error("missing mutation recovery record");
          await idempotencyFor(MESSAGE_REQUEST, record);
          if (conflictError) {
            const stable = withCollaborationMutation({ ...stored, phase: "thread_ready" }, "append-message", undefined);
            saveCollaborationJourney(stable);
            retryAction.current = null;
            dispatch({ type: "HYDRATE", phase: "thread_ready", context });
            fail(conflictError);
            return;
          }
          retryAction.current = async () => {
            try {
              const current = loadDemoJourneyEnvelope();
              if (!current || current.journey !== "collaboration") throw new Error("session recovery required");
              const exact = current.mutations["append-message"];
              if (!exact) throw new Error("missing mutation recovery record");
              await idempotencyFor(MESSAGE_REQUEST, exact);
              await api.appendMessage(current.threadId!, MESSAGE_REQUEST, current.csrf, exact.idempotencyKey);
              await recoverRef.current();
            } catch (error) { if (conflict(error)) await recoverRef.current(error as CollaborationDemoApiError); else fail(error); }
          };
          dispatch({ type: "HYDRATE", phase: "message_submitting", context });
          dispatch({ type: "FAILURE", category: "transport_unavailable_or_timeout" });
          return;
        }

        const proposalRecord = stored.mutations["propose-memory-candidate"];
        if (stored.phase === "thread_ready" && proposalRecord) {
          await idempotencyFor(PROPOSAL_REQUEST, proposalRecord);
          if (candidate) {
            const stable = withCollaborationMutation({ ...stored, phase: "proposal_pending" }, "propose-memory-candidate", undefined);
            saveCollaborationJourney(stable);
            retryAction.current = null;
            dispatch({ type: "HYDRATE", phase: "proposal_pending", context });
            return;
          }
          if (conflictError) {
            const stable = withCollaborationMutation(stored, "propose-memory-candidate", undefined);
            saveCollaborationJourney(stable);
            retryAction.current = null;
            dispatch({ type: "HYDRATE", phase: "thread_ready", context });
            fail(conflictError);
            return;
          }
          retryAction.current = async () => {
            try {
              const current = loadDemoJourneyEnvelope();
              if (!current || current.journey !== "collaboration" || !current.messageId) throw new Error("session recovery required");
              const exact = current.mutations["propose-memory-candidate"];
              if (!exact) throw new Error("missing mutation recovery record");
              await idempotencyFor(PROPOSAL_REQUEST, exact);
              await api.proposeCandidate(current.messageId, PROPOSAL_REQUEST, current.csrf, exact.idempotencyKey);
              await recoverRef.current();
            } catch (error) { if (conflict(error)) await recoverRef.current(error as CollaborationDemoApiError); else fail(error); }
          };
          dispatch({ type: "HYDRATE", phase: "thread_ready", context });
          dispatch({ type: "FAILURE", category: "transport_unavailable_or_timeout" });
          return;
        }
        if (stored.phase === "proposal_pending" && !candidate) throw new Error("projection identity mismatch");
        dispatch({ type: "HYDRATE", phase: stored.phase, context });
        return;
      }

      const candidates = await api.candidates(stored.caseId, "advisor");
      const candidate = candidates.find((item) => item.candidate_id === stored.candidateId) ?? null;
      if (!candidate || candidate.message_event_id !== stored.messageId) throw new Error("projection identity mismatch");
      if (stored.phase === "confirmation_submitting" || stored.phase === "replan_required") {
        const facts = await api.confirmedFacts(stored.caseId, "advisor");
        const fact = findAdvisorFact(facts.current, stored.candidateId);
        const ledger = await identity.advisorLedger(stored.caseId);
        const context: CollaborationContext = { ...baseContext, role: "advisor", candidate, fact, caseRevision: ledger.case_revision };
        if (candidate.state === "confirmed" && fact && ledger.case_revision > candidate.case_revision) {
          const stable = withCollaborationMutation({ ...stored, phase: "replan_required" }, "verify-memory-candidate", undefined);
          saveCollaborationJourney(stable);
          retryAction.current = null;
          setInspector(await api.planningSkillInspector(stored.caseId).catch(() => null));
          dispatch({ type: "HYDRATE", phase: "replan_required", context });
          return;
        }
        if (stored.phase === "replan_required") throw new Error("authority proof mismatch");
        const body = verificationBody(candidate.case_revision);
        const record = stored.mutations["verify-memory-candidate"];
        if (!record || candidate.state !== "pending" || ledger.case_revision !== candidate.case_revision) {
          const stable = withCollaborationMutation({ ...stored, phase: "advisor_reviewing" }, "verify-memory-candidate", undefined);
          saveCollaborationJourney(stable);
          retryAction.current = null;
          dispatch({ type: "HYDRATE", phase: "advisor_reviewing", context });
          dispatch({ type: "FAILURE", category: conflictError ? category(conflictError) : (candidate.state === "pending" ? "stale" : "expired_or_terminal") });
          return;
        }
        await idempotencyFor(body, record);
        if (conflictError) {
          const stable = withCollaborationMutation({ ...stored, phase: "advisor_reviewing" }, "verify-memory-candidate", undefined);
          saveCollaborationJourney(stable);
          retryAction.current = null;
          dispatch({ type: "HYDRATE", phase: "advisor_reviewing", context });
          fail(conflictError);
          return;
        }
        retryAction.current = async () => {
          try {
            const current = loadDemoJourneyEnvelope();
            if (!current || current.journey !== "collaboration" || !current.candidateId) throw new Error("session recovery required");
            const exact = current.mutations["verify-memory-candidate"];
            if (!exact) throw new Error("missing mutation recovery record");
            await idempotencyFor(body, exact);
            await api.verifyCandidate(current.candidateId, body, current.csrf, exact.idempotencyKey);
            await recoverRef.current();
          } catch (error) { if (conflict(error)) await recoverRef.current(error as CollaborationDemoApiError); else fail(error); }
        };
        dispatch({ type: "HYDRATE", phase: "confirmation_submitting", context });
        dispatch({ type: "FAILURE", category: "transport_unavailable_or_timeout" });
        return;
      }

      const ledger = await identity.advisorLedger(stored.caseId);
      const context: CollaborationContext = { ...baseContext, role: "advisor", candidate, caseRevision: ledger.case_revision };
      setInspector(await api.planningSkillInspector(stored.caseId).catch(() => null));
      dispatch({ type: "HYDRATE", phase: "advisor_reviewing", context });
    } catch (error) { fail(error); }
  }, [connectParent, fail]);

  useEffect(() => {
    recoverRef.current = recover;
  }, [recover]);

  useEffect(() => {
    if (recoveryStarted.current) return;
    recoveryStarted.current = true;
    const stored = loadDemoJourneyEnvelope();
    if (stored?.journey === "collaboration") queueMicrotask(() => { void recover(); });
  }, [recover]);

  const persistMutation = useCallback(async (stored: CollaborationJourneyEnvelopeV2, operation: CollaborationMutationKind, body: unknown, phase: CollaborationPersistedPhase) => {
    const record = await idempotencyFor(body, stored.mutations[operation]);
    const updated = withCollaborationMutation({ ...stored, phase }, operation, record);
    saveCollaborationJourney(updated);
    return { record, updated };
  }, []);

  const refreshHandoffInspector = useCallback(async (request: Promise<PlanningSkillInspector>) => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      const unavailable = new Promise<null>((resolve) => {
        timer = setTimeout(() => resolve(null), 1_000);
      });
      setInspector(await Promise.race([request, unavailable]));
    } catch {
      setInspector(null);
    } finally {
      if (timer) clearTimeout(timer);
    }
  }, []);

  const appendMessage = useCallback(async () => {
    if (state.value !== "thread_ready" || !state.context.thread) return;
    const stored = loadDemoJourneyEnvelope();
    if (!stored || stored.journey !== "collaboration" || stored.role !== "parent") return;
    const body = MESSAGE_REQUEST;
    const attempt = async () => {
      try {
        const current = loadDemoJourneyEnvelope();
        if (!current || current.journey !== "collaboration") throw new Error("session recovery required");
        const { record, updated } = await persistMutation(current, "append-message", body, "message_submitting");
        const message = await api.appendMessage(current.threadId!, body, current.csrf, record.idempotencyKey);
        const messages = await api.messages(current.threadId!);
        const context = { ...state.context, messages: messages.items };
        saveCollaborationJourney({ ...updated, phase: "thread_ready", messageId: message.message_event_id });
        retryAction.current = null;
        dispatch({ type: "PARENT_RELOADED", context });
      } catch (error) { if (conflict(error)) await recover(error as CollaborationDemoApiError); else fail(error); }
    };
    retryAction.current = attempt;
    dispatch({ type: "MESSAGE_SUBMIT" });
    await attempt();
  }, [fail, persistMutation, recover, state]);

  const proposeBudget = useCallback(async () => {
    if (state.value !== "thread_ready") return;
    const stored = loadDemoJourneyEnvelope();
    if (!stored || stored.journey !== "collaboration" || stored.role !== "parent" || !stored.messageId) return;
    const body = PROPOSAL_REQUEST;
    const attempt = async () => {
      try {
        const current = loadDemoJourneyEnvelope();
        if (!current || current.journey !== "collaboration") throw new Error("session recovery required");
        const { record, updated } = await persistMutation(current, "propose-memory-candidate", body, "thread_ready");
        await api.proposeCandidate(current.messageId!, body, current.csrf, record.idempotencyKey);
        const candidate = participantBudget(await api.candidates(current.caseId, "parent"));
        if (!candidate) throw new Error("authority projection missing");
        const context = { ...state.context, candidate };
        saveCollaborationJourney({ ...updated, phase: "proposal_pending", candidateId: null });
        retryAction.current = null;
        dispatch({ type: "PROPOSAL_RELOADED", context });
      } catch (error) { if (conflict(error)) await recover(error as CollaborationDemoApiError); else fail(error); }
    };
    retryAction.current = attempt;
    await attempt();
  }, [fail, persistMutation, recover, state]);

  const switchToAdvisor = useCallback(async () => {
    if (state.value !== "proposal_pending") return;
    const stored = loadDemoJourneyEnvelope();
    if (!stored || stored.journey !== "collaboration" || stored.role !== "parent") return;
    saveCollaborationJourney({ ...stored, phase: "switching_to_advisor" });
    dispatch({ type: "ROLE_SWITCH" });
    setInspector(null);
    try {
      await identity.revoke(stored.csrf);
      const bootstrap = await identity.bootstrap();
      const advisor = await identity.mint("advisor", bootstrap.csrf_token);
      saveCollaborationJourney({ ...stored, role: "advisor", csrf: advisor.csrf_token, candidateId: null, phase: "switching_to_advisor" });
      const thread = await api.thread(stored.caseId);
      const messages = await api.messages(thread.thread_id);
      const candidates = await api.candidates(stored.caseId, "advisor");
      const candidate = candidates.find((item) => item.message_event_id === stored.messageId) ?? null;
      if (!candidate) throw new Error("candidate projection missing");
      const ledger = await identity.advisorLedger(stored.caseId);
      if (ledger.case_revision !== candidate.case_revision) throw new Error("candidate revision mismatch");
      const context: CollaborationContext = { role: "advisor", caseId: stored.caseId, thread, messages: messages.items, candidate, fact: null, caseRevision: ledger.case_revision };
      setInspector(await api.planningSkillInspector(stored.caseId).catch(() => null));
      saveCollaborationJourney(envelope(context, advisor.csrf_token, "advisor_reviewing", {}, { messageId: stored.messageId, candidateId: candidate.candidate_id }));
      dispatch({ type: "ADVISOR_RELOADED", context });
    } catch (error) { fail(error); }
  }, [fail, state]);

  const confirmCandidate = useCallback(async () => {
    if (state.value !== "advisor_reviewing" || !advisorCandidate(state.context.candidate)) return;
    const stored = loadDemoJourneyEnvelope();
    if (!stored || stored.journey !== "collaboration" || stored.role !== "advisor" || !stored.candidateId) return;
    const projected = state.context.candidate;
    const ledger = await identity.advisorLedger(stored.caseId).catch((error) => { fail(error); return null; });
    if (!ledger || ledger.case_revision !== projected.case_revision) { if (ledger) dispatch({ type: "FAILURE", category: "stale" }); return; }
    const body = verificationBody(projected.case_revision);
    const prove = async (result?: { result_fact_id: string | null; result_revision: number | null }) => {
      const candidates = await api.candidates(stored.caseId, "advisor");
      const candidate = candidates.find((item) => item.candidate_id === stored.candidateId) ?? null;
      const facts = await api.confirmedFacts(stored.caseId, "advisor");
      const fact = findAdvisorFact(facts.current, stored.candidateId);
      const refreshed = await identity.advisorLedger(stored.caseId);
      if (!candidate || candidate.state !== "confirmed" || !fact || refreshed.case_revision <= candidate.case_revision) throw new Error("authority proof mismatch");
      if (result && (fact.confirmed_fact_id !== result.result_fact_id || refreshed.case_revision !== result.result_revision)) throw new Error("authority proof mismatch");
      setInspector(await api.planningSkillInspector(stored.caseId).catch(() => null));
      const context = { ...state.context, candidate, fact, caseRevision: refreshed.case_revision };
      const current = loadDemoJourneyEnvelope();
      if (!current || current.journey !== "collaboration") throw new Error("session recovery required");
      saveCollaborationJourney(withCollaborationMutation({ ...current, phase: "replan_required" }, "verify-memory-candidate", undefined));
      retryAction.current = null;
      dispatch({ type: "CONFIRMED_RELOADED", context });
    };
    const attempt = async () => {
      try {
        const current = loadDemoJourneyEnvelope();
        if (!current || current.journey !== "collaboration") throw new Error("session recovery required");
        const { record } = await persistMutation(current, "verify-memory-candidate", body, "confirmation_submitting");
        const result = await api.verifyCandidate(current.candidateId!, body, current.csrf, record.idempotencyKey);
        await prove(result);
      } catch (error) {
        if (conflict(error)) {
          await recover(error as CollaborationDemoApiError);
          return;
        }
        fail(error);
      }
    };
    retryAction.current = attempt;
    dispatch({ type: "CONFIRM_SUBMIT" });
    await attempt();
  }, [fail, persistMutation, recover, state]);

  const continueToPlanning = useCallback(async () => {
    if (state.value !== "replan_required" || handoffInFlight.current) return;
    const expectedContext = state.context;
    const attempt = async () => {
      if (handoffInFlight.current) return;
      handoffInFlight.current = true;
      dispatch({ type: "HANDOFF_VALIDATE" });
      try {
        const stored = loadDemoJourneyEnvelope();
        requireHandoff(
          stored?.journey === "collaboration"
          && stored.role === "advisor"
          && stored.phase === "replan_required"
          && stored.caseId === expectedContext.caseId
          && stored.candidateId !== null,
          "session_recovery_required",
        );

        const candidates = await api.candidates(stored.caseId, "advisor");
        const candidate = candidates.find((item) => item.candidate_id === stored.candidateId) ?? null;
        requireHandoff(candidate, "stale");
        requireHandoff(candidate.state === "confirmed", candidate.state === "stale" ? "stale" : "expired_or_terminal");
        requireHandoff(candidate.message_event_id === stored.messageId, "stale");

        const facts = await api.confirmedFacts(stored.caseId, "advisor");
        const fact = findAdvisorFact(facts.current, stored.candidateId);
        requireHandoff(fact, "stale");
        requireHandoff(fact.source_message_event_id === stored.messageId, "stale");
        requireHandoff(
          advisorFact(expectedContext.fact)
          && expectedContext.fact.confirmed_fact_id === fact.confirmed_fact_id,
          "stale",
        );

        const ledger = await identity.advisorLedger(stored.caseId);
        requireHandoff(ledger.case_id === stored.caseId, "stale");
        requireHandoff(ledger.case_revision === expectedContext.caseRevision, "stale");
        requireHandoff(ledger.case_revision === candidate.case_revision + 1, "stale");
        if (ledger.canonical_task_inputs) {
          requireHandoff(ledger.canonical_task_inputs.case_id === stored.caseId, "stale");
          requireHandoff(ledger.canonical_task_inputs.expected_case_revision === ledger.case_revision, "stale");
        }

        let taskId: string | null;
        if (["active-task", "review-required", "terminal-task-failure"].includes(ledger.phase)) {
          requireHandoff(ledger.task?.task_id, "stale");
          taskId = ledger.task.task_id;
        } else if (["task-ready", "family-review", "plan-ready"].includes(ledger.phase)) {
          taskId = null;
        } else {
          throw new HandoffValidationError("stale");
        }

        await refreshHandoffInspector(api.planningSkillInspector(stored.caseId));
        const converted = continueCollaborationAsAdvisorFamily(stored, taskId);
        saveRecoveryMetadata(converted);
        retryAction.current = null;
        collaborationNavigation.toPlanning();
      } catch (error) {
        const mapped = handoffFailure(error);
        if (mapped === "stale" || mapped === "session_recovery_required") retryAction.current = null;
        if (
          mapped === "session_recovery_required"
          && (error instanceof CollaborationDemoApiError || error instanceof ConnectedDemoApiError)
          && error.status === 401
        ) fail(error);
        else dispatch({ type: "FAILURE", category: mapped });
      } finally {
        handoffInFlight.current = false;
      }
    };
    retryAction.current = attempt;
    await attempt();
  }, [fail, refreshHandoffInspector, state]);

  const retry = useCallback(async () => { if (retryAction.current) await retryAction.current(); else await recover(); }, [recover]);

  const endConflictingJourney = useCallback(async () => {
    const stored = loadDemoJourneyEnvelope();
    if (!stored || stored.journey !== "advisor-family") { setJourneyConflict(null); return; }
    try {
      await identity.revoke(stored.csrf);
      clearDemoJourneyEnvelope();
      setJourneyConflict(null);
      await connectParent();
    } catch (error) {
      if (error instanceof ConnectedDemoApiError && error.status === 401) {
        clearDemoJourneyEnvelope(); setJourneyConflict(null); await connectParent();
      } else fail(error);
    }
  }, [connectParent, fail]);

  return { state, inspector, journeyConflict, connectParent, appendMessage, proposeBudget, switchToAdvisor, confirmCandidate, continueToPlanning, recover, retry, endConflictingJourney };
}
