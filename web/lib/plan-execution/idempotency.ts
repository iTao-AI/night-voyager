function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    return `{${Object.keys(record).sort().map((key) => `${JSON.stringify(key)}:${canonical(record[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}
export interface PlanExecutionIdempotencyRecord { fingerprint: string; idempotencyKey: string }
export async function idempotencyFor(
  body: unknown,
  previous?: PlanExecutionIdempotencyRecord,
): Promise<PlanExecutionIdempotencyRecord> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(canonical(body)));
  const fingerprint = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
  return previous?.fingerprint === fingerprint
    ? previous
    : { fingerprint, idempotencyKey: crypto.randomUUID() };
}
