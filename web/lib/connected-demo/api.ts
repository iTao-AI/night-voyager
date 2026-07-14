import {
  parseBootstrap,
  parseBrief,
  parseLedger,
  parseSession,
  parseTask,
  type AdvisorLedger,
  type AdvisorReviewBody,
  type CancelTaskBody,
  type CreateTaskBody,
  type CurrentDecisionBrief,
  type DecisionResult,
  type FamilyDecisionBody,
  type ReviewResult,
  type SessionProjection,
  type TaskProjection,
} from "./contracts";

export interface ConnectedDemoApi {
  bootstrap(): Promise<{ csrf_token: string }>;
  mint(role: "advisor" | "parent", csrf: string): Promise<SessionProjection>;
  revoke(csrf: string): Promise<void>;
  advisorLedger(caseId: string): Promise<AdvisorLedger>;
  createTask(caseId: string, body: CreateTaskBody, csrf: string, key: string): Promise<TaskProjection>;
  task(taskId: string): Promise<TaskProjection>;
  cancelTask(taskId: string, body: CancelTaskBody, csrf: string, key: string): Promise<TaskProjection>;
  review(caseId: string, body: AdvisorReviewBody, csrf: string, key: string): Promise<ReviewResult>;
  currentBrief(caseId: string): Promise<CurrentDecisionBrief>;
  decide(briefId: string, body: FamilyDecisionBody, csrf: string, key: string): Promise<DecisionResult>;
}

export class ConnectedDemoApiError extends Error {
  constructor(public readonly status: number, public readonly code: string) {
    super(code);
  }
}

async function json(
  path: string,
  init?: RequestInit,
): Promise<unknown> {
  const response = await fetch(path, { ...init, cache: "no-store" });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const code = payload && typeof payload === "object" && "code" in payload ? String(payload.code) : "request_failed";
    throw new ConnectedDemoApiError(response.status, code);
  }
  return payload;
}

function mutation(csrf: string, key?: string): Headers {
  const headers = new Headers({ "Content-Type": "application/json", "X-CSRF-Token": csrf });
  if (key) headers.set("Idempotency-Key", key);
  return headers;
}

export function createConnectedDemoApi(): ConnectedDemoApi {
  return {
    async bootstrap() {
      return parseBootstrap(await json("/api/demo/session-bootstrap"));
    },
    async mint(role, csrf) {
      return parseSession(await json("/api/demo/sessions", {
        method: "POST",
        headers: mutation(csrf),
        body: JSON.stringify({ demo_actor: role }),
      }));
    },
    async revoke(csrf) {
      const response = await fetch("/api/demo/session", {
        method: "DELETE",
        headers: mutation(csrf),
        cache: "no-store",
      });
      if (!response.ok) throw new ConnectedDemoApiError(response.status, "session_revoke_failed");
    },
    async advisorLedger(caseId) {
      return parseLedger(await json(`/api/demo/cases/${caseId}/advisor-ledger`));
    },
    async createTask(caseId, body, csrf, key) {
      return parseTask(await json(`/api/demo/cases/${caseId}/agent-tasks`, {
        method: "POST", headers: mutation(csrf, key), body: JSON.stringify(body),
      }));
    },
    async task(taskId) {
      return parseTask(await json(`/api/demo/tasks/${taskId}`));
    },
    async cancelTask(taskId, body, csrf, key) {
      return parseTask(await json(`/api/demo/tasks/${taskId}/cancel`, {
        method: "POST", headers: mutation(csrf, key), body: JSON.stringify(body),
      }));
    },
    async review(caseId, body, csrf, key) {
      return await json(`/api/demo/cases/${caseId}/advisor-reviews`, {
        method: "POST", headers: mutation(csrf, key), body: JSON.stringify(body),
      }) as ReviewResult;
    },
    async currentBrief(caseId) {
      return parseBrief(await json(`/api/demo/cases/${caseId}/current-decision-brief`));
    },
    async decide(briefId, body, csrf, key) {
      return await json(`/api/demo/decision-briefs/${briefId}/family-decisions`, {
        method: "POST", headers: mutation(csrf, key), body: JSON.stringify(body),
      }) as DecisionResult;
    },
  };
}
