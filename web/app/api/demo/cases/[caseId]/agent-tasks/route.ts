import { demoBffProblem } from "../../../../../../lib/demo-bff/problem";
import { forwardDemoJson, requireCanonicalUuid } from "../../../../../../lib/demo-bff/transport";

export const dynamic = "force-dynamic";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ caseId: string }> },
) {
  try {
    const { caseId } = await params;
    return forwardDemoJson(request, {
      method: "POST",
      upstreamPath: `/api/v1/cases/${requireCanonicalUuid(caseId)}/agent-tasks`,
      mutation: true,
    });
  } catch {
    return demoBffProblem(400, "bff_invalid_request", "invalid request");
  }
}
