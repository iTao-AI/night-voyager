import { demoBffProblem } from "../../../../../../lib/demo-bff/problem";
import { forwardDemoJson, requireCanonicalUuid } from "../../../../../../lib/demo-bff/transport";

export const dynamic = "force-dynamic";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const CODES = ["documents_status_confirmed", "application_status_confirmed", "visa_status_confirmed", "arrival_status_confirmed"];

function exactAttestation(value: unknown): boolean {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const body = value as Record<string, unknown>;
  return Object.keys(body).sort().join(",") === "attestation_code,attestation_kind,case_id,checkpoint_id,expected_checkpoint_version,expected_execution_version,reason_code,schema_version,status_code"
    && body.schema_version === 1
    && typeof body.case_id === "string"
    && UUID.test(body.case_id)
    && typeof body.checkpoint_id === "string"
    && UUID.test(body.checkpoint_id)
    && Number.isSafeInteger(body.expected_execution_version)
    && Number(body.expected_execution_version) > 0
    && Number.isSafeInteger(body.expected_checkpoint_version)
    && Number(body.expected_checkpoint_version) > 0
    && ["progress", "completion", "blocked"].includes(String(body.attestation_kind))
    && ["work_in_progress", "ready_for_advisor", "work_blocked"].includes(String(body.status_code))
    && CODES.includes(String(body.attestation_code))
    && ["not_applicable", "missing_required_input", "external_dependency_unavailable", "deadline_at_risk"].includes(String(body.reason_code));
}

export async function POST(request: Request, { params }: { params: Promise<{ executionId: string }> }) {
  try {
    if (new URL(request.url).search) throw new Error("unexpected query");
    const { executionId } = await params;
    return forwardDemoJson(request, {
      method: "POST",
      upstreamPath: `/api/v1/timeline-executions/${requireCanonicalUuid(executionId)}/checkpoint-attestations`,
      mutation: true,
      validateBody: exactAttestation,
    });
  } catch {
    return demoBffProblem(400, "bff_invalid_request", "invalid request");
  }
}
