import type { NextRequest } from "next/server";

import { demoBffProblem } from "../../../../lib/demo-bff/problem";
import { forwardDemoJson } from "../../../../lib/demo-bff/transport";

export const dynamic = "force-dynamic";

export function GET(request: NextRequest) {
  if (request.cookies.has("night_voyager_session")) {
    return demoBffProblem(
      409,
      "bff_session_recovery_required",
      "session recovery required",
    );
  }
  return forwardDemoJson(request, {
    method: "GET",
    upstreamPath: "/api/v1/demo/session-bootstrap",
    mutation: false,
  });
}
