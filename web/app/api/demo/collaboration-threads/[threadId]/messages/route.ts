import { demoBffProblem } from "../../../../../../lib/demo-bff/problem";
import { forwardDemoJson, requireCanonicalUuid } from "../../../../../../lib/demo-bff/transport";

export const dynamic = "force-dynamic";

function canonicalMessagesQuery(request: Request): string {
  const params = new URL(request.url).searchParams;
  for (const key of params.keys()) if (key !== "after_sequence" && key !== "limit") throw new Error("unexpected query");
  for (const key of ["after_sequence", "limit"]) if (params.getAll(key).length > 1) throw new Error("repeated query");
  const after = params.get("after_sequence");
  const limit = params.get("limit");
  if (after !== null && (!/^\d+$/.test(after) || !Number.isSafeInteger(Number(after)))) throw new Error("invalid cursor");
  if (limit !== null && (!/^\d+$/.test(limit) || Number(limit) < 1 || Number(limit) > 100)) throw new Error("invalid limit");
  const canonical = new URLSearchParams();
  if (after !== null) canonical.set("after_sequence", String(Number(after)));
  if (limit !== null) canonical.set("limit", String(Number(limit)));
  const encoded = canonical.toString();
  return encoded ? `?${encoded}` : "";
}

export async function GET(request: Request, { params }: { params: Promise<{ threadId: string }> }) {
  try {
    const { threadId } = await params;
    return forwardDemoJson(request, { method: "GET", upstreamPath: `/api/v1/collaboration-threads/${requireCanonicalUuid(threadId)}/messages${canonicalMessagesQuery(request)}`, mutation: false });
  } catch { return demoBffProblem(400, "bff_invalid_request", "invalid request"); }
}

export async function POST(request: Request, { params }: { params: Promise<{ threadId: string }> }) {
  try {
    if (new URL(request.url).search) throw new Error("unexpected query");
    const { threadId } = await params;
    return forwardDemoJson(request, { method: "POST", upstreamPath: `/api/v1/collaboration-threads/${requireCanonicalUuid(threadId)}/messages`, mutation: true });
  } catch { return demoBffProblem(400, "bff_invalid_request", "invalid request"); }
}
