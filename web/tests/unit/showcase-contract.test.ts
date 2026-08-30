import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  SHOWCASE_ASSET_CONTRACT,
  SHOWCASE_ASSET_NAMES,
} from "../../lib/presentation/showcase";
import { en, zhCN } from "../../lib/presentation/catalog";

const MANIFEST_PATH = resolve(process.cwd(), "../docs/evidence/advisor-showcase-manifest.json");
const README_PATH = resolve(process.cwd(), "../README.md");
const README_CN_PATH = resolve(process.cwd(), "../README_CN.md");

function readFirstLayer(path: string, boundary: string): string {
  const readme = readFileSync(path, "utf8");
  const boundaryIndex = readme.indexOf(boundary);

  expect(boundaryIndex).toBeGreaterThan(0);
  return readme.slice(0, boundaryIndex);
}

describe("advisor showcase contract", () => {
  it("freezes the four canonical real-state frames", () => {
    expect(SHOWCASE_ASSET_NAMES).toEqual([
      "advisor-workspace-overview.png",
      "advisor-normal-path.png",
      "advisor-blocked-recovery.png",
      "advisor-workspace-mobile.png",
    ]);
    expect(SHOWCASE_ASSET_CONTRACT).toMatchObject({
      "advisor-workspace-overview.png": {
        route: "/",
        state: "route_analysis_preview",
        locale: "zh-CN",
        proofSegment: "connected_same_case",
        viewport: { width: 1600, height: 1000 },
      },
      "advisor-normal-path.png": {
        route: "/demo",
        state: "persisted_receipt_timeline",
        locale: "zh-CN",
        proofSegment: "connected_same_case",
        viewport: { width: 1600, height: 1000 },
      },
      "advisor-blocked-recovery.png": {
        route: "/demo/plan?scenario=blocked",
        state: "blocked_reassessment",
        locale: "zh-CN",
        proofSegment: "independent_execution_scenario",
        viewport: { width: 1600, height: 1000 },
      },
      "advisor-workspace-mobile.png": {
        route: "/",
        state: "route_analysis_preview",
        locale: "zh-CN",
        proofSegment: "connected_same_case",
        viewport: { width: 390, height: 844 },
      },
    });
  });

  it("keeps a committed public-neutral manifest with matching hashes", () => {
    const manifest = JSON.parse(readFileSync(MANIFEST_PATH, "utf8")) as {
      schema_version: string;
      source: { commit: string; tree: string };
      synthetic_demo_disclosure: string;
      assets: Record<string, {
        path: string;
        sha256: string;
        route: string;
        state: string;
        locale: string;
        proof_segment: string;
        viewport: { width: number; height: number };
      }>;
    };

    expect(manifest.schema_version).toBe("night-voyager.advisor-showcase.v1");
    expect(manifest.source.commit).toMatch(/^[0-9a-f]{40}$/);
    expect(manifest.source.tree).toMatch(/^[0-9a-f]{40}$/);
    expect(manifest.synthetic_demo_disclosure).toMatch(/synthetic|合成/i);
    expect(Object.keys(manifest.assets)).toEqual(SHOWCASE_ASSET_NAMES);

    for (const name of SHOWCASE_ASSET_NAMES) {
      const asset = manifest.assets[name];
      expect(asset.sha256).toMatch(/^[0-9a-f]{64}$/);
      const png = readFileSync(resolve(process.cwd(), "..", asset.path));
      expect(png.subarray(0, 8)).toEqual(Buffer.from("89504e470d0a1a0a", "hex"));
      expect(png.subarray(12, 16).toString("ascii")).toBe("IHDR");
      expect({ width: png.readUInt32BE(16), height: png.readUInt32BE(20) }).toEqual(asset.viewport);
      expect(createHash("sha256").update(png).digest("hex")).toBe(asset.sha256);
      expect(asset.route).toBe(SHOWCASE_ASSET_CONTRACT[name].route);
      expect(asset.state).toBe(SHOWCASE_ASSET_CONTRACT[name].state);
      expect(asset.locale).toBe(SHOWCASE_ASSET_CONTRACT[name].locale);
      expect(asset.proof_segment).toBe(SHOWCASE_ASSET_CONTRACT[name].proofSegment);
      expect(asset.viewport).toEqual(SHOWCASE_ASSET_CONTRACT[name].viewport);
    }
  });

  it("keeps the first layer anchored in the frozen product judgments", () => {
    const readme = readFirstLayer(README_PATH, "\n## Detailed proof\n");
    const readmeCn = readFirstLayer(README_CN_PATH, "\n## 详细证明\n");

    expect(readme).toContain(
      "Confirmed facts are kept separate from dialogue drafts; planning consumes only explicit facts.",
    );
    expect(readme).toContain(
      "The Agent analyzes and recommends, but responsibility-bearing decisions and actions remain with the advisor and client, not the model.",
    );
    expect(readme).toContain(
      "When premises change or execution is blocked, preserve versions, receipts, and recovery entry points instead of continuing with stale state.",
    );

    expect(readmeCn).toContain(
      "已确认事实与对话草稿分开保存；后续规划只使用明确确认的事实。",
    );
    expect(readmeCn).toContain(
      "智能助手可以分析并提出建议，但承担责任的决定和行动仍由顾问与客户负责，不能由模型代替。",
    );
    expect(readmeCn).toContain(
      "当方案前提发生变化或执行受阻时，保留版本、回执和恢复入口，不沿用过期状态继续执行。",
    );
    expect(readmeCn).toContain("## 顾问工作台概览");
    expect(readmeCn).toContain("## 三个产品判断");
    expect(readmeCn).not.toContain("## Advisor workspace overview");
    expect(readme).toContain(
      "The committed `advisor-normal-path.png` is the receipt and action-timeline handoff frame for the same consultation case: after route analysis, advisor review, and client confirmation, the existing primary action continues that same Case at `/demo/plan?case_id=<case_id>` in the server-derived, role-gated execution workspace. Bare `/demo/plan` remains an independently seeded Happy / Blocked scenario and does not carry the Case or session forward.",
    );
    expect(readme).toContain("the preceding case");
    expect(readmeCn).toContain("留学顾问团队");
    expect(readmeCn).toContain("参与确认的学生和家长");
    expect(readmeCn).toContain("来源版本、页面状态、图像尺寸和 SHA-256");
    expect(readmeCn).toContain("标准 390x844 视口");
    expect(readmeCn).toContain("决策回执与行动时间线");
    expect(readmeCn).toContain(
      "阻塞帧展示一个单独设置的确定性执行场景：当方案前提或预算发生变化，导致检查点受阻时，工作流回到顾问重新评估或安全停止。",
    );
  });

  it("keeps internal execution language below the detailed-proof boundary", () => {
    const readme = readFirstLayer(README_PATH, "\n## Detailed proof\n").toLowerCase();
    const readmeCn = readFirstLayer(README_CN_PATH, "\n## 详细证明\n").toLowerCase();

    for (const phrase of [
      "durable facts versus live events",
      "live execution seam",
      "model/tool result",
      "capability providers and consumers",
      "approval and sandbox",
      "agent output",
      "each turn moves through step",
    ]) {
      expect(readme).not.toContain(phrase);
    }

    for (const phrase of [
      "durable facts 与 live events",
      "live execution seam",
      "model/tool result",
      "provider/consumer",
      "approval 与 sandbox",
      "agent output",
      "capability 与 authority",
      "每个 turn 经过 step",
    ]) {
      expect(readmeCn).not.toContain(phrase);
    }
  });

  it("describes the connected same-Case receipt handoff separately from independent scenarios", () => {
    const readme = readFirstLayer(README_PATH, "\n## Detailed proof\n");
    const readmeCn = readFirstLayer(README_CN_PATH, "\n## 详细证明\n");

    expect(readme).toContain(
      "5. **Record the outcome and offer the next handoff:** preserve the decision receipt and action timeline, and offer the existing role-gated entry so the same case can continue into the execution workspace.",
    );
    expect(readme).toContain(
      "The committed `advisor-normal-path.png` is the receipt and action-timeline handoff frame for the same consultation case: after route analysis, advisor review, and client confirmation, the existing primary action continues that same Case at `/demo/plan?case_id=<case_id>` in the server-derived, role-gated execution workspace. Bare `/demo/plan` remains an independently seeded Happy / Blocked scenario and does not carry the Case or session forward.",
    );

    expect(readmeCn).toContain(
      "5. **记录结果并提供下一步交接：** 持久化决策回执与行动时间线，并提供现有的角色受限入口，让同一 Case 可以继续进入执行工作区。",
    );
    expect(readmeCn).toContain(
      "已提交的 `advisor-normal-path.png` 是同一咨询个案的回执与行动时间线交接帧：路线研判、顾问审核和客户确认完成后，现有主操作会在 `/demo/plan?case_id=<case_id>` 把同一 Case 继续带入由服务器推导、按角色限制的执行工作区。裸 `/demo/plan` 仍是单独设置的 Happy / Blocked 场景，不承接这个 Case 或 session。",
    );

    expect(zhCN.rootJourneyStepThreeBody).toBe(
      "客户确认形成回执与计划；现有主操作会把同一 Case 交给服务器推导、角色受限的执行工作区。裸 /demo/plan 仍是单独设置的确定性场景，不承接当前 Case 或 session。",
    );
    expect(en.rootJourneyStepThreeBody).toBe(
      "Client confirmation creates a receipt and plan; the existing primary action continues the same Case into the server-derived, role-gated execution workspace. Bare /demo/plan remains an independently seeded deterministic scenario and does not carry this Case or session forward.",
    );
    expect(zhCN.rootWorkflowBody).toBe(
      "连接证明会继续通过回执与 TimelinePlan 交接：现有主操作把同一 Case 带入服务器推导、角色受限的执行工作区；裸 /demo/plan 的 Happy / Blocked 场景仍单独设置，不承接任何 Case 或 session。",
    );
    expect(en.rootWorkflowBody).toBe(
      "The connected proof continues past the receipt and TimelinePlan handoff: the existing primary action carries the same Case into the server-derived, role-gated execution workspace. Bare /demo/plan Happy / Blocked scenarios remain independently seeded and carry no Case or session.",
    );
  });

  it("keeps reader-facing case and manifest vocabulary natural in the first layer", () => {
    const readme = readFirstLayer(README_PATH, "\n## Detailed proof\n").toLowerCase();
    const readmeCn = readFirstLayer(README_CN_PATH, "\n## 详细证明\n").toLowerCase();

    for (const phrase of [
      "connected same-case",
      "connected case",
      "student/client",
      "source commit/tree",
      "route/state",
      "viewport",
      "locale",
      "timelineplan",
    ]) {
      expect(readme).not.toContain(phrase);
    }

    for (const phrase of [
      "connected same-case",
      "connected case",
      "student/client",
      "学生和客户",
      "source commit/tree",
      "route/state",
      "viewport",
      "locale",
      "timelineplan",
      "独立播种",
      "当前提",
    ]) {
      expect(readmeCn).not.toContain(phrase);
    }
  });
});
