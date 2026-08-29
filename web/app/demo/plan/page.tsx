import { PlanExecutionWorkspace } from "../../../components/plan-execution/PlanExecutionWorkspace";
import { notFound } from "next/navigation";
import { parsePlanExecutionRoute } from "../../../lib/plan-execution/scenario";

async function resolveAuthority(
  searchParams: Promise<Record<string, string | string[] | undefined>>,
) {
  try {
    return parsePlanExecutionRoute(await searchParams);
  } catch {
    notFound();
  }
}

export default async function PlanExecutionPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const authority = await resolveAuthority(searchParams);
  return <PlanExecutionWorkspace authority={authority} />;
}
