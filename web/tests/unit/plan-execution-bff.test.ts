// @vitest-environment node
import { afterAll, beforeAll, beforeEach, expect, it, vi } from "vitest";

import { GET as context } from "../../app/api/demo/plan-execution-context/route";
import { POST as start } from "../../app/api/demo/timeline-plans/[timelinePlanId]/executions/route";
import { GET as execution } from "../../app/api/demo/cases/[caseId]/timeline-execution/route";
import { POST as attest } from "../../app/api/demo/timeline-executions/[executionId]/checkpoint-attestations/route";
import { POST as verify } from "../../app/api/demo/timeline-executions/[executionId]/checkpoint-verifications/route";
import { POST as reassess } from "../../app/api/demo/timeline-executions/[executionId]/reassessments/route";
import { createPlanExecutionApi } from "../../lib/plan-execution/api";

const ID = "94000000-0000-0000-0000-000000000001";
const origin = "http://127.0.0.1:3000";
const original = { ...process.env };
beforeAll(() => {
  process.env.NIGHT_VOYAGER_API_INTERNAL_URL = "http://api:8000";
  process.env.NIGHT_VOYAGER_PUBLIC_ORIGIN = origin;
});
afterAll(() => { process.env = original; });
beforeEach(() => vi.unstubAllGlobals());

const mutation = (body: object) => new Request(`${origin}/api`, {
  method: "POST",
  headers: {
    Origin: origin,
    "Content-Type": "application/json",
    "X-CSRF-Token": "csrf",
    "Idempotency-Key": ID,
    Cookie: "night_voyager_session=opaque",
  },
  body: JSON.stringify(body),
});

it("composes the plan execution client through the exact queryless BFF context path", async () => {
  const payload = {
    schema_version: 1,
    scenario: "governed-plan-execution-v1",
    case_id: ID,
    case_revision: 1,
    decision_id: ID,
    decision_receipt_id: ID,
    timeline_plan_id: ID,
    execution_id: null,
    active_role: "student",
    assignment_status: "assigned",
  };
  const fetchMock = vi.fn(async (url: string) => {
    expect(url).toBe("/api/demo/plan-execution-context");
    return Response.json(payload);
  });
  vi.stubGlobal("fetch", fetchMock);

  await expect(createPlanExecutionApi().context()).resolves.toEqual(payload);
  expect(fetchMock).toHaveBeenCalledOnce();
});

it("forwards only the fixed context scenario and rejects arbitrary query", async () => {
  const fetchMock = vi.fn(async (url: string) => {
    expect(url).toBe("http://api:8000/api/v1/plan-execution-context?scenario=governed-plan-execution-v1");
    return Response.json({});
  });
  vi.stubGlobal("fetch", fetchMock);
  expect((await context(new Request(`${origin}/api/demo/plan-execution-context`))).status).toBe(200);
  expect((await context(new Request(`${origin}/api/demo/plan-execution-context?case_id=${ID}`))).status).toBe(400);
  expect(fetchMock).toHaveBeenCalledOnce();
});

it("maps the five identity-scoped routes without authority derivation", async () => {
  const urls: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    urls.push(url);
    return Response.json({});
  }));
  const params = { params: Promise.resolve({ timelinePlanId: ID, executionId: ID, caseId: ID }) };
  expect((await start(mutation({ schema_version: 1, case_id: ID, expected_case_revision: 1 }), params)).status).toBe(200);
  expect((await execution(new Request(`${origin}/api`), params)).status).toBe(200);
  expect((await attest(mutation({
    schema_version: 1, case_id: ID, checkpoint_id: ID,
    expected_execution_version: 1, expected_checkpoint_version: 1,
    attestation_kind: "progress", status_code: "work_in_progress",
    attestation_code: "documents_status_confirmed", reason_code: "not_applicable",
  }), params)).status).toBe(200);
  expect((await verify(mutation({
    schema_version: 1, case_id: ID, checkpoint_id: ID, attestation_id: ID,
    expected_execution_version: 2, expected_checkpoint_version: 2,
    action: "verify", reason_code: "attestation_verified",
  }), params)).status).toBe(200);
  expect((await reassess(mutation({
    schema_version: 1, case_id: ID, checkpoint_id: ID,
    expected_execution_version: 2, expected_checkpoint_version: 2,
    trigger: "blocked_attestation", trigger_reference_id: ID,
  }), params)).status).toBe(200);
  expect(urls).toEqual([
    `http://api:8000/api/v1/timeline-plans/${ID}/executions`,
    `http://api:8000/api/v1/cases/${ID}/timeline-execution`,
    `http://api:8000/api/v1/timeline-executions/${ID}/checkpoint-attestations`,
    `http://api:8000/api/v1/timeline-executions/${ID}/checkpoint-verifications`,
    `http://api:8000/api/v1/timeline-executions/${ID}/reassessments`,
  ]);
});

it("rejects extra authority fields before upstream", async () => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  const response = await start(
    mutation({
      schema_version: 1,
      case_id: ID,
      expected_case_revision: 1,
      actor_id: ID,
    }),
    { params: Promise.resolve({ timelinePlanId: ID }) },
  );
  expect(response.status).toBe(400);
  expect(fetchMock).not.toHaveBeenCalled();
});

it("rejects invalid UUIDs and closed codes before upstream", async () => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  const response = await attest(mutation({
    schema_version: 1,
    case_id: "not-a-uuid",
    checkpoint_id: ID,
    expected_execution_version: 1,
    expected_checkpoint_version: 1,
    attestation_kind: "narrative",
    status_code: "anything",
    attestation_code: "documents_status_confirmed",
    reason_code: "not_applicable",
  }), { params: Promise.resolve({ executionId: ID }) });
  expect(response.status).toBe(400);
  expect(fetchMock).not.toHaveBeenCalled();
});
