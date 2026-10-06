import { notFound } from "next/navigation";
import { ConnectedDemo } from "../../components/connected-demo/ConnectedDemo";
import { parseConnectedDemoScenario } from "../../lib/connected-demo/scenario";

export default async function DemoPage({ searchParams }: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  let scenario;
  try { scenario = parseConnectedDemoScenario(params.scenario); }
  catch { notFound(); }
  return <ConnectedDemo scenario={scenario} />;
}
