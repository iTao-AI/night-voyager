import { defineConfig } from "@playwright/test";
import compose from "./playwright.compose.config";

const root = process.env.CONTROLLED_INTAKE_REVIEW_ROOT ?? "test-results/intake-native";

export default defineConfig({
  ...compose,
  testMatch: ["controlled-intake-revision.spec.ts"],
  timeout: 240_000,
  outputDir: `${root}/playwright`,
  reporter: [["list"], ["json", { outputFile: `${root}/playwright-results.json` }]],
  use: { ...compose.use, locale: "zh-CN" },
  workers: 1,
  retries: 0,
});
