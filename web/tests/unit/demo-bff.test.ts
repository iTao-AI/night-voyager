// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";

import { loadDemoBffConfig } from "../../lib/demo-bff/config";
import {
  forwardDemoJson,
  forwardDemoSse,
  requireCanonicalUuid,
} from "../../lib/demo-bff/transport";

const env = {
  NIGHT_VOYAGER_API_INTERNAL_URL: "http://api:8000",
  NIGHT_VOYAGER_PUBLIC_ORIGIN: "http://127.0.0.1:3000",
};

afterEach(() => vi.unstubAllGlobals());

describe("demo BFF transport", () => {
  it("loads only canonical server-owned origins", () => {
    expect(loadDemoBffConfig(env)).toEqual({
      apiOrigin: "http://api:8000",
      publicOrigin: "http://127.0.0.1:3000",
      jsonTimeoutMs: 10_000,
      maxJsonBytes: 32 * 1024,
    });
    expect(() =>
      loadDemoBffConfig({ ...env, NIGHT_VOYAGER_API_INTERNAL_URL: "file:///tmp/api" }),
    ).toThrow("invalid internal API origin");
  });

  it("rejects non-canonical UUIDs before fetch", () => {
    expect(() => requireCanonicalUuid("not-a-uuid")).toThrow("invalid UUID");
    expect(requireCanonicalUuid("40000000-0000-0000-0000-000000000002")).toBe(
      "40000000-0000-0000-0000-000000000002",
    );
  });

  it("uses fixed Origin and preserves upstream problems and cookies", async () => {
    const headers = new Headers({
      "Content-Type": "application/problem+json",
      "Cache-Control": "no-store",
    });
    headers.append("Set-Cookie", "night_voyager_session=a; Path=/; HttpOnly");
    headers.append("Set-Cookie", "night_voyager_csrf_bootstrap=; Max-Age=0; Path=/");
    const fetchMock = vi.fn(async (_url: string, init: RequestInit) => {
      expect(new Headers(init.headers).get("Origin")).toBe("http://127.0.0.1:3000");
      return new Response('{"code":"request_rejected"}', { status: 403, headers });
    });
    vi.stubGlobal("fetch", fetchMock);
    const response = await forwardDemoJson(
      new Request("http://127.0.0.1:3000/api/demo/sessions", {
        method: "POST",
        headers: {
          Origin: "http://127.0.0.1:3000",
          "Content-Type": "application/json",
        },
        body: "{}",
      }),
      { method: "POST", upstreamPath: "/api/v1/demo/sessions", mutation: true },
      loadDemoBffConfig(env),
    );
    expect(response.status).toBe(403);
    expect(await response.json()).toEqual({ code: "request_rejected" });
    expect(response.headers.getSetCookie()).toEqual(headers.getSetCookie());
  });

  it("rejects caller Origin mismatch and oversize JSON locally", async () => {
    const config = loadDemoBffConfig(env);
    const origin = await forwardDemoJson(
      new Request("http://127.0.0.1/api", {
        method: "POST",
        headers: { Origin: "https://evil.invalid", "Content-Type": "application/json" },
        body: "{}",
      }),
      { method: "POST", upstreamPath: "/api/v1/demo/sessions", mutation: true },
      config,
    );
    expect(origin.status).toBe(403);
    expect((await origin.json()).code).toBe("bff_origin_rejected");

    const large = await forwardDemoJson(
      new Request("http://127.0.0.1/api", {
        method: "POST",
        headers: {
          Origin: config.publicOrigin,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ data: "x".repeat(config.maxJsonBytes) }),
      }),
      { method: "POST", upstreamPath: "/api/v1/demo/sessions", mutation: true },
      config,
    );
    expect(large.status).toBe(413);
    expect((await large.json()).code).toBe("bff_request_too_large");
  });

  it("returns the SSE body directly and maps cursor precedence", async () => {
    const bytes = new TextEncoder().encode("id: 2\ndata: {}\n\n");
    const body = new ReadableStream({ start(controller) { controller.enqueue(bytes); controller.close(); } });
    const fetchMock = vi.fn(async (_url: string, init: RequestInit) => {
      expect(new Headers(init.headers).get("Last-Event-ID")).toBe("7");
      return new Response(body, {
        headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-store" },
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    const response = await forwardDemoSse(
      new Request("http://127.0.0.1/api?after=7"),
      { method: "GET", upstreamPath: "/api/v1/tasks/40000000-0000-0000-0000-000000000002/events", mutation: false },
      loadDemoBffConfig(env),
    );
    expect(new Uint8Array(await response.arrayBuffer())).toEqual(bytes);
  });
});
