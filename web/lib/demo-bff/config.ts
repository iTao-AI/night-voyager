export interface DemoBffConfig {
  apiOrigin: string;
  publicOrigin: string;
  jsonTimeoutMs: number;
  maxJsonBytes: number;
}

type DemoEnvironment = Record<string, string | undefined>;

function requireEnv(env: DemoEnvironment, name: string): string {
  const value = env[name];
  if (!value) throw new Error(`missing ${name}`);
  return value;
}

export function loadDemoBffConfig(
  env: DemoEnvironment = process.env,
): DemoBffConfig {
  const api = new URL(requireEnv(env, "NIGHT_VOYAGER_API_INTERNAL_URL"));
  const publicUrl = new URL(requireEnv(env, "NIGHT_VOYAGER_PUBLIC_ORIGIN"));
  if (
    !["http:", "https:"].includes(api.protocol) ||
    api.username ||
    api.password ||
    api.pathname !== "/" ||
    api.search ||
    api.hash
  ) {
    throw new Error("invalid internal API origin");
  }
  if (
    !["http:", "https:"].includes(publicUrl.protocol) ||
    publicUrl.username ||
    publicUrl.password ||
    publicUrl.pathname !== "/" ||
    publicUrl.search ||
    publicUrl.hash
  ) {
    throw new Error("invalid public origin");
  }
  return {
    apiOrigin: api.origin,
    publicOrigin: publicUrl.origin,
    jsonTimeoutMs: 10_000,
    maxJsonBytes: 32 * 1024,
  };
}
