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

    expect(zhCN.rootOriginBudget).toBe("预算 ¥340,000–400,000");
    expect(zhCN.rootRouteAtlasDescription).toBe(
      "当前档案的 intended field 为 computing，预算为 CNY 340,000–400,000。澳大利亚在预算条件下推荐，日本为有条件备选，马来西亚暂不可选。",
    );
    expect(en.rootOriginBudget).toBe("Budget CNY 340,000–400,000");
    expect(en.rootRouteAtlasDescription).toBe(
      "The current case has intended field computing and a CNY 340,000–400,000 budget. Australia is recommended with a budget condition, Japan is a conditional alternative, and Malaysia is blocked.",
    );
    expect(
      [
        zhCN.rootOriginBudget,
        zhCN.rootRouteAtlasDescription,
        en.rootOriginBudget,
        en.rootRouteAtlasDescription,
      ].join(" "),
    ).not.toMatch(/30\.55|305,500|300,000/);
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
