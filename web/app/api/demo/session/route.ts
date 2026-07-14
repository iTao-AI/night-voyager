import { forwardDemoJson } from "../../../../lib/demo-bff/transport";

export const dynamic = "force-dynamic";

export function DELETE(request: Request) {
  return forwardDemoJson(request, {
    method: "DELETE",
    upstreamPath: "/api/v1/demo/session",
    mutation: true,
  });
}
