"use client";

import { useCallback, useReducer } from "react";

import { createConnectedDemoApi } from "./api";
import { demoReducer, type DemoDisplayState } from "./reducer";
import { clearRecoveryMetadata, loadRecoveryMetadata, saveRecoveryMetadata } from "./session-storage";

const api = createConnectedDemoApi();
const initial: DemoDisplayState = { value: "bootstrapping" };

export function useConnectedDemo() {
  const [state, dispatch] = useReducer(demoReducer, initial);

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

  return { state, dispatch, connectAdvisor, recover, api };
}
