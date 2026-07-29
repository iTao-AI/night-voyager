import type { NextRequest } from "next/server";

import { demoBffProblem } from "../../../../lib/demo-bff/problem";
import { forwardDemoJson } from "../../../../lib/demo-bff/transport";

export const dynamic = "force-dynamic";

export function GET(request: NextRequest) {
  if (request.cookies.has("night_voyager_session")) {
    const response = demoBffProblem(
      409,
      "bff_session_recovery_required",
      "session recovery required",
    );
    response.headers.append(
      "Set-Cookie",
      "night_voyager_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax",
    );
    response.headers.append(
      "Set-Cookie",
      "night_voyager_csrf_bootstrap=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax",
    );
    return response;
  }
  return forwardDemoJson(request, {
    method: "GET",
    upstreamPath: "/api/v1/demo/session-bootstrap",
    mutation: false,
  });
}
