import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  SHOWCASE_ASSET_CONTRACT,
  SHOWCASE_ASSET_NAMES,
} from "../../lib/presentation/showcase";

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
      "当前提变化或执行受阻时，保留版本、回执和恢复入口，不沿用过期状态继续执行。",
    );
    expect(readmeCn).toContain("## 顾问工作台概览");
    expect(readmeCn).toContain("## 三个产品判断");
    expect(readmeCn).not.toContain("## Advisor workspace overview");
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
});
