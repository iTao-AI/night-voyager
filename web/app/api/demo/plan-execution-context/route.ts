import { demoBffProblem } from "../../../../lib/demo-bff/problem";
import { forwardDemoJson } from "../../../../lib/demo-bff/transport";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    if (new URL(request.url).search) throw new Error("unexpected query");
    return forwardDemoJson(request, {
      method: "GET",
      upstreamPath: "/api/v1/plan-execution-context?scenario=governed-plan-execution-v1",
      mutation: false,
    });
  } catch {
    return demoBffProblem(400, "bff_invalid_request", "invalid request");
  }
}
