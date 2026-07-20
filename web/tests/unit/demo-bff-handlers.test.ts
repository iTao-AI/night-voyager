// @vitest-environment node
import { NextRequest } from "next/server";
import { afterAll, beforeAll, beforeEach, expect, it, vi } from "vitest";

import { GET as bootstrap } from "../../app/api/demo/session-bootstrap/route";
import { POST as sessions } from "../../app/api/demo/sessions/route";
import { DELETE as session } from "../../app/api/demo/session/route";
import { GET as ledger } from "../../app/api/demo/cases/[caseId]/advisor-ledger/route";
import { POST as tasks } from "../../app/api/demo/cases/[caseId]/agent-tasks/route";
import { GET as task } from "../../app/api/demo/tasks/[taskId]/route";
import { POST as cancel } from "../../app/api/demo/tasks/[taskId]/cancel/route";
import { GET as events } from "../../app/api/demo/tasks/[taskId]/events/route";
import { POST as review } from "../../app/api/demo/cases/[caseId]/advisor-reviews/route";
import { GET as currentBrief } from "../../app/api/demo/cases/[caseId]/current-decision-brief/route";
import { POST as decide } from "../../app/api/demo/decision-briefs/[briefId]/family-decisions/route";
import { GET as collaborationThread } from "../../app/api/demo/cases/[caseId]/collaboration-thread/route";
import { GET as collaborationMessages, POST as appendMessage } from "../../app/api/demo/collaboration-threads/[threadId]/messages/route";
import { POST as proposeCandidate } from "../../app/api/demo/messages/[messageId]/memory-candidates/route";
import { GET as candidates } from "../../app/api/demo/cases/[caseId]/memory-candidates/route";
import { POST as verifyCandidate } from "../../app/api/demo/memory-candidates/[candidateId]/verification-decisions/route";
import { GET as confirmedFacts } from "../../app/api/demo/cases/[caseId]/confirmed-facts/route";
import { GET as skillInspector } from "../../app/api/demo/cases/[caseId]/planning-skill-inspector/route";

const ID = "40000000-0000-0000-0000-000000000002";
const original = { ...process.env };
beforeAll(() => { process.env.NIGHT_VOYAGER_API_INTERNAL_URL = "http://api:8000"; process.env.NIGHT_VOYAGER_PUBLIC_ORIGIN = "http://127.0.0.1:3000"; });
afterAll(() => { process.env = original; });
beforeEach(() => vi.unstubAllGlobals());

const cases = [
  ["bootstrap", "GET", bootstrap, "/api/v1/demo/session-bootstrap", undefined],
  ["sessions", "POST", sessions, "/api/v1/demo/sessions", undefined],
  ["session", "DELETE", session, "/api/v1/demo/session", undefined],
  ["ledger", "GET", ledger, `/api/v1/cases/${ID}/advisor-ledger`, { caseId: ID }],
  ["tasks", "POST", tasks, `/api/v1/cases/${ID}/agent-tasks`, { caseId: ID }],
  ["task", "GET", task, `/api/v1/tasks/${ID}`, { taskId: ID }],
  ["cancel", "POST", cancel, `/api/v1/tasks/${ID}/cancel`, { taskId: ID }],
  ["events", "GET", events, `/api/v1/tasks/${ID}/events`, { taskId: ID }],
  ["review", "POST", review, `/api/v1/cases/${ID}/advisor-reviews`, { caseId: ID }],
  ["brief", "GET", currentBrief, `/api/v1/cases/${ID}/current-decision-brief`, { caseId: ID }],
  ["decide", "POST", decide, `/api/v1/decision-briefs/${ID}/family-decisions`, { briefId: ID }],
  ["collaboration-thread", "GET", collaborationThread, `/api/v1/cases/${ID}/collaboration-thread`, { caseId: ID }],
  ["collaboration-messages", "GET", collaborationMessages, `/api/v1/collaboration-threads/${ID}/messages`, { threadId: ID }],
  ["append-message", "POST", appendMessage, `/api/v1/collaboration-threads/${ID}/messages`, { threadId: ID }],
  ["propose-candidate", "POST", proposeCandidate, `/api/v1/messages/${ID}/memory-candidates`, { messageId: ID }],
  ["candidates", "GET", candidates, `/api/v1/cases/${ID}/memory-candidates`, { caseId: ID }],
  ["verify-candidate", "POST", verifyCandidate, `/api/v1/memory-candidates/${ID}/verification-decisions`, { candidateId: ID }],
  ["confirmed-facts", "GET", confirmedFacts, `/api/v1/cases/${ID}/confirmed-facts`, { caseId: ID }],
  ["skill-inspector", "GET", skillInspector, `/api/v1/cases/${ID}/planning-skill-inspector`, { caseId: ID }],
] as const;

