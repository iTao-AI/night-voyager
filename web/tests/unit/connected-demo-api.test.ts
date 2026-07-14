// @vitest-environment node
import { afterEach, expect, it, vi } from "vitest";

import { createConnectedDemoApi } from "../../lib/connected-demo/api";
import { requestFingerprint } from "../../lib/connected-demo/idempotency";

afterEach(() => vi.unstubAllGlobals());

it("uses only same-origin explicit routes and closed schema guards", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    expect(String(input)).toBe("/api/demo/session-bootstrap");
    return Response.json({ csrf_token: "csrf", extra: "forbidden" });
  });
  vi.stubGlobal("fetch", fetchMock);
  await expect(createConnectedDemoApi().bootstrap()).rejects.toThrow("invalid response");
});

it("fingerprints canonical requests without storing their body", async () => {
  const first = await requestFingerprint({ b: 2, a: 1 });
  const second = await requestFingerprint({ a: 1, b: 2 });
  expect(first).toBe(second);
  expect(first).toMatch(/^[0-9a-f]{64}$/);
});
