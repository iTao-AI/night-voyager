"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { useRouter } from "next/navigation";
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
  type CollaborationJourneyEnvelopeV3,
  type CollaborationJourneyEnvelopeV2,
  type CollaborationMutationKind,
  type CollaborationPersistedPhase,
} from "../connected-demo/session-storage";
import { CollaborationDemoApiError, createCollaborationDemoApi, type VerificationBody } from "./api";
import {
  budgetDraftFromIntent,
  budgetValueMatchesIntent,
  defaultBudgetIntent,
  messageRequestForBudget,
  proposalRequestForBudget,
  renderBudgetMessage,
  validateBudgetDraft,
  type BudgetDraft,
  type BudgetValidationIssue,
  type CollaborationBudgetIntent,
} from "./budget";
import type { ConfirmedFactAdvisor, MemoryCandidateAdvisor, MemoryCandidateParticipant } from "./contracts";
import { classifyCollaborationProblem, collaborationReducer, initialCollaborationState, type CollaborationContext, type CollaborationErrorCategory } from "./reducer";

export const COLLABORATION_CASE_ID = "41000000-0000-0000-0000-000000000001";
const VERIFICATION_REASON = "The family confirmed this bounded program budget.";
const LEGACY_DEFAULT_INTENT = defaultBudgetIntent(1);
const MESSAGE_REQUEST = messageRequestForBudget(LEGACY_DEFAULT_INTENT);
const PROPOSAL_REQUEST = proposalRequestForBudget(LEGACY_DEFAULT_INTENT);
const identity = createConnectedDemoApi();
const api = createCollaborationDemoApi();

type CollaborationRouter = {
  push: (href: string) => void;
};

