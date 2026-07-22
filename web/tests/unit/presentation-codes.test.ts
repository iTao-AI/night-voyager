import { describe, expect, it } from "vitest";

import {
  PRESENTATION_CODE_VALUES,
  presentCode,
  presentRouteOutcome,
  presentRouteReason,
  presentTradeOff,
} from "../../lib/presentation/codes";

describe("closed presentation code maps", () => {
  it("covers every strict frontend-contract and fixture value in both locales", () => {
    for (const [kind, values] of Object.entries(PRESENTATION_CODE_VALUES)) {
      for (const value of values) {
        const zh = presentCode("zh-CN", kind as keyof typeof PRESENTATION_CODE_VALUES, value);
        const en = presentCode("en", kind as keyof typeof PRESENTATION_CODE_VALUES, value);
        expect(zh).not.toBe("状态暂不可用");
        expect(en).not.toBe("Status unavailable");
        expect(zh).not.toBe(value);
        expect(en).not.toBe(value);
      }
    }
  });

  it.each(["unknown", "__proto__", "<script>raw</script>", "en,zh-CN"])(
    "uses a bounded localized fallback without revealing %s",
    (raw) => {
      for (const locale of ["zh-CN", "en"] as const) {
        const visible = presentCode(locale, "taskStatus", raw);
        expect(visible).toBe(locale === "zh-CN" ? "状态暂不可用" : "Status unavailable");
        expect(visible).not.toContain(raw);
      }
    },
  );

  it("keeps compatibility helpers locale-aware", () => {
    expect(presentRouteOutcome("zh-CN", "recommended_with_condition")).toBe("在预算条件下推荐");
    expect(presentRouteOutcome("en", "recommended_with_condition")).toBe("Recommended with budget condition");
    expect(presentRouteReason("zh-CN", "direct_program_fit_evidence_absent")).toBe("缺少直接的项目匹配证据");
    expect(presentTradeOff("en", "budget_elasticity")).toBe("Budget flexibility");
  });
});
