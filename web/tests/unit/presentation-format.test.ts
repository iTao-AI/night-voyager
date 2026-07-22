import { describe, expect, it } from "vitest";

import {
  formatCnyMinor,
  formatCnyRange,
  formatIsoDate,
} from "../../lib/presentation/format";

describe("pure presentation formatters", () => {
  it.each([
    [0, "¥0", "CNY 0"],
    [1, "¥0.01", "CNY 0.01"],
    [100, "¥1", "CNY 1"],
    [30_550_000, "¥305,500", "CNY 305,500"],
    [Number.MAX_SAFE_INTEGER, "¥90,071,992,547,409.91", "CNY 90,071,992,547,409.91"],
  ])("preserves exact CNY minor units for %s", (minor, zh, en) => {
    expect(formatCnyMinor("zh-CN", minor, "CNY")).toBe(zh);
    expect(formatCnyMinor("en", minor, "CNY")).toBe(en);
    expect(zh.replace(/\D/g, "")).toBe(en.replace(/\D/g, ""));
  });

  it("preserves exact range endpoints in both locales", () => {
    expect(formatCnyRange("zh-CN", 30_550_000, 40_000_001, "CNY")).toBe(
      "¥305,500–400,000.01",
    );
    expect(formatCnyRange("en", 30_550_000, 40_000_001, "CNY")).toBe(
      "CNY 305,500–400,000.01",
    );
  });

  it.each([
    [1, 1, "USD"],
    [-1, 1, "CNY"],
    [1.5, 2, "CNY"],
    [Number.MAX_SAFE_INTEGER + 1, Number.MAX_SAFE_INTEGER + 1, "CNY"],
  ])("fails closed for malformed money without exposing it", (minimum, maximum, currency) => {
    expect(formatCnyMinor("zh-CN", minimum, currency)).toBe("状态暂不可用");
    expect(formatCnyRange("en", minimum, maximum, currency)).toBe("Status unavailable");
  });

  it("fails closed for a reversed range without invalidating either amount", () => {
    expect(formatCnyMinor("zh-CN", 2, "CNY")).toBe("¥0.02");
    expect(formatCnyRange("en", 2, 1, "CNY")).toBe("Status unavailable");
  });

  it("formats strict calendar dates without changing the underlying day", () => {
    expect(formatIsoDate("zh-CN", "2026-09-01")).toBe("2026年9月1日");
    expect(formatIsoDate("en", "2026-09-01")).toBe("Sep 1, 2026");
  });

  it.each(["", "2026-02-30", "2026-9-1", "not-a-date"])(
    "fails closed for malformed date %s",
    (value) => {
      expect(formatIsoDate("zh-CN", value)).toBe("状态暂不可用");
      expect(formatIsoDate("en", value)).toBe("Status unavailable");
    },
  );
});
