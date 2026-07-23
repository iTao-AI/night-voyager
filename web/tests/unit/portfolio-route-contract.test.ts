import { describe, expect, it } from "vitest";

import { en, zhCN } from "../../lib/presentation/catalog";
import { formatCnyRange } from "../../lib/presentation/format";
import { PORTFOLIO_ROUTE_STOPS } from "../../lib/presentation/portfolio";

describe("portfolio route contract", () => {
  it("keeps the approved route order and emphasis closed", () => {
    expect(PORTFOLIO_ROUTE_STOPS.map(({ id }) => id)).toEqual([
      "australia",
      "japan",
      "malaysia",
    ]);
    expect(PORTFOLIO_ROUTE_STOPS.map(({ emphasis }) => emphasis)).toEqual([
      "primary",
      "secondary",
      "muted",
    ]);
  });

  it("uses catalog-backed country, status, and reason keys in both locales", () => {
    for (const stop of PORTFOLIO_ROUTE_STOPS) {
      for (const key of [stop.countryKey, stop.statusKey, stop.reasonKey]) {
        expect(zhCN[key]).toBeTruthy();
        expect(en[key]).toBeTruthy();
      }
    }

    expect(zhCN.rootOriginBudget).toBe("预算 30–40 万元");
    expect(zhCN.rootRouteAtlasDescription).toBe(
      "学生希望学习数据科学，预算 30–40 万元。澳大利亚为推荐路线，日本为备选路线，马来西亚暂不推荐。",
    );
    expect(en.rootOriginBudget).toBe("Budget CNY 300,000–400,000");
    expect(en.rootRouteAtlasDescription).toBe(
      "The student plans to study data science with a budget of CNY 300,000–400,000. Australia is recommended, Japan is the reserve route, and Malaysia is not recommended at present.",
    );
    expect(
      [
        zhCN.rootOriginBudget,
        zhCN.rootRouteAtlasDescription,
        en.rootOriginBudget,
        en.rootRouteAtlasDescription,
      ].join(" "),
    ).not.toMatch(/30\.55|305,500/);
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