export const collaborationNavigation = {
  toPlanning(router: CollaborationRouter): void {
    router.push("/demo");
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
function envelopeBudgetIntent(value: CollaborationJourneyEnvelopeV2 | CollaborationJourneyEnvelopeV3): Readonly<CollaborationBudgetIntent> | null {
  return value.schema_version === 3 ? value.budgetIntent : null;
}
function participantBudget(items: readonly MemoryCandidateParticipant[], intent: CollaborationBudgetIntent | null): MemoryCandidateParticipant | null {
  const matches = items.filter((item) => item.fact_key === "family.budget" && budgetValueMatchesIntent(item.value, intent));
  return matches.length === 1 ? matches[0] : null;
}
function candidateMatchesIntent(item: MemoryCandidateAdvisor, intent: CollaborationBudgetIntent | null): boolean {
  return intent !== null
    && budgetValueMatchesIntent(item.value, intent)
    && item.case_revision === intent.expected_case_revision;
}
function candidateValueMatchesIntent(item: MemoryCandidateAdvisor, intent: CollaborationBudgetIntent | null): boolean {
  return intent !== null && budgetValueMatchesIntent(item.value, intent);
}
function matchingMessage(messages: CollaborationContext["messages"], messageId: string | null, intent: CollaborationBudgetIntent | null) {
  if (!intent) return null;
  const matches = messages.filter((item) => item.actor_role === "parent" && item.body === renderBudgetMessage(intent));
  if (messageId !== null) return matches.find((item) => item.message_event_id === messageId) ?? null;
  return matches.length === 1 ? matches[0] : null;
}
function exactRecord(record: CollaborationJourneyEnvelopeV2["mutations"][CollaborationMutationKind] | undefined, body: unknown): Promise<boolean> {
  if (!record) return Promise.resolve(false);
  return idempotencyFor(body, record).then((result) => result.fingerprint === record.fingerprint);
}
async function upgradeLegacyCollaboration(
  value: CollaborationJourneyEnvelopeV2 | CollaborationJourneyEnvelopeV3,
  messages: CollaborationContext["messages"],
): Promise<CollaborationJourneyEnvelopeV3> {
  const intent = LEGACY_DEFAULT_INTENT;
  const parentMessages = messages.filter((item) => item.actor_role === "parent");
  const legacyMessages = parentMessages.filter((item) => item.body === renderBudgetMessage(intent));
  const canObserveUnsubmittedBudget = value.phase === "bootstrapping_parent"
    || (value.phase === "thread_ready" && value.messageId === null && Object.keys(value.mutations).length === 0
      && (value.schema_version === 2 || value.budgetIntent === null));
  if (canObserveUnsubmittedBudget) {
    if (!parentMessages.length) {
      return value.schema_version === 3 ? value : { ...value, schema_version: 3, budgetIntent: null };
    }
    if (parentMessages.length !== 1 || legacyMessages.length !== 1) {
      throw new Error("legacy collaboration identity is ambiguous");
    }
    return {
      ...value,
      schema_version: 3,
      messageId: legacyMessages[0].message_event_id,
      budgetIntent: intent,
    };
  }
  if (value.schema_version === 3) return value;
  if (value.messageId !== null && !matchingMessage(messages, value.messageId, intent)) {
    throw new Error("legacy collaboration message identity mismatch");
  }
  if (value.messageId === null && ["proposal_pending", "switching_to_advisor", "advisor_reviewing", "confirmation_submitting", "replan_required"].includes(value.phase)) {
    throw new Error("legacy collaboration message identity missing");
  }
  if (value.mutations["append-message"] && !(await exactRecord(value.mutations["append-message"], MESSAGE_REQUEST))) {
    throw new Error("legacy collaboration append intent mismatch");
  }
  if (value.mutations["propose-memory-candidate"] && !(await exactRecord(value.mutations["propose-memory-candidate"], PROPOSAL_REQUEST))) {
    throw new Error("legacy collaboration proposal intent mismatch");
  }
  return { ...value, schema_version: 3, budgetIntent: intent };
}

function handoffFailure(error: unknown): CollaborationErrorCategory {
  return error instanceof HandoffValidationError ? error.category : category(error);
}

function requireHandoff(value: unknown, category: CollaborationErrorCategory = "stale"): asserts value {
  if (!value) throw new HandoffValidationError(category);
}

function envelope(
  context: CollaborationContext,
  csrf: string,
  phase: CollaborationPersistedPhase,
  mutations: CollaborationJourneyEnvelopeV2["mutations"],
  ids?: { messageId?: string | null; candidateId?: string | null },
  budgetIntent: Readonly<CollaborationBudgetIntent> | null = null,
): CollaborationJourneyEnvelopeV3 {
  const messageId = ids?.messageId ?? (budgetIntent ? matchingMessage(context.messages, null, budgetIntent)?.message_event_id ?? null : null);
  return {
    schema_version: 3,
    journey: "collaboration",
    role: context.role,
    csrf,
    caseId: context.caseId,
    threadId: context.thread?.thread_id ?? null,
    messageId,
    candidateId: context.role === "advisor" ? (ids?.candidateId ?? (advisorCandidate(context.candidate) ? context.candidate.candidate_id : null)) : null,
    phase,
    mutations,
    budgetIntent,
  };
}

export function useCollaborationDemo() {
  const router = useRouter();
  const [state, dispatch] = useReducer(collaborationReducer, COLLABORATION_CASE_ID, initialCollaborationState);
  const [journeyConflict, setJourneyConflict] = useState<"advisor-family" | null>(() => {
    if (typeof window === "undefined") return null;
    return loadDemoJourneyEnvelope()?.journey === "advisor-family" ? "advisor-family" : null;
  });
  const [inspector, setInspector] = useState<PlanningSkillInspector | null>(null);
  const [budgetDraft, setBudgetDraft] = useState<BudgetDraft>({ preferredYuan: "300000", hardCeilingYuan: "400000" });
  const [budgetIntent, setBudgetIntent] = useState<Readonly<CollaborationBudgetIntent> | null>(null);
  const [budgetValidation, setBudgetValidation] = useState<BudgetValidationIssue | null>(null);
  const updateBudgetDraft = useCallback((draft: BudgetDraft) => {
    setBudgetDraft(draft);
    setBudgetValidation(null);
  }, []);
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
        schema_version: 3,
        journey: "collaboration",
        role: "parent",
        csrf: session.csrf_token,
        caseId: COLLABORATION_CASE_ID,
        threadId: null,
        messageId: null,
        candidateId: null,
        phase: "bootstrapping_parent",
        mutations: {},
        budgetIntent: null,
      });
      const thread = await api.thread(COLLABORATION_CASE_ID);
      const messages = await api.messages(thread.thread_id);
      const stored = loadDemoJourneyEnvelope();
      if (!stored || stored.journey !== "collaboration") throw new Error("session recovery required");
      const current = await upgradeLegacyCollaboration(stored, messages.items);
      setBudgetIntent(current.budgetIntent);
      if (current.budgetIntent) setBudgetDraft(budgetDraftFromIntent(current.budgetIntent));
      const context: CollaborationContext = { role: "parent", caseId: COLLABORATION_CASE_ID, thread, messages: messages.items, candidate: null, fact: null, caseRevision: 1 };
      saveCollaborationJourney(envelope(context, session.csrf_token, "thread_ready", {}, { messageId: current.messageId }, current.budgetIntent));
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
        const current = await upgradeLegacyCollaboration(stored, messages.items);
        setBudgetIntent(current.budgetIntent);
        if (current.budgetIntent) setBudgetDraft(budgetDraftFromIntent(current.budgetIntent));
        const context: CollaborationContext = { role: "parent", caseId: stored.caseId, thread, messages: messages.items, candidate: null, fact: null, caseRevision: 1 };
        saveCollaborationJourney(envelope(context, stored.csrf, "thread_ready", {}, undefined, current.budgetIntent));
        retryAction.current = null;
        dispatch({ type: "PARENT_RELOADED", context });
        return;
      }
      const thread = await api.thread(stored.caseId);
      if (thread.thread_id !== stored.threadId) throw new Error("projection identity mismatch");
      const messages = await api.messages(thread.thread_id);
      const current = await upgradeLegacyCollaboration(stored, messages.items);
      setBudgetIntent(current.budgetIntent);
      if (current.budgetIntent) setBudgetDraft(budgetDraftFromIntent(current.budgetIntent));
      if (current.schema_version !== stored.schema_version) saveCollaborationJourney(current);
      const baseContext: CollaborationContext = { role: current.role, caseId: current.caseId, thread, messages: messages.items, candidate: null, fact: null, caseRevision: 1 };

      if (current.phase === "switching_to_advisor") {
        try {
          const participants = await api.candidates(current.caseId, "parent");
          const candidate = participantBudget(participants, current.budgetIntent);
          if (!candidate || !matchingMessage(messages.items, current.messageId, current.budgetIntent)) throw new Error("projection identity mismatch");
          const context = { ...baseContext, role: "parent" as const, candidate };
          const stable = withCollaborationMutation({ ...current, role: "parent", phase: "proposal_pending" }, "propose-memory-candidate", undefined);
          saveCollaborationJourney(stable);
          retryAction.current = null;
          dispatch({ type: "HYDRATE", phase: "proposal_pending", context });
          return;
        } catch (parentError) {
          try {
            const advisors = await api.candidates(current.caseId, "advisor");
            const candidate = advisors.find((item) => item.message_event_id === current.messageId && candidateMatchesIntent(item, current.budgetIntent)) ?? null;
            if (!candidate) throw new Error("projection identity mismatch");
            if (current.role !== "advisor") {
              retryAction.current = null;
              clearDemoJourneyEnvelope();
              dispatch({ type: "HYDRATE", phase: "switching_to_advisor", context: baseContext });
              dispatch({ type: "FAILURE", category: "session_recovery_required" });
              return;
            }
            const ledger = await identity.advisorLedger(current.caseId);
            if (ledger.case_revision !== candidate.case_revision) throw new Error("candidate revision mismatch");
            const context: CollaborationContext = { ...baseContext, role: "advisor", candidate, caseRevision: ledger.case_revision };
            setInspector(await api.planningSkillInspector(current.caseId).catch(() => null));
            saveCollaborationJourney(envelope(context, current.csrf, "advisor_reviewing", {}, { messageId: current.messageId, candidateId: candidate.candidate_id }, current.budgetIntent));
            retryAction.current = null;
            dispatch({ type: "HYDRATE", phase: "advisor_reviewing", context });
            return;
          } catch {
            throw parentError;
          }
        }
      }

      if (current.role === "parent") {
        const projectedMessage = matchingMessage(messages.items, current.messageId, current.budgetIntent);
        const participants = projectedMessage ? await api.candidates(current.caseId, "parent") : [];
        const candidate = participantBudget(participants, current.budgetIntent);
        const context: CollaborationContext = { ...baseContext, role: "parent", candidate };

        if (current.phase === "message_submitting") {
          if (projectedMessage) {
            const stable = withCollaborationMutation({ ...current, messageId: projectedMessage.message_event_id, phase: "thread_ready" }, "append-message", undefined);
            saveCollaborationJourney(stable);
            retryAction.current = null;
            dispatch({ type: "HYDRATE", phase: "thread_ready", context });
            return;
          }
          const record = current.mutations["append-message"];
          if (!record) throw new Error("missing mutation recovery record");
          const intent = current.budgetIntent;
          if (!intent || !(await exactRecord(record, messageRequestForBudget(intent)))) throw new Error("message mutation identity mismatch");
          if (conflictError) {
            const stable = withCollaborationMutation({ ...current, phase: "thread_ready" }, "append-message", undefined);
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
              if (current.schema_version !== 3 || !current.budgetIntent || !(await exactRecord(exact, messageRequestForBudget(current.budgetIntent)))) throw new Error("message mutation identity mismatch");
              await api.appendMessage(current.threadId!, messageRequestForBudget(current.budgetIntent), current.csrf, exact.idempotencyKey);
              await recoverRef.current();
            } catch (error) { if (conflict(error)) await recoverRef.current(error as CollaborationDemoApiError); else fail(error); }
          };
          dispatch({ type: "HYDRATE", phase: "message_submitting", context });
          dispatch({ type: "FAILURE", category: "transport_unavailable_or_timeout" });
          return;
        }

        const proposalRecord = current.mutations["propose-memory-candidate"];
        if (current.phase === "thread_ready" && proposalRecord) {
          if (!current.budgetIntent || !(await exactRecord(proposalRecord, proposalRequestForBudget(current.budgetIntent)))) throw new Error("proposal mutation identity mismatch");
          if (candidate) {
            const stable = withCollaborationMutation({ ...current, phase: "proposal_pending" }, "propose-memory-candidate", undefined);
            saveCollaborationJourney(stable);
            retryAction.current = null;
            dispatch({ type: "HYDRATE", phase: "proposal_pending", context });
            return;
          }
          if (conflictError) {
            const stable = withCollaborationMutation(current, "propose-memory-candidate", undefined);
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
              if (current.schema_version !== 3 || !current.budgetIntent || !(await exactRecord(exact, proposalRequestForBudget(current.budgetIntent)))) throw new Error("proposal mutation identity mismatch");
              await api.proposeCandidate(current.messageId, proposalRequestForBudget(current.budgetIntent), current.csrf, exact.idempotencyKey);
              await recoverRef.current();
            } catch (error) { if (conflict(error)) await recoverRef.current(error as CollaborationDemoApiError); else fail(error); }
          };
          dispatch({ type: "HYDRATE", phase: "thread_ready", context });
          dispatch({ type: "FAILURE", category: "transport_unavailable_or_timeout" });
          return;
        }
        if (current.phase === "proposal_pending" && !candidate) throw new Error("projection identity mismatch");
        dispatch({ type: "HYDRATE", phase: current.phase, context });
        return;
      }

      const candidates = await api.candidates(current.caseId, "advisor");
      const candidate = candidates.find((item) => item.candidate_id === current.candidateId && item.message_event_id === current.messageId && candidateValueMatchesIntent(item, current.budgetIntent)) ?? null;
      if (!candidate || candidate.message_event_id !== current.messageId || !matchingMessage(messages.items, current.messageId, current.budgetIntent)) throw new Error("projection identity mismatch");
      if (current.phase === "advisor_reviewing" && !candidateMatchesIntent(candidate, current.budgetIntent)) throw new Error("candidate revision mismatch");
      if (current.phase === "confirmation_submitting" || current.phase === "replan_required") {
        const facts = await api.confirmedFacts(current.caseId, "advisor");
        const fact = findAdvisorFact(facts.current, current.candidateId);
        const ledger = await identity.advisorLedger(current.caseId);
        const context: CollaborationContext = { ...baseContext, role: "advisor", candidate, fact, caseRevision: ledger.case_revision };
        if (current.phase === "confirmation_submitting" && candidate.state === "pending" && !candidateMatchesIntent(candidate, current.budgetIntent)) {
          const stable = withCollaborationMutation({ ...current, phase: "advisor_reviewing" }, "verify-memory-candidate", undefined);
          saveCollaborationJourney(stable);
          retryAction.current = null;
          dispatch({ type: "HYDRATE", phase: "advisor_reviewing", context });
          dispatch({ type: "FAILURE", category: "stale" });
          return;
        }
        if (candidate.state === "confirmed" && fact && ledger.case_revision > candidate.case_revision) {
          const stable = withCollaborationMutation({ ...current, phase: "replan_required" }, "verify-memory-candidate", undefined);
          saveCollaborationJourney(stable);
          retryAction.current = null;
          setInspector(await api.planningSkillInspector(current.caseId).catch(() => null));
          dispatch({ type: "HYDRATE", phase: "replan_required", context });
          return;
        }
        if (current.phase === "replan_required") throw new Error("authority proof mismatch");
        const body = verificationBody(candidate.case_revision);
        const record = current.mutations["verify-memory-candidate"];
        if (!record || candidate.state !== "pending" || ledger.case_revision !== candidate.case_revision) {
          const stable = withCollaborationMutation({ ...current, phase: "advisor_reviewing" }, "verify-memory-candidate", undefined);
          saveCollaborationJourney(stable);
          retryAction.current = null;
          dispatch({ type: "HYDRATE", phase: "advisor_reviewing", context });
          dispatch({ type: "FAILURE", category: conflictError ? category(conflictError) : (candidate.state === "pending" ? "stale" : "expired_or_terminal") });
          return;
        }
        if (conflictError) {
          const stable = withCollaborationMutation({ ...current, phase: "advisor_reviewing" }, "verify-memory-candidate", undefined);
          saveCollaborationJourney(stable);
          retryAction.current = null;
          dispatch({ type: "HYDRATE", phase: "advisor_reviewing", context });
          fail(conflictError);
          return;
        }
        if (!(await exactRecord(record, body))) throw new Error("verification mutation identity mismatch");
        retryAction.current = async () => {
          try {
            const current = loadDemoJourneyEnvelope();
            if (!current || current.journey !== "collaboration" || !current.candidateId) throw new Error("session recovery required");
            const exact = current.mutations["verify-memory-candidate"];
            if (!exact) throw new Error("missing mutation recovery record");
            if (!(await exactRecord(exact, body))) throw new Error("verification mutation identity mismatch");
            await api.verifyCandidate(current.candidateId, body, current.csrf, exact.idempotencyKey);
            await recoverRef.current();
          } catch (error) { if (conflict(error)) await recoverRef.current(error as CollaborationDemoApiError); else fail(error); }
        };
        dispatch({ type: "HYDRATE", phase: "confirmation_submitting", context });
        dispatch({ type: "FAILURE", category: "transport_unavailable_or_timeout" });
        return;
      }

      const ledger = await identity.advisorLedger(current.caseId);
      const context: CollaborationContext = { ...baseContext, role: "advisor", candidate, caseRevision: ledger.case_revision };
      setInspector(await api.planningSkillInspector(current.caseId).catch(() => null));
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

  const persistMutation = useCallback(async (
    stored: CollaborationJourneyEnvelopeV2 | CollaborationJourneyEnvelopeV3,
    operation: CollaborationMutationKind,
    body: unknown,
    phase: CollaborationPersistedPhase,
    submittedIntent: Readonly<CollaborationBudgetIntent> | null = envelopeBudgetIntent(stored) ?? LEGACY_DEFAULT_INTENT,
  ) => {
    const record = await idempotencyFor(body, stored.mutations[operation]);
    const current: CollaborationJourneyEnvelopeV3 = stored.schema_version === 3
      ? { ...stored, budgetIntent: stored.budgetIntent ?? submittedIntent }
      : { ...stored, schema_version: 3, budgetIntent: submittedIntent };
    const updated = withCollaborationMutation({ ...current, phase }, operation, record);
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

  const appendMessage = useCallback(async (draft: BudgetDraft = budgetDraft) => {
    if (state.value !== "thread_ready" || !state.context.thread) return;
    const validation = validateBudgetDraft(draft, state.context.caseRevision);
    if (!validation.ok) {
      setBudgetValidation(validation.error);
      return;
    }
    setBudgetValidation(null);
    const intent = validation.intent;
    setBudgetIntent(intent);
    setBudgetDraft(draft);
    const stored = loadDemoJourneyEnvelope();
    if (!stored || stored.journey !== "collaboration" || stored.role !== "parent") return;
    const body = messageRequestForBudget(intent);
    const attempt = async () => {
      try {
        const current = loadDemoJourneyEnvelope();
        if (!current || current.journey !== "collaboration") throw new Error("session recovery required");
        const { record, updated } = await persistMutation(current, "append-message", body, "message_submitting", intent);
        const message = await api.appendMessage(current.threadId!, body, current.csrf, record.idempotencyKey);
        const messages = await api.messages(current.threadId!);
        const context = { ...state.context, messages: messages.items };
        saveCollaborationJourney({ ...updated, phase: "thread_ready", messageId: message.message_event_id, budgetIntent: intent });
        retryAction.current = null;
        dispatch({ type: "PARENT_RELOADED", context });
      } catch (error) { if (conflict(error)) await recover(error as CollaborationDemoApiError); else fail(error); }
    };
    retryAction.current = attempt;
    dispatch({ type: "MESSAGE_SUBMIT" });
    await attempt();
  }, [budgetDraft, fail, persistMutation, recover, state]);

  const proposeBudget = useCallback(async () => {
    if (state.value !== "thread_ready") return;
    const stored = loadDemoJourneyEnvelope();
    if (!stored || stored.journey !== "collaboration" || stored.role !== "parent" || !stored.messageId) return;
    const intent = envelopeBudgetIntent(stored) ?? LEGACY_DEFAULT_INTENT;
    const body = proposalRequestForBudget(intent);
    setBudgetIntent(intent);
    setBudgetDraft(budgetDraftFromIntent(intent));
    const attempt = async () => {
      try {
        const current = loadDemoJourneyEnvelope();
        if (!current || current.journey !== "collaboration") throw new Error("session recovery required");
        if (current.schema_version !== 3 || !current.budgetIntent || !budgetValueMatchesIntent(current.budgetIntent.value, intent)) throw new Error("budget intent mismatch");
        const { record, updated } = await persistMutation(current, "propose-memory-candidate", body, "thread_ready", intent);
        await api.proposeCandidate(current.messageId!, body, current.csrf, record.idempotencyKey);
        const candidate = participantBudget(await api.candidates(current.caseId, "parent"), intent);
        if (!candidate) throw new Error("authority projection missing");
        const context = { ...state.context, candidate };
        saveCollaborationJourney({ ...updated, phase: "proposal_pending", candidateId: null, budgetIntent: intent });
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
    const intent = envelopeBudgetIntent(stored) ?? LEGACY_DEFAULT_INTENT;
    if (!stored.messageId) {
      fail(new Error("budget intent identity mismatch"));
      return;
    }
    const current: CollaborationJourneyEnvelopeV3 = stored.schema_version === 3
      ? { ...stored, budgetIntent: intent, phase: "switching_to_advisor" }
      : { ...stored, schema_version: 3, budgetIntent: intent, phase: "switching_to_advisor" };
    saveCollaborationJourney(current);
    dispatch({ type: "ROLE_SWITCH" });
    setInspector(null);
    try {
      await identity.revoke(current.csrf);
      const bootstrap = await identity.bootstrap();
      const advisor = await identity.mint("advisor", bootstrap.csrf_token);
      saveCollaborationJourney({ ...current, role: "advisor", csrf: advisor.csrf_token, candidateId: null, phase: "switching_to_advisor" });
      const thread = await api.thread(current.caseId);
      const messages = await api.messages(thread.thread_id);
      const candidates = await api.candidates(current.caseId, "advisor");
      const candidate = candidates.find((item) => item.message_event_id === current.messageId && candidateMatchesIntent(item, current.budgetIntent)) ?? null;
      if (!candidate) throw new Error("candidate projection missing");
      if (!matchingMessage(messages.items, current.messageId, current.budgetIntent)) throw new Error("message projection missing");
      const ledger = await identity.advisorLedger(current.caseId);
      if (ledger.case_revision !== candidate.case_revision) throw new Error("candidate revision mismatch");
      const context: CollaborationContext = { role: "advisor", caseId: current.caseId, thread, messages: messages.items, candidate, fact: null, caseRevision: ledger.case_revision };
      setInspector(await api.planningSkillInspector(current.caseId).catch(() => null));
      saveCollaborationJourney(envelope(context, advisor.csrf_token, "advisor_reviewing", {}, { messageId: current.messageId, candidateId: candidate.candidate_id }, current.budgetIntent));
      dispatch({ type: "ADVISOR_RELOADED", context });
    } catch (error) { fail(error); }
  }, [fail, state]);

  const confirmCandidate = useCallback(async () => {
    if (state.value !== "advisor_reviewing" || !advisorCandidate(state.context.candidate)) return;
    const stored = loadDemoJourneyEnvelope();
    if (!stored || stored.journey !== "collaboration" || stored.role !== "advisor" || !stored.candidateId) return;
    const intent = envelopeBudgetIntent(stored) ?? LEGACY_DEFAULT_INTENT;
    const projected = state.context.candidate;
    if (!candidateMatchesIntent(projected, intent) || !matchingMessage(state.context.messages, stored.messageId, intent)) {
      dispatch({ type: "FAILURE", category: "stale" });
      return;
    }
    const ledger = await identity.advisorLedger(stored.caseId).catch((error) => { fail(error); return null; });
    if (!ledger || ledger.case_revision !== projected.case_revision) { if (ledger) dispatch({ type: "FAILURE", category: "stale" }); return; }
    const body = verificationBody(projected.case_revision);
    const prove = async (result?: { result_fact_id: string | null; result_revision: number | null }) => {
      const candidates = await api.candidates(stored.caseId, "advisor");
      const candidate = candidates.find((item) => item.candidate_id === stored.candidateId && candidateValueMatchesIntent(item, intent)) ?? null;
      const facts = await api.confirmedFacts(stored.caseId, "advisor");
      const fact = findAdvisorFact(facts.current, stored.candidateId);
      const refreshed = await identity.advisorLedger(stored.caseId);
      if (!candidate || candidate.state !== "confirmed" || !fact || refreshed.case_revision <= candidate.case_revision) throw new Error("authority proof mismatch");
      if (result && (fact.confirmed_fact_id !== result.result_fact_id || refreshed.case_revision !== result.result_revision)) throw new Error("authority proof mismatch");
      setInspector(await api.planningSkillInspector(stored.caseId).catch(() => null));
      const context = { ...state.context, candidate, fact, caseRevision: refreshed.case_revision };
      const current = loadDemoJourneyEnvelope();
      if (!current || current.journey !== "collaboration") throw new Error("session recovery required");
      const currentV3: CollaborationJourneyEnvelopeV3 = current.schema_version === 3
        ? { ...current, budgetIntent: current.budgetIntent ?? intent, phase: "replan_required" }
        : { ...current, schema_version: 3, budgetIntent: intent, phase: "replan_required" };
      saveCollaborationJourney(withCollaborationMutation(currentV3, "verify-memory-candidate", undefined));
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
        const intent = envelopeBudgetIntent(stored) ?? LEGACY_DEFAULT_INTENT;

        const candidates = await api.candidates(stored.caseId, "advisor");
        const candidate = candidates.find((item) => item.candidate_id === stored.candidateId && candidateValueMatchesIntent(item, intent)) ?? null;
        requireHandoff(candidate, "stale");
        requireHandoff(matchingMessage(expectedContext.messages, stored.messageId, intent), "stale");
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

        if (["active_task", "review_required", "terminal_task_failure"].includes(ledger.phase)) {
          requireHandoff(ledger.task?.task_id, "stale");
        } else if (ledger.phase === "task_ready") {
          requireHandoff(ledger.task === null, "stale");
        } else {
          throw new HandoffValidationError("stale");
        }

        await refreshHandoffInspector(api.planningSkillInspector(stored.caseId));
        const converted = continueCollaborationAsAdvisorFamily(stored, {
          phase: ledger.phase,
          currentRevision: ledger.case_revision,
          currentTaskId: ledger.task?.task_id ?? null,
          predecessorRunId: ledger.comparison?.previous_planning_run_id ?? null,
          currentRunId: ledger.planning_run?.planning_run_id ?? null,
        });
        saveRecoveryMetadata(converted);
        retryAction.current = null;
        collaborationNavigation.toPlanning(router);
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
  }, [fail, refreshHandoffInspector, router, state]);

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

  return {
    state,
    inspector,
    journeyConflict,
    budgetDraft,
    setBudgetDraft: updateBudgetDraft,
    budgetIntent,
    budgetValidation,
    connectParent,
    appendMessage,
    proposeBudget,
    switchToAdvisor,
    confirmCandidate,
    continueToPlanning,
    recover,
    retry,
    endConflictingJourney,
  };
}
