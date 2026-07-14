function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    return `{${Object.keys(record).sort().map((key) => `${JSON.stringify(key)}:${canonical(record[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

export async function requestFingerprint(value: unknown): Promise<string> {
  const bytes = new TextEncoder().encode(canonical(value));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export interface IdempotencyRecord {
  fingerprint: string;
  idempotencyKey: string;
}

export async function idempotencyFor(
  body: unknown,
  previous?: IdempotencyRecord,
): Promise<IdempotencyRecord> {
  const fingerprint = await requestFingerprint(body);
  if (previous?.fingerprint === fingerprint) return previous;
  return { fingerprint, idempotencyKey: crypto.randomUUID() };
}
