"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  createPlanExecutionApi,
  isPlanExecutionSessionLoss,
  isPlanExecutionStaleAuthority,
  type PlanExecutionApi,
} from "./api";
import type {
  PlanExecutionContext,
  PlanExecutionRole,
  TimelineExecutionView,
  TimelineMutationReceipt,
} from "./contracts";
import { idempotencyFor, type PlanExecutionIdempotencyRecord } from "./idempotency";
import {
  beginPlanExecutionMutation,
  derivePlanExecutionState,
  loadingPlanExecutionState,
  type PlanExecutionState,
} from "./reducer";
import {
  loadPlanExecutionEnvelope,
  clearPlanExecutionEnvelope,
  savePlanExecutionEnvelope,
  type PlanExecutionEnvelopeV1,
} from "./session-storage";
import type { PlanExecutionDemoScenario } from "./scenario";

export interface PlanExecutionController {
  state: PlanExecutionState;
  busy: boolean;
  connect(role: PlanExecutionRole): Promise<void>;
  switchRole(role: PlanExecutionRole): Promise<void>;
  start(): Promise<void>;
  attest(kind?: "progress" | "completion" | "blocked", reason?: "missing_required_input" | "external_dependency_unavailable" | "deadline_at_risk"): Promise<void>;
  verify(action: "verify" | "request_update"): Promise<void>;
  reassess(trigger: "blocked_attestation" | "deadline_elapsed"): Promise<void>;
  recover(): Promise<void>;
}

type Operation = "start" | "attest" | "verify" | "reassess";
interface PendingMutation {
  operation: Operation;
  body: Record<string, unknown>;
  record: PlanExecutionIdempotencyRecord;
  role: PlanExecutionRole;
  caseId: string;
  call(csrfToken: string, key: string): Promise<TimelineMutationReceipt>;
}

const RESULT_KIND_BY_OPERATION = {
  start: "timeline_execution_started",
  attest: "timeline_checkpoint_attested",
  verify: "timeline_checkpoint_verified",
  reassess: "timeline_reassessment_requested",
} as const;

function receiptReconciles(
  pending: PendingMutation,
  receipt: TimelineMutationReceipt,
  context: PlanExecutionContext,
  view: TimelineExecutionView,
): boolean {
  if (receipt.operation !== pending.operation
    || receipt.result_kind !== RESULT_KIND_BY_OPERATION[pending.operation]
    || receipt.execution_id !== view.execution.execution_id
    || receipt.execution_id !== context.execution_id
    || view.execution.case_id !== context.case_id
    || view.execution.timeline_plan_id !== context.timeline_plan_id) return false;

  const bodyCheckpoint = pending.operation === "start"
    ? null
    : typeof pending.body.checkpoint_id === "string"
      ? pending.body.checkpoint_id
      : undefined;
  if (bodyCheckpoint === undefined
    || receipt.checkpoint_id !== bodyCheckpoint
    || (bodyCheckpoint !== null
      && !view.checkpoints.some(({ checkpoint_id }) =>
        checkpoint_id === bodyCheckpoint))) return false;

  if (pending.operation === "start") {
    return receipt.result_id === view.execution.execution_id;
  }
  if (pending.operation === "attest") {
    return view.latest_attestation?.attestation_id === receipt.result_id
      && view.latest_attestation.checkpoint_id === bodyCheckpoint;
  }
  if (pending.operation === "verify") {
    return view.latest_verification?.verification_id === receipt.result_id
      && view.latest_verification.checkpoint_id === bodyCheckpoint;
  }
  return view.reassessment?.reassessment_id === receipt.result_id
    && view.reassessment.checkpoint_id === bodyCheckpoint;
}

