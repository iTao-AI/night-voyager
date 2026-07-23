import { describe, expect, it } from "vitest";

import { en, zhCN } from "../../lib/presentation/catalog";
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

    expect(zhCN.rootRouteAtlasDescription).toBe(
      "学生希望学习数据科学，预算 30.55–40 万元。澳大利亚为推荐路线，日本为备选路线，马来西亚暂不推荐。",
    );
    expect(en.rootRouteAtlasDescription).toMatch(
      /data science.*CNY 305,500–400,000.*Australia.*Japan.*Malaysia/i,
    );
  });
});
