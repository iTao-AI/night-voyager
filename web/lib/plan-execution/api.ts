import {
  parsePlanExecutionContext,
  parseTimelineExecutionView,
  parseTimelineMutationReceipt,
  type PlanExecutionContext,
  type PlanExecutionRole,
  type TimelineExecutionView,
  type TimelineMutationReceipt,
} from "./contracts";

export interface PlanExecutionApi {
  bootstrap(): Promise<{ csrf_token: string }>;
  mint(role: PlanExecutionRole, csrf: string): Promise<{ role: PlanExecutionRole; csrf_token: string }>;
  revoke(csrf: string): Promise<void>;
  context(): Promise<PlanExecutionContext>;
  read(caseId: string): Promise<TimelineExecutionView>;
  start(timelinePlanId: string, body: unknown, csrf: string, key: string): Promise<TimelineMutationReceipt>;
  attest(executionId: string, body: unknown, csrf: string, key: string): Promise<TimelineMutationReceipt>;
  verify(executionId: string, body: unknown, csrf: string, key: string): Promise<TimelineMutationReceipt>;
  reassess(executionId: string, body: unknown, csrf: string, key: string): Promise<TimelineMutationReceipt>;
}
async function json(path: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(path, { ...init, cache: "no-store" });
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(
    body && typeof body === "object" && "code" in body ? String(body.code) : "request_failed",
  );
  return body;
}
function headers(csrf: string, key?: string): Headers {
  const value = new Headers({ "Content-Type": "application/json", "X-CSRF-Token": csrf });
  if (key) value.set("Idempotency-Key", key);
  return value;
}
function session(value: unknown): { role: PlanExecutionRole; csrf_token: string } {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error("invalid session");
  const item = value as Record<string, unknown>;
  if (!["advisor", "student", "parent"].includes(String(item.role)) || typeof item.csrf_token !== "string") throw new Error("invalid session");
  return item as unknown as { role: PlanExecutionRole; csrf_token: string };
}
export function createPlanExecutionApi(): PlanExecutionApi {
  const mutation = async (path: string, body: unknown, csrf: string, key: string) =>
    parseTimelineMutationReceipt(await json(path, {
      method: "POST", headers: headers(csrf, key), body: JSON.stringify(body),
    }));
  return {
    async bootstrap() {
      const value = await json("/api/demo/session-bootstrap");
      if (typeof value !== "object" || value === null || !("csrf_token" in value) || typeof value.csrf_token !== "string") throw new Error("invalid bootstrap");
      return { csrf_token: value.csrf_token };
    },
    async mint(role, csrf) {
      return session(await json("/api/demo/sessions", {
        method: "POST", headers: headers(csrf), body: JSON.stringify({ demo_actor: role }),
      }));
    },
    async revoke(csrf) {
      const response = await fetch("/api/demo/session", { method: "DELETE", headers: headers(csrf), cache: "no-store" });
      if (!response.ok) throw new Error("session_revoke_failed");
    },
    async context() {
      return parsePlanExecutionContext(await json("/api/demo/plan-execution-context"));
    },
    async read(caseId) {
      return parseTimelineExecutionView(await json(`/api/demo/cases/${caseId}/timeline-execution`));
    },
    start: (timelinePlanId, body, csrf, key) => mutation(`/api/demo/timeline-plans/${timelinePlanId}/executions`, body, csrf, key),
    attest: (executionId, body, csrf, key) => mutation(`/api/demo/timeline-executions/${executionId}/checkpoint-attestations`, body, csrf, key),
    verify: (executionId, body, csrf, key) => mutation(`/api/demo/timeline-executions/${executionId}/checkpoint-verifications`, body, csrf, key),
    reassess: (executionId, body, csrf, key) => mutation(`/api/demo/timeline-executions/${executionId}/reassessments`, body, csrf, key),
  };
}
