import { loadDemoBffConfig, type DemoBffConfig } from "./config";
import { demoBffProblem } from "./problem";

export interface DemoRoute {
  method: "GET" | "POST" | "DELETE";
  upstreamPath: string;
  mutation: boolean;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export function requireCanonicalUuid(value: string): string {
  if (!UUID.test(value)) throw new Error("invalid UUID");
  return value;
}

async function readBoundedBody(
  request: Request,
  maxBytes: number,
): Promise<Uint8Array | Response | undefined> {
  if (request.method === "GET" || request.method === "DELETE") return undefined;
  const contentType = request.headers.get("Content-Type")?.split(";", 1)[0];
  if (contentType !== "application/json") {
    return demoBffProblem(415, "bff_unsupported_media_type", "unsupported media type");
  }
  if (!request.body) return new Uint8Array();
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
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
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  try {
    JSON.parse(new TextDecoder().decode(body));
  } catch {
    return demoBffProblem(400, "bff_invalid_request", "invalid request");
  }
  return body;
}

function upstreamHeaders(request: Request, config: DemoBffConfig): Headers {
  const headers = new Headers({ Origin: config.publicOrigin });
  for (const name of [
    "Cookie",
    "Content-Type",
    "X-CSRF-Token",
    "Idempotency-Key",
    "Last-Event-ID",
  ]) {
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
  const body = await readBoundedBody(request, config.maxJsonBytes);
  if (body instanceof Response) return body;
  const controller = new AbortController();
  const abort = () => controller.abort();
  request.signal.addEventListener("abort", abort, { once: true });
  const timer = setTimeout(abort, config.jsonTimeoutMs);
  try {
    const upstream = await fetch(`${config.apiOrigin}${route.upstreamPath}`, {
      method: route.method,
      headers: upstreamHeaders(request, config),
      body: body === undefined ? undefined : new TextDecoder().decode(body),
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
  const headers = upstreamHeaders(request, config);
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