it.each(cases)("maps explicit %s handler to fixed method/path", async (_name, method, handler, upstreamPath, params) => {
  const fetchMock = vi.fn(async (url: string, init: RequestInit) => {
    expect(url).toBe(`http://api:8000${upstreamPath}`);
    expect(init.method).toBe(method);
    return new Response(method === "GET" && upstreamPath.endsWith("/events") ? "" : "{}", { headers: { "Content-Type": upstreamPath.endsWith("/events") ? "text/event-stream" : "application/json" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  const headers: Record<string, string> = {};
  if (method !== "GET") headers.Origin = "http://127.0.0.1:3000";
  if (method === "POST") headers["Content-Type"] = "application/json";
  const body = _name === "verify-candidate"
    ? JSON.stringify({ schema_version: 1, expected_case_revision: 1, decision: "confirm", reason: "Confirmed." })
    : "{}";
  const init: RequestInit = { method, headers, ...(method === "POST" ? { body } : {}) };
  const request = _name === "bootstrap" ? new NextRequest("http://127.0.0.1:3000/api/demo/session-bootstrap") : new Request("http://127.0.0.1:3000/api", init);
  const response = params
    ? await (handler as (request: Request, context: { params: Promise<Record<string, string>> }) => Promise<Response>)(request, { params: Promise.resolve(params) })
    : await (handler as (request: Request) => Promise<Response> | Response)(request);
  expect(response.status).toBe(200);
  expect(fetchMock).toHaveBeenCalledOnce();
});

it("canonicalizes only approved message pagination parameters", async () => {
  const urls: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string) => { urls.push(url); return Response.json({ schema_version: 1, items: [], next_after_sequence: null }); }));
  const context = { params: Promise.resolve({ threadId: ID }) };
  const accepted = await collaborationMessages(new Request("http://127.0.0.1:3000/api/demo/messages?limit=10&after_sequence=2"), context);
  expect(accepted.status).toBe(200);
  expect(urls).toEqual([`http://api:8000/api/v1/collaboration-threads/${ID}/messages?after_sequence=2&limit=10`]);
  for (const query of ["?limit=0", "?limit=101", "?after_sequence=-1", "?limit=10&limit=11", "?debug=1"]) {
    expect((await collaborationMessages(new Request(`http://127.0.0.1:3000/api/demo/messages${query}`), context)).status).toBe(400);
  }
  expect(urls).toHaveLength(1);
});

it("rejects non-exact verification bodies before upstream", async () => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  const response = await verifyCandidate(new Request("http://127.0.0.1:3000/api", {
    method: "POST",
    headers: { Origin: "http://127.0.0.1:3000", "Content-Type": "application/json", "X-CSRF-Token": "csrf", "Idempotency-Key": ID },
    body: JSON.stringify({ schema_version: 1, expected_case_revision: 1, decision: "confirm", reason: "Confirmed.", actor_id: ID }),
  }), { params: Promise.resolve({ candidateId: ID }) });
  expect(response.status).toBe(400);
  expect(fetchMock).not.toHaveBeenCalled();
});

it("blocks residual bootstrap cookies before upstream and forwards fixed Origin without inbound Origin", async () => {
  const fetchMock = vi.fn(async (_url: string, init: RequestInit) => {
    expect(new Headers(init.headers).get("Origin")).toBe("http://127.0.0.1:3000");
    return Response.json({ csrf_token: "csrf" });
  });
  vi.stubGlobal("fetch", fetchMock);
  const clean = await bootstrap(new NextRequest("http://127.0.0.1:3000/api/demo/session-bootstrap"));
  expect(clean.status).toBe(200);
  const residual = await bootstrap(new NextRequest("http://127.0.0.1:3000/api/demo/session-bootstrap", { headers: { Cookie: "night_voyager_session=opaque" } }));
  expect(residual.status).toBe(409);
  expect((await residual.json()).code).toBe("bff_session_recovery_required");
  expect(fetchMock).toHaveBeenCalledTimes(1);
});
