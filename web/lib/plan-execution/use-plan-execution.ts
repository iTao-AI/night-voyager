"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { createPlanExecutionApi, type PlanExecutionApi } from "./api";
import type { PlanExecutionRole, TimelineMutationReceipt } from "./contracts";
import { idempotencyFor, type PlanExecutionIdempotencyRecord } from "./idempotency";
import {
  beginPlanExecutionMutation,
  derivePlanExecutionState,
  loadingPlanExecutionState,
  type PlanExecutionState,
} from "./reducer";
import {
  loadPlanExecutionEnvelope,
  savePlanExecutionEnvelope,
  type PlanExecutionEnvelopeV1,
} from "./session-storage";

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

function envelopeFor(
  state: PlanExecutionState,
  role: PlanExecutionRole,
  previous?: PlanExecutionEnvelopeV1 | null,
): PlanExecutionEnvelopeV1 {
  const checkpoint = state.view?.current_checkpoint ?? null;
  return {
    schema_version: 1,
    journey: "plan-execution",
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
): PlanExecutionController {
  const api = suppliedApi ?? createPlanExecutionApi();
  const [state, setState] = useState<PlanExecutionState>(loadingPlanExecutionState);
  const [busy, setBusy] = useState(false);
  const csrf = useRef<string | null>(null);
  const locked = useRef(false);
  const generation = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const pendingMutation = useRef<PendingMutation | null>(null);

  const beginGeneration = useCallback(() => {
    controller.current?.abort();
    controller.current = new AbortController();
    generation.current += 1;
    return generation.current;
  }, []);

  useEffect(() => () => controller.current?.abort(), []);

  const loadAuthority = useCallback(async (
    role: PlanExecutionRole,
    receipt: TimelineMutationReceipt | null = null,
    expectedGeneration = generation.current,
  ) => {
    const context = await api.context();
    if (expectedGeneration !== generation.current) return;
    if (context.active_role !== role) {
      setState({ value: "session_changed", context, view: null, receipt, error: "role authority changed", operation: null, safeDisplayState: null });
      return;
    }
    const view = context.execution_id === null ? null : await api.read(context.case_id);
    if (expectedGeneration !== generation.current) return;
    const next = derivePlanExecutionState(context, view, receipt);
    setState(next);
    savePlanExecutionEnvelope(envelopeFor(next, role, loadPlanExecutionEnvelope()));
  }, [api]);

  const connect = useCallback(async (role: PlanExecutionRole) => {
    const expectedGeneration = beginGeneration();
    locked.current = true;
    setBusy(true);
    try {
      const bootstrap = await api.bootstrap();
      const session = await api.mint(role, bootstrap.csrf_token);
      if (expectedGeneration !== generation.current) return;
      csrf.current = session.csrf_token;
      await loadAuthority(role, null, expectedGeneration);
    } catch (error) {
      if (expectedGeneration === generation.current) {
        setState({ value: "recoverable_error", context: null, view: null, receipt: null, error: error instanceof Error ? error.message : "request_failed", operation: null, safeDisplayState: null });
      }
    } finally {
      if (expectedGeneration === generation.current) {
        locked.current = false;
        setBusy(false);
      }
    }
  }, [api, beginGeneration, loadAuthority]);

  const switchRole = useCallback(async (role: PlanExecutionRole) => {
    beginGeneration();
    locked.current = false;
    if (csrf.current) await api.revoke(csrf.current);
    csrf.current = null;
    await connect(role);
  }, [api, beginGeneration, connect]);

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
      const previous = loadPlanExecutionEnvelope() ?? envelopeFor(state, state.context.active_role);
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
      const receipt = await call(csrf.current, record.idempotencyKey);
      if (expectedGeneration !== generation.current) return;
      const withReceipt = { ...pending, lastReceiptId: receipt.receipt_id };
      savePlanExecutionEnvelope(withReceipt);
      const view = await api.read(state.context.case_id);
      if (expectedGeneration !== generation.current) return;
      const next = derivePlanExecutionState(state.context, view, receipt);
      setState(next);
      savePlanExecutionEnvelope(envelopeFor(next, state.context.active_role, { ...withReceipt, mutations: {} }));
      pendingMutation.current = null;
    } catch (error) {
      if (expectedGeneration === generation.current) {
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
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }, [api, state]);

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
        const bootstrap = await api.bootstrap();
        const session = await api.mint(pending.role, bootstrap.csrf_token);
        if (expectedGeneration !== generation.current) return;
        csrf.current = session.csrf_token;
        const context = await api.context();
        if (expectedGeneration !== generation.current
          || context.active_role !== pending.role
          || context.case_id !== pending.caseId) {
          throw new Error("session_changed");
        }
        const receipt = await pending.call(session.csrf_token, pending.record.idempotencyKey);
        if (expectedGeneration !== generation.current) return;
        const view = await api.read(context.case_id);
        if (expectedGeneration !== generation.current) return;
        const next = derivePlanExecutionState(context, view, receipt);
        setState(next);
        savePlanExecutionEnvelope(envelopeFor(next, pending.role, {
          ...(loadPlanExecutionEnvelope() ?? envelopeFor(next, pending.role)),
          mutations: {},
          lastReceiptId: receipt.receipt_id,
        }));
        pendingMutation.current = null;
      } catch (error) {
        if (expectedGeneration === generation.current) {
          setState((previous) => ({ ...previous, value: error instanceof Error && error.message === "session_changed" ? "session_changed" : "recoverable_error", error: error instanceof Error ? error.message : "request_failed" }));
        }
      } finally {
        if (expectedGeneration === generation.current) {
          locked.current = false;
          setBusy(false);
        }
      }
      return;
    }
    const stored = loadPlanExecutionEnvelope();
    if (!stored) {
      setState({ ...loadingPlanExecutionState, value: "recoverable_error", error: "recovery metadata unavailable" });
      return;
    }
    await switchRole(stored.role);
  }, [api, beginGeneration, switchRole]);

  return { state, busy, connect, switchRole, start, attest, verify, reassess, recover };
}
