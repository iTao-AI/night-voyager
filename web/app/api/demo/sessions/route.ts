import { forwardDemoJson } from "../../../../lib/demo-bff/transport";

export const dynamic = "force-dynamic";

export function POST(request: Request) {
  return forwardDemoJson(request, {
    method: "POST",
    upstreamPath: "/api/v1/demo/sessions",
    mutation: true,
  });
}
