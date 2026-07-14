import { demoBffProblem } from "../../../../../lib/demo-bff/problem";
import { forwardDemoJson, requireCanonicalUuid } from "../../../../../lib/demo-bff/transport";

export const dynamic = "force-dynamic";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ taskId: string }> },
) {
  try {
    const { taskId } = await params;
    return forwardDemoJson(request, {
      method: "GET",
      upstreamPath: `/api/v1/tasks/${requireCanonicalUuid(taskId)}`,
      mutation: false,
    });
  } catch {
    return demoBffProblem(400, "bff_invalid_request", "invalid request");
  }
}
