import { demoBffProblem } from "../../../../../../lib/demo-bff/problem";
import { forwardDemoJson, requireCanonicalUuid } from "../../../../../../lib/demo-bff/transport";

export const dynamic = "force-dynamic";
export async function POST(request: Request, { params }: { params: Promise<{ messageId: string }> }) {
  try {
    if (new URL(request.url).search) throw new Error("unexpected query");
    const { messageId } = await params;
    return forwardDemoJson(request, { method: "POST", upstreamPath: `/api/v1/messages/${requireCanonicalUuid(messageId)}/memory-candidates`, mutation: true });
  } catch { return demoBffProblem(400, "bff_invalid_request", "invalid request"); }
}
