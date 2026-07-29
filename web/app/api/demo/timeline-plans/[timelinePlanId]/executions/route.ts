import { demoBffProblem } from "../../../../../../lib/demo-bff/problem";
import { forwardDemoJson, requireCanonicalUuid } from "../../../../../../lib/demo-bff/transport";

export const dynamic = "force-dynamic";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

function exactStart(value: unknown): boolean {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const body = value as Record<string, unknown>;
  return Object.keys(body).sort().join(",") === "case_id,expected_case_revision,schema_version"
    && body.schema_version === 1
    && typeof body.case_id === "string"
    && UUID.test(body.case_id)
    && Number.isSafeInteger(body.expected_case_revision)
    && Number(body.expected_case_revision) > 0;
}

export async function POST(request: Request, { params }: { params: Promise<{ timelinePlanId: string }> }) {
  try {
    if (new URL(request.url).search) throw new Error("unexpected query");
    const { timelinePlanId } = await params;
    return forwardDemoJson(request, {
      method: "POST",
      upstreamPath: `/api/v1/timeline-plans/${requireCanonicalUuid(timelinePlanId)}/executions`,
      mutation: true,
      validateBody: exactStart,
    });
  } catch {
    return demoBffProblem(400, "bff_invalid_request", "invalid request");
  }
}
