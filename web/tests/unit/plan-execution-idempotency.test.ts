import { expect, it, vi } from "vitest";

import {
  idempotencyFor,
  matchesIdempotencyRecord,
} from "../../lib/plan-execution/idempotency";

it("reuses one stable slot only for the exact canonical body", async () => {
  vi.spyOn(crypto, "randomUUID").mockReturnValueOnce("10000000-0000-0000-0000-000000000001");
  const first = await idempotencyFor({ b: 2, a: 1 });
  const replay = await idempotencyFor({ a: 1, b: 2 }, first);

  expect(replay).toEqual(first);
  expect(await matchesIdempotencyRecord({ a: 1, b: 2 }, first)).toBe(true);
  expect(await matchesIdempotencyRecord({ a: 1, b: 3 }, first)).toBe(false);
});

it("creates a new stable slot for a confirmed different user action", async () => {
  vi.spyOn(crypto, "randomUUID")
    .mockReturnValueOnce("10000000-0000-0000-0000-000000000001")
    .mockReturnValueOnce("10000000-0000-0000-0000-000000000002");
  const first = await idempotencyFor({ kind: "progress" });
  const second = await idempotencyFor({ kind: "completion" }, first);

  expect(second.idempotencyKey).not.toBe(first.idempotencyKey);
  expect(second.fingerprint).not.toBe(first.fingerprint);
});
