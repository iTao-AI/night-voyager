import { demoBffProblem } from "../../../../../../lib/demo-bff/problem";
import { forwardDemoJson, requireCanonicalUuid } from "../../../../../../lib/demo-bff/transport";

export const dynamic = "force-dynamic";
function exactVerification(value: unknown): boolean {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const body = value as Record<string, unknown>;
  const keys = Object.keys(body).sort().join(",");
  return keys === "decision,expected_case_revision,reason,schema_version" && body.schema_version === 1 && Number.isSafeInteger(body.expected_case_revision) && Number(body.expected_case_revision) > 0 && (body.decision === "confirm" || body.decision === "reject") && typeof body.reason === "string" && new TextEncoder().encode(body.reason).byteLength >= 1 && new TextEncoder().encode(body.reason).byteLength <= 512;
}
export async function POST(request: Request, { params }: { params: Promise<{ candidateId: string }> }) {
  try {
    if (new URL(request.url).search) throw new Error("unexpected query");
    const { candidateId } = await params;
    return forwardDemoJson(request, { method: "POST", upstreamPath: `/api/v1/memory-candidates/${requireCanonicalUuid(candidateId)}/verification-decisions`, mutation: true, validateBody: exactVerification });
  } catch { return demoBffProblem(400, "bff_invalid_request", "invalid request"); }
}