function envelopeFor(
  state: PlanExecutionState,
  role: PlanExecutionRole,
  scenario: PlanExecutionDemoScenario,
  previous?: PlanExecutionEnvelopeV1 | null,
): PlanExecutionEnvelopeV1 {
  const checkpoint = state.view?.current_checkpoint ?? null;
  return {
    schema_version: 1,
    journey: "plan-execution",
    scenario,
    role,
    caseId: state.context?.case_id ?? previous?.caseId ?? "",
    timelinePlanId: state.context?.timeline_plan_id ?? previous?.timelinePlanId ?? "",
    executionId: state.view?.execution.execution_id ?? state.context?.execution_id ?? null,
    executionVersion: state.view?.execution.row_version ?? null,
    checkpointId: checkpoint?.checkpoint_id ?? null,
    checkpointVersion: checkpoint?.row_version ?? null,
    lastReceiptId: state.receipt?.receipt_id ?? previous?.lastReceiptId ?? null,
    mutations: previous?.mutations ?? {},
  };
}

export function usePlanExecution(
  suppliedApi?: PlanExecutionApi,
  scenario: PlanExecutionDemoScenario = "happy",
): PlanExecutionController {
  const api = suppliedApi ?? createPlanExecutionApi();
  const [state, setState] = useState<PlanExecutionState>(loadingPlanExecutionState);
  const [busy, setBusy] = useState(false);
  const csrf = useRef<string | null>(null);
  const locked = useRef(false);
  const generation = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const pendingMutation = useRef<PendingMutation | null>(null);
  const recoveryStarted = useRef(false);

  const beginGeneration = useCallback(() => {
    controller.current?.abort();
    controller.current = new AbortController();
    generation.current += 1;
    return generation.current;
  }, []);

  useEffect(() => () => controller.current?.abort(), []);

  const finishGeneration = useCallback((expectedGeneration: number) => {
    if (expectedGeneration !== generation.current) return;
    locked.current = false;
    setBusy(false);
  }, []);

  const closeSessionChanged = useCallback((
    error: unknown,
    clearAuthority = false,
  ) => {
    csrf.current = null;
    pendingMutation.current = null;
    if (clearAuthority) clearPlanExecutionEnvelope();
    setState((previous) => clearAuthority
      ? {
          ...loadingPlanExecutionState,
          value: "session_changed",
          error: error instanceof Error ? error.message : "session_changed",
        }
      : {
          ...previous,
          value: "session_changed",
          error: error instanceof Error ? error.message : "session_changed",
          operation: null,
          safeDisplayState: previous.value === "mutation_in_flight"
            ? previous.safeDisplayState
            : previous.value,
        });
  }, []);

  const clearMutationSlot = useCallback((operation: Operation) => {
    const stored = loadPlanExecutionEnvelope();
    if (!stored) return;
    const mutations = { ...stored.mutations };
    delete mutations[operation];
    savePlanExecutionEnvelope({ ...stored, mutations });
  }, []);

  const loadAuthority = useCallback(async (
    role: PlanExecutionRole,
    receipt: TimelineMutationReceipt | null = null,
    expectedGeneration = generation.current,
  ) => {
    const context = await api.context();
    if (expectedGeneration !== generation.current) return;
    if (context.active_role !== role) {
      closeSessionChanged(new Error("session_changed"));
      return;
    }
    const view = context.execution_id === null ? null : await api.read(context.case_id);
    if (expectedGeneration !== generation.current) return;
    const confirmed = view === null ? context : await api.context();
    if (expectedGeneration !== generation.current) return;
    const crossCase = confirmed.case_id !== context.case_id
      || confirmed.timeline_plan_id !== context.timeline_plan_id
      || confirmed.execution_id !== context.execution_id;
    if (crossCase || confirmed.active_role !== role) {
      closeSessionChanged(new Error("session_changed"), crossCase);
      return;
    }
    const next = derivePlanExecutionState(confirmed, view, receipt);
    setState(next);
    savePlanExecutionEnvelope(envelopeFor(next, role, scenario, loadPlanExecutionEnvelope()));
  }, [api, closeSessionChanged, scenario]);

  const connect = useCallback(async (role: PlanExecutionRole) => {
    if (locked.current) return;
    const expectedGeneration = beginGeneration();
    locked.current = true;
    setBusy(true);
    try {
      const bootstrap = await api.bootstrap();
      const session = await api.mint(role, bootstrap.csrf_token, scenario);
      if (expectedGeneration !== generation.current) return;
      csrf.current = session.csrf_token;
      await loadAuthority(role, null, expectedGeneration);
    } catch (error) {
      if (expectedGeneration === generation.current) {
        setState({ value: "recoverable_error", context: null, view: null, receipt: null, error: error instanceof Error ? error.message : "request_failed", operation: null, safeDisplayState: null });
      }
    } finally {
      finishGeneration(expectedGeneration);
    }
  }, [api, beginGeneration, finishGeneration, loadAuthority, scenario]);

  const switchRole = useCallback(async (role: PlanExecutionRole) => {
    if (locked.current || !csrf.current || !state.context
      || state.context.active_role === role) return;
    const expectedGeneration = beginGeneration();
    const priorCsrf = csrf.current;
    const priorContext = state.context;
    locked.current = true;
    setBusy(true);
    try {
      const session = await api.mint(role, priorCsrf, scenario);
      if (expectedGeneration !== generation.current) return;
      csrf.current = session.csrf_token;
      const context = await api.context();
      if (expectedGeneration !== generation.current) return;
      const crossCase = context.case_id !== priorContext.case_id
        || context.timeline_plan_id !== priorContext.timeline_plan_id
        || context.execution_id !== priorContext.execution_id;
      if (crossCase || context.active_role !== role) {
        closeSessionChanged(new Error("session_changed"), crossCase);
        return;
      }
      await loadAuthority(role, null, expectedGeneration);
    } catch (error) {
      if (expectedGeneration === generation.current) {
        if (isPlanExecutionSessionLoss(error)) {
          closeSessionChanged(error);
        } else {
          setState((previous) => ({
            ...previous,
            value: "recoverable_error",
            error: error instanceof Error ? error.message : "request_failed",
            operation: null,
          }));
        }
      }
    } finally {
      finishGeneration(expectedGeneration);
    }
  }, [
    api,
    beginGeneration,
    closeSessionChanged,
    finishGeneration,
    loadAuthority,
    scenario,
    state.context,
  ]);

  const runMutation = useCallback(async (
    operation: Operation,
    body: Record<string, unknown>,
    call: (csrfToken: string, key: string) => Promise<TimelineMutationReceipt>,
  ) => {
    if (locked.current || !state.context || !csrf.current) return;
    locked.current = true;
    setBusy(true);
    const expectedGeneration = generation.current;
    try {
      const stored = loadPlanExecutionEnvelope();
      if (stored && (stored.scenario !== scenario
        || stored.caseId !== state.context.case_id
        || stored.timelinePlanId !== state.context.timeline_plan_id
        || stored.role !== state.context.active_role)) {
        clearPlanExecutionEnvelope();
        throw new Error("session_changed");
      }
      const previous = stored ?? envelopeFor(state, state.context.active_role, scenario);
      const record = await idempotencyFor(body, previous.mutations[operation]);
      const pending = {
        ...previous,
        mutations: { ...previous.mutations, [operation]: record },
      };
      savePlanExecutionEnvelope(pending);
      pendingMutation.current = {
        operation,
        body: structuredClone(body),
        record,
        role: state.context.active_role,
        caseId: state.context.case_id,
        call,
      };
      setState(beginPlanExecutionMutation(state, operation));
      const sessionCsrf = csrf.current;
      if (!sessionCsrf) throw new Error("session_changed");
      const receipt = await call(sessionCsrf, record.idempotencyKey);
      if (expectedGeneration !== generation.current) return;
      const withReceipt = { ...pending, lastReceiptId: receipt.receipt_id };
      const view = await api.read(state.context.case_id);
      if (expectedGeneration !== generation.current) return;
      const context = await api.context();
      if (expectedGeneration !== generation.current) return;
      const crossCase = context.case_id !== state.context.case_id
        || context.timeline_plan_id !== state.context.timeline_plan_id
        || context.execution_id !== view.execution.execution_id;
      if (crossCase || context.active_role !== state.context.active_role) {
        pendingMutation.current = null;
        clearMutationSlot(operation);
        closeSessionChanged(new Error("session_changed"), crossCase);
        return;
      }
      const activePending = pendingMutation.current;
      if (!activePending
        || !receiptReconciles(activePending, receipt, context, view)) {
        pendingMutation.current = null;
        clearMutationSlot(operation);
        closeSessionChanged(new Error("session_changed"));
        return;
      }
      const next = derivePlanExecutionState(context, view, receipt);
      setState(next);
      savePlanExecutionEnvelope(envelopeFor(next, context.active_role, scenario, { ...withReceipt, mutations: {} }));
      pendingMutation.current = null;
    } catch (error) {
      if (expectedGeneration === generation.current) {
        if (isPlanExecutionSessionLoss(error)) {
          pendingMutation.current = null;
          clearMutationSlot(operation);
          closeSessionChanged(error);
        } else if (isPlanExecutionStaleAuthority(error)) {
          pendingMutation.current = null;
          clearMutationSlot(operation);
          try {
            await loadAuthority(state.context.active_role, null, expectedGeneration);
          } catch (refreshError) {
            if (expectedGeneration === generation.current) {
              if (isPlanExecutionSessionLoss(refreshError)) {
                closeSessionChanged(refreshError);
              } else {
                setState((previous) => ({
                  ...previous,
                  value: "recoverable_error",
                  error: refreshError instanceof Error
                    ? refreshError.message
                    : "request_failed",
                  operation: null,
                }));
              }
            }
          }
        } else {
          setState({
            ...state,
            value: "recoverable_error",
            error: error instanceof Error ? error.message : "request_failed",
            operation,
            safeDisplayState: state.value === "mutation_in_flight"
              ? state.safeDisplayState
              : state.value,
          });
        }
      }
    } finally {
      finishGeneration(expectedGeneration);
    }
  }, [
    api,
    clearMutationSlot,
    closeSessionChanged,
    finishGeneration,
    loadAuthority,
    scenario,
    state,
  ]);

  const start = useCallback(async () => {
    if (!state.context) return;
    const body = {
      schema_version: 1,
      case_id: state.context.case_id,
      expected_case_revision: state.context.case_revision,
    };
    await runMutation("start", body, (token, key) =>
      api.start(state.context!.timeline_plan_id, body, token, key));
  }, [api, runMutation, state.context]);

  const attest = useCallback(async (
    kind: "progress" | "completion" | "blocked" = "completion",
    reason: "missing_required_input" | "external_dependency_unavailable" | "deadline_at_risk" = "missing_required_input",
  ) => {
    const context = state.context;
    const view = state.view;
    const checkpoint = view?.current_checkpoint;
    if (!context || !view || !checkpoint) return;
    const body = {
      schema_version: 1,
      case_id: context.case_id,
      checkpoint_id: checkpoint.checkpoint_id,
      expected_execution_version: view.execution.row_version,
      expected_checkpoint_version: checkpoint.row_version,
      attestation_kind: kind,
      status_code: kind === "completion" ? "ready_for_advisor" : kind === "blocked" ? "work_blocked" : "work_in_progress",
      attestation_code: `${checkpoint.milestone_key}_status_confirmed`,
      reason_code: kind === "blocked" ? reason : "not_applicable",
    };
    await runMutation("attest", body, (token, key) =>
      api.attest(view.execution.execution_id, body, token, key));
  }, [api, runMutation, state.context, state.view]);

  const verify = useCallback(async (action: "verify" | "request_update") => {
    const context = state.context;
    const view = state.view;
    const checkpoint = view?.current_checkpoint;
    const attestation = view?.latest_attestation;
    if (!context || !view || !checkpoint || !attestation) return;
    const body = {
      schema_version: 1,
      case_id: context.case_id,
      checkpoint_id: checkpoint.checkpoint_id,
      attestation_id: attestation.attestation_id,
      expected_execution_version: view.execution.row_version,
      expected_checkpoint_version: checkpoint.row_version,
      action,
      reason_code: action === "verify" ? "attestation_verified" : "status_update_required",
    };
    await runMutation("verify", body, (token, key) =>
      api.verify(view.execution.execution_id, body, token, key));
  }, [api, runMutation, state.context, state.view]);

  const reassess = useCallback(async (trigger: "blocked_attestation" | "deadline_elapsed") => {
    const context = state.context;
    const view = state.view;
    const checkpoint = view?.current_checkpoint;
    if (!context || !view || !checkpoint) return;
    const body = {
      schema_version: 1,
      case_id: context.case_id,
      checkpoint_id: checkpoint.checkpoint_id,
      expected_execution_version: view.execution.row_version,
      expected_checkpoint_version: checkpoint.row_version,
      trigger,
      trigger_reference_id: trigger === "blocked_attestation"
        ? view.latest_attestation?.attestation_id ?? null
        : null,
    };
    await runMutation("reassess", body, (token, key) =>
      api.reassess(view.execution.execution_id, body, token, key));
  }, [api, runMutation, state.context, state.view]);

  const recover = useCallback(async () => {
    const pending = pendingMutation.current;
    if (pending) {
      const expectedGeneration = beginGeneration();
      locked.current = true;
      setBusy(true);
      try {
        const sessionCsrf = csrf.current;
        if (!sessionCsrf) throw new Error("session_changed");
        const context = await api.context();
        if (expectedGeneration !== generation.current
          || context.active_role !== pending.role
          || context.case_id !== pending.caseId) {
          throw new Error("session_changed");
        }
        const receipt = await pending.call(sessionCsrf, pending.record.idempotencyKey);
        if (expectedGeneration !== generation.current) return;
        const view = await api.read(context.case_id);
        if (expectedGeneration !== generation.current) return;
        const confirmed = await api.context();
        if (expectedGeneration !== generation.current) return;
        const crossCase = confirmed.case_id !== context.case_id
          || confirmed.timeline_plan_id !== context.timeline_plan_id
          || confirmed.execution_id !== view.execution.execution_id;
        if (crossCase || confirmed.active_role !== pending.role) {
          pendingMutation.current = null;
          clearMutationSlot(pending.operation);
          closeSessionChanged(new Error("session_changed"), crossCase);
          return;
        }
        if (!receiptReconciles(pending, receipt, confirmed, view)) {
          pendingMutation.current = null;
          clearMutationSlot(pending.operation);
          closeSessionChanged(new Error("session_changed"));
          return;
        }
        const withReceipt = {
          ...(loadPlanExecutionEnvelope() ?? envelopeFor(
            state,
            pending.role,
            scenario,
          )),
          mutations: {},
          lastReceiptId: receipt.receipt_id,
        };
        const next = derivePlanExecutionState(confirmed, view, receipt);
        setState(next);
        savePlanExecutionEnvelope(envelopeFor(
          next,
          pending.role,
          scenario,
          withReceipt,
        ));
        pendingMutation.current = null;
      } catch (error) {
        if (expectedGeneration === generation.current) {
          if (isPlanExecutionSessionLoss(error)) {
            pendingMutation.current = null;
            clearMutationSlot(pending.operation);
            closeSessionChanged(error);
          } else if (isPlanExecutionStaleAuthority(error)) {
            pendingMutation.current = null;
            clearMutationSlot(pending.operation);
            try {
              await loadAuthority(pending.role, null, expectedGeneration);
            } catch (refreshError) {
              if (expectedGeneration === generation.current) {
                if (isPlanExecutionSessionLoss(refreshError)) {
                  closeSessionChanged(refreshError);
                } else {
                  setState((previous) => ({
                    ...previous,
                    value: "recoverable_error",
                    error: refreshError instanceof Error
                      ? refreshError.message
                      : "request_failed",
                    operation: null,
                  }));
                }
              }
            }
          } else {
            setState((previous) => ({
              ...previous,
              value: "recoverable_error",
              error: error instanceof Error ? error.message : "request_failed",
            }));
          }
        }
      } finally {
        finishGeneration(expectedGeneration);
      }
      return;
    }
    const stored = loadPlanExecutionEnvelope();
    if (!stored) {
      setState({ ...loadingPlanExecutionState, value: "recoverable_error", error: "recovery metadata unavailable" });
      return;
    }
    if (stored.scenario !== scenario) {
      clearPlanExecutionEnvelope();
      setState({
        ...loadingPlanExecutionState,
        value: "recoverable_error",
        error: "recovery metadata unavailable",
      });
      return;
    }
    const expectedGeneration = beginGeneration();
    locked.current = true;
    setBusy(true);
    try {
      const priorContext = await api.context();
      if (expectedGeneration !== generation.current) return;
      if (priorContext.active_role !== stored.role
        || priorContext.case_id !== stored.caseId
        || priorContext.timeline_plan_id !== stored.timelinePlanId
        || (stored.executionId !== null
          && priorContext.execution_id !== stored.executionId)) {
        clearPlanExecutionEnvelope();
        throw new Error("session_changed");
      }
      let bootstrap: { csrf_token: string };
      try {
        bootstrap = await api.bootstrap();
      } catch (error) {
        if (!(error instanceof Error)
          || error.message !== "bff_session_recovery_required") throw error;
        bootstrap = await api.bootstrap();
      }
      const session = await api.mint(stored.role, bootstrap.csrf_token, scenario);
      if (expectedGeneration !== generation.current) return;
      csrf.current = session.csrf_token;
      const context = await api.context();
      if (expectedGeneration !== generation.current) return;
      if (context.active_role !== stored.role
        || context.case_id !== stored.caseId
        || context.timeline_plan_id !== stored.timelinePlanId
        || (stored.executionId !== null
          && context.execution_id !== stored.executionId)) {
        clearPlanExecutionEnvelope();
        throw new Error("session_changed");
      }
      const view = context.execution_id === null ? null : await api.read(context.case_id);
      if (expectedGeneration !== generation.current) return;
      const confirmed = view === null ? context : await api.context();
      if (expectedGeneration !== generation.current) return;
      const crossCase = confirmed.case_id !== context.case_id
        || confirmed.timeline_plan_id !== context.timeline_plan_id
        || confirmed.execution_id !== context.execution_id;
      if (crossCase || confirmed.active_role !== stored.role) {
        closeSessionChanged(new Error("session_changed"), crossCase);
        return;
      }
      const next = derivePlanExecutionState(confirmed, view);
      setState(next);
      savePlanExecutionEnvelope(envelopeFor(next, stored.role, scenario, stored));
    } catch (error) {
      if (expectedGeneration === generation.current) {
        if (isPlanExecutionSessionLoss(error)) {
          closeSessionChanged(error);
        } else {
          setState({
            ...loadingPlanExecutionState,
            value: "recoverable_error",
            error: error instanceof Error ? error.message : "request_failed",
          });
        }
      }
    } finally {
      finishGeneration(expectedGeneration);
    }
  }, [
    api,
    beginGeneration,
    clearMutationSlot,
    closeSessionChanged,
    finishGeneration,
    loadAuthority,
    scenario,
    state,
  ]);

  useEffect(() => {
    if (recoveryStarted.current) return;
    recoveryStarted.current = true;
    if (loadPlanExecutionEnvelope()) {
      queueMicrotask(() => { void recover(); });
    }
  }, [recover]);

  return { state, busy, connect, switchRole, start, attest, verify, reassess, recover };
}
