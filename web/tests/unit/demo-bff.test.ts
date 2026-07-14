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

  it.each([
    ["session create", 201],
    ["successful delete", 204],
    ["stale cleanup", 401],
  ])("round-trips separate Set-Cookie fields for %s", async (_name, status) => {
    const headers = new Headers();
    headers.append("Set-Cookie", "night_voyager_session=opaque; Path=/; HttpOnly");
    headers.append("Set-Cookie", "night_voyager_csrf_bootstrap=; Max-Age=0; Path=/");
    vi.stubGlobal("fetch", vi.fn(async () => new Response(status === 204 ? null : "{}", { status, headers })));
    const response = await forwardDemoJson(
      new Request("http://127.0.0.1/api", { method: "DELETE", headers: { Origin: env.NIGHT_VOYAGER_PUBLIC_ORIGIN } }),
      { method: "DELETE", upstreamPath: "/api/v1/demo/session", mutation: true },
      loadDemoBffConfig(env),
    );
    expect(response.headers.getSetCookie()).toEqual(headers.getSetCookie());
    expect(response.headers.get("Set-Cookie")).toContain("night_voyager_session");
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

  it.each([
    ["malformed JSON", "application/json", "{", 400, "bff_invalid_request"],
    ["unsupported media", "text/plain", "{}", 415, "bff_unsupported_media_type"],
  ])("rejects %s before upstream", async (_name, contentType, body, status, code) => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const response = await forwardDemoJson(
      new Request("http://127.0.0.1/api", { method: "POST", headers: { Origin: env.NIGHT_VOYAGER_PUBLIC_ORIGIN, "Content-Type": contentType }, body }),
      { method: "POST", upstreamPath: "/api/v1/demo/sessions", mutation: true },
      loadDemoBffConfig(env),
    );
    expect(response.status).toBe(status);
    expect((await response.json()).code).toBe(code);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("applies one deadline across body read and fetch and cancels an unclosed reader", async () => {
    let cancelled = false;
    const body = new ReadableStream<Uint8Array>({
      start(controller) { controller.enqueue(new TextEncoder().encode("{")); },
      cancel() { cancelled = true; },
    });
    const response = await forwardDemoJson(
      new Request("http://127.0.0.1/api", { method: "POST", headers: { Origin: env.NIGHT_VOYAGER_PUBLIC_ORIGIN, "Content-Type": "application/json" }, body, duplex: "half" } as RequestInit),
      { method: "POST", upstreamPath: "/api/v1/demo/sessions", mutation: true },
      { ...loadDemoBffConfig(env), jsonTimeoutMs: 5 },
    );
    expect(response.status).toBe(504);
    expect((await response.json()).code).toBe("bff_upstream_timeout");
    expect(cancelled).toBe(true);
  });

  it("forwards only request/response allowlists", async () => {
    vi.stubGlobal("fetch", vi.fn(async (_url: string, init: RequestInit) => {
      const headers = new Headers(init.headers);
      expect(headers.get("Cookie")).toBe("night_voyager_session=opaque");
      expect(headers.get("X-Private-Debug")).toBeNull();
      return new Response("{}", { headers: { "Content-Type": "application/json", Server: "hidden", "X-Trace": "hidden" } });
    }));
    const response = await forwardDemoJson(
      new Request("http://127.0.0.1/api", { headers: { Cookie: "night_voyager_session=opaque", "X-Private-Debug": "secret" } }),
      { method: "GET", upstreamPath: "/api/v1/tasks/40000000-0000-0000-0000-000000000002", mutation: false },
      loadDemoBffConfig(env),
    );
    expect(response.headers.get("Server")).toBeNull();
    expect(response.headers.get("X-Trace")).toBeNull();
    expect(response.headers.get("Cache-Control")).toBe("no-store");
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

  it("prefers inbound Last-Event-ID and rejects invalid initial cursors", async () => {
    const fetchMock = vi.fn(async (_url: string, init: RequestInit) => {
      expect(new Headers(init.headers).get("Last-Event-ID")).toBe("11");
      return new Response("", { headers: { "Content-Type": "text/event-stream" } });
    });
    vi.stubGlobal("fetch", fetchMock);
    await forwardDemoSse(new Request("http://127.0.0.1/api?after=7", { headers: { "Last-Event-ID": "11" } }), { method: "GET", upstreamPath: "/api/v1/tasks/40000000-0000-0000-0000-000000000002/events", mutation: false }, loadDemoBffConfig(env));
    const invalid = await forwardDemoSse(new Request("http://127.0.0.1/api?after=-1"), { method: "GET", upstreamPath: "/api/v1/tasks/40000000-0000-0000-0000-000000000002/events", mutation: false }, loadDemoBffConfig(env));
    expect(invalid.status).toBe(400);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
