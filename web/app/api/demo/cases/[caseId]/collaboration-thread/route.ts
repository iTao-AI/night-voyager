import { demoBffProblem } from "../../../../../../lib/demo-bff/problem";
import { forwardDemoJson, requireCanonicalUuid } from "../../../../../../lib/demo-bff/transport";

export const dynamic = "force-dynamic";

export async function GET(request: Request, { params }: { params: Promise<{ caseId: string }> }) {
  try {
    if (new URL(request.url).search) throw new Error("unexpected query");
    const { caseId } = await params;
    return forwardDemoJson(request, { method: "GET", upstreamPath: `/api/v1/cases/${requireCanonicalUuid(caseId)}/collaboration-thread`, mutation: false });
  } catch { return demoBffProblem(400, "bff_invalid_request", "invalid request"); }
}
