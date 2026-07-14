export type DemoBffProblemCode =
  | "bff_invalid_request"
  | "bff_origin_rejected"
  | "bff_session_recovery_required"
  | "bff_request_too_large"
  | "bff_unsupported_media_type"
  | "bff_upstream_unavailable"
  | "bff_upstream_timeout";

export function demoBffProblem(
  status: number,
  code: DemoBffProblemCode,
  detail: string,
): Response {
  return Response.json(
    {
      type: `https://night-voyager.invalid/problems/${code}`,
      title: "Request could not be completed",
      status,
      detail,
      code,
    },
    {
      status,
      headers: {
        "Content-Type": "application/problem+json",
        "Cache-Control": "no-store",
      },
    },
  );
}
