import { PlanExecutionWorkspace } from "../../../components/plan-execution/PlanExecutionWorkspace";
import { notFound } from "next/navigation";
import { parsePlanExecutionScenario } from "../../../lib/plan-execution/scenario";

async function resolveScenario(
  searchParams: Promise<Record<string, string | string[] | undefined>>,
) {
  try {
    return parsePlanExecutionScenario(await searchParams);
  } catch {
    notFound();
  }
}

export default async function PlanExecutionPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const scenario = await resolveScenario(searchParams);
  return <PlanExecutionWorkspace scenario={scenario} />;
}
