import { describe, expect, it } from "vitest";

import { en, zhCN } from "../../lib/presentation/catalog";
import { formatCnyRange } from "../../lib/presentation/format";

describe("portfolio catalog contract", () => {
  it("uses catalog-backed country, status, and reason keys in both locales", () => {
    expect(zhCN.rootOriginBudget).toBe("规划预算 ¥300,000–400,000");
    expect(zhCN.rootRouteAtlasDescription).toContain("CNY 300,000–400,000");
    expect(en.rootOriginBudget).toBe("Planning budget CNY 300,000–400,000");
    expect(en.rootRouteAtlasDescription).toContain("CNY 300,000–400,000");
    expect(
      [
        zhCN.rootOriginBudget,
        zhCN.rootRouteAtlasDescription,
        en.rootOriginBudget,
        en.rootRouteAtlasDescription,
      ].join(" "),
    ).not.toMatch(/340,000|¥340,000/);
  });

  it("keeps governed-flow money formatting exact", () => {
    expect(formatCnyRange("zh-CN", 30_550_000, 40_000_000, "CNY")).toBe(
      "¥305,500–400,000",
    );
    expect(formatCnyRange("en", 30_550_000, 40_000_000, "CNY")).toBe(
      "CNY 305,500–400,000",
    );
  });
});
