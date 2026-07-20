import { loadDemoBffConfig, type DemoBffConfig } from "./config";
import { demoBffProblem } from "./problem";

export interface DemoRoute {
  method: "GET" | "POST" | "DELETE";
  upstreamPath: string;
  mutation: boolean;
  validateBody?: (value: unknown) => boolean;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export function requireCanonicalUuid(value: string): string {
  if (!UUID.test(value)) throw new Error("invalid UUID");
  return value;
}

async function readBoundedBody(
  request: Request,
  maxBytes: number,
  signal: AbortSignal,
): Promise<Uint8Array | Response | undefined> {
  if (request.method === "GET" || request.method === "DELETE") return undefined;
  const contentType = request.headers.get("Content-Type")?.split(";", 1)[0];
  if (contentType !== "application/json") {
    return demoBffProblem(415, "bff_unsupported_media_type", "unsupported media type");
  }
  if (!request.body) return new Uint8Array();
  const reader = request.body.getReader();
  const cancel = () => { void reader.cancel("request aborted"); };
  signal.addEventListener("abort", cancel, { once: true });
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    for (;;) {
      if (signal.aborted) throw new DOMException("aborted", "AbortError");
      const { done, value } = await reader.read();
      if (signal.aborted) throw new DOMException("aborted", "AbortError");
      if (done) break;
      size += value.byteLength;
      if (size > maxBytes) {
        await reader.cancel();
        return demoBffProblem(413, "bff_request_too_large", "request body too large");
      }
      chunks.push(value);
    }
    const body = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.byteLength; }
    try { JSON.parse(new TextDecoder().decode(body)); }
    catch { return demoBffProblem(400, "bff_invalid_request", "invalid request"); }
    return body;
  } finally {
    signal.removeEventListener("abort", cancel);
  }
}

function jsonHeaders(request: Request, config: DemoBffConfig, mutation: boolean): Headers {
  const headers = new Headers({ Origin: config.publicOrigin });
  for (const name of ["Cookie", ...(mutation ? ["Content-Type", "X-CSRF-Token", "Idempotency-Key"] : [])]) {
    const value = request.headers.get(name);
    if (value !== null) headers.set(name, value);
  }
  return headers;
}

function sseHeaders(request: Request, config: DemoBffConfig): Headers {
  const headers = new Headers({ Origin: config.publicOrigin });
  for (const name of ["Cookie", "Last-Event-ID"]) {
    const value = request.headers.get(name);
    if (value !== null) headers.set(name, value);
  }
  return headers;
}

function responseHeaders(upstream: Response, sse: boolean): Headers {
  const headers = new Headers({ "Cache-Control": "no-store" });
  for (const name of ["Content-Type", ...(sse ? ["X-Accel-Buffering"] : [])]) {
    const value = upstream.headers.get(name);
    if (value !== null) headers.set(name, value);
  }
  for (const cookie of upstream.headers.getSetCookie()) {
    headers.append("Set-Cookie", cookie);
  }
  return headers;
}

function validateOrigin(request: Request, config: DemoBffConfig): Response | undefined {
  if (request.headers.get("Origin") !== config.publicOrigin) {
    return demoBffProblem(403, "bff_origin_rejected", "request origin rejected");
  }
  return undefined;
}

export async function forwardDemoJson(
  request: Request,
  route: DemoRoute,
  config: DemoBffConfig = loadDemoBffConfig(),
): Promise<Response> {
  if (route.mutation) {
    const rejected = validateOrigin(request, config);
    if (rejected) return rejected;
  }
  const controller = new AbortController();
  const abort = () => controller.abort();
  request.signal.addEventListener("abort", abort, { once: true });
  const timer = setTimeout(abort, config.jsonTimeoutMs);
  try {
    const body = await readBoundedBody(request, config.maxJsonBytes, controller.signal);
    if (body instanceof Response) return body;
    if (route.validateBody) {
      if (!body) return demoBffProblem(400, "bff_invalid_request", "invalid request");
      const parsed = JSON.parse(new TextDecoder().decode(body)) as unknown;
      if (!route.validateBody(parsed)) return demoBffProblem(400, "bff_invalid_request", "invalid request");
    }
    const upstream = await fetch(`${config.apiOrigin}${route.upstreamPath}`, {
      method: route.method,
      headers: jsonHeaders(request, config, route.mutation),
      body: body ? body.buffer.slice(body.byteOffset, body.byteOffset + body.byteLength) as ArrayBuffer : undefined,
      signal: controller.signal,
    });
    return new Response(upstream.body, {
      status: upstream.status,
      headers: responseHeaders(upstream, false),
    });
  } catch {
    if (controller.signal.aborted && !request.signal.aborted) {
      return demoBffProblem(504, "bff_upstream_timeout", "upstream request timed out");
    }
    return demoBffProblem(503, "bff_upstream_unavailable", "upstream unavailable");
  } finally {
    clearTimeout(timer);
    request.signal.removeEventListener("abort", abort);
  }
}

export async function forwardDemoSse(
  request: Request,
  route: DemoRoute,
  config: DemoBffConfig = loadDemoBffConfig(),
): Promise<Response> {
  const headers = sseHeaders(request, config);
  if (!headers.has("Last-Event-ID")) {
    const after = new URL(request.url).searchParams.get("after");
    if (after !== null) {
      if (!/^\d+$/.test(after)) {
        return demoBffProblem(400, "bff_invalid_request", "invalid request");
      }
      headers.set("Last-Event-ID", after);
    }
  }
  try {
    const upstream = await fetch(`${config.apiOrigin}${route.upstreamPath}`, {
      method: route.method,
      headers,
      signal: request.signal,
    });
    return new Response(upstream.body, {
      status: upstream.status,
      headers: responseHeaders(upstream, true),
    });
  } catch {
    return demoBffProblem(503, "bff_upstream_unavailable", "upstream unavailable");
  }
}
