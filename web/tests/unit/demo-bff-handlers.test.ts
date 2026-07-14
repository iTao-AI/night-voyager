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
  const init: RequestInit = { method, headers, ...(method === "POST" ? { body: "{}" } : {}) };
  const request = _name === "bootstrap" ? new NextRequest("http://127.0.0.1:3000/api/demo/session-bootstrap") : new Request("http://127.0.0.1:3000/api", init);
  const response = params
    ? await (handler as (request: Request, context: { params: Promise<Record<string, string>> }) => Promise<Response>)(request, { params: Promise.resolve(params) })
    : await (handler as (request: Request) => Promise<Response> | Response)(request);
  expect(response.status).toBe(200);
  expect(fetchMock).toHaveBeenCalledOnce();
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
