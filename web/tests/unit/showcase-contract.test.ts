import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  SHOWCASE_ASSET_CONTRACT,
  SHOWCASE_ASSET_NAMES,
} from "../../lib/presentation/showcase";

const MANIFEST_PATH = resolve(process.cwd(), "../docs/evidence/advisor-showcase-manifest.json");

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
});
