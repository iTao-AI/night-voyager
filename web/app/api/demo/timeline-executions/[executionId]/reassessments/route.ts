import { demoBffProblem } from "../../../../../../lib/demo-bff/problem";
import { forwardDemoJson, requireCanonicalUuid } from "../../../../../../lib/demo-bff/transport";

export const dynamic = "force-dynamic";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

function exactReassessment(value: unknown): boolean {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const body = value as Record<string, unknown>;
  return Object.keys(body).sort().join(",") === "case_id,checkpoint_id,expected_checkpoint_version,expected_execution_version,schema_version,trigger,trigger_reference_id"
    && body.schema_version === 1
    && typeof body.case_id === "string"
    && UUID.test(body.case_id)
    && typeof body.checkpoint_id === "string"
    && UUID.test(body.checkpoint_id)
    && Number.isSafeInteger(body.expected_execution_version)
    && Number(body.expected_execution_version) > 0
    && Number.isSafeInteger(body.expected_checkpoint_version)
    && Number(body.expected_checkpoint_version) > 0
    && ((body.trigger === "blocked_attestation"
      && typeof body.trigger_reference_id === "string"
      && UUID.test(body.trigger_reference_id))
      || (body.trigger === "deadline_elapsed" && body.trigger_reference_id === null));
}

export async function POST(request: Request, { params }: { params: Promise<{ executionId: string }> }) {
  try {
    if (new URL(request.url).search) throw new Error("unexpected query");
    const { executionId } = await params;
    return forwardDemoJson(request, {
      method: "POST",
      upstreamPath: `/api/v1/timeline-executions/${requireCanonicalUuid(executionId)}/reassessments`,
      mutation: true,
      validateBody: exactReassessment,
    });
  } catch {
    return demoBffProblem(400, "bff_invalid_request", "invalid request");
  }
}
