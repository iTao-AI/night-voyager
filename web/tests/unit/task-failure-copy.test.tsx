import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";

import { TaskProgress } from "../../components/connected-demo/TaskProgress";
import { PresentationProvider } from "../../lib/presentation/context";
import { PRESENTATION_LOCALE_STORAGE_KEY } from "../../lib/presentation/locales";
import { ledger } from "./connected-demo-test-data";

function backendFailureCodes(): Set<string> {
  const source = (path: string) => readFileSync(resolve("../src/night_voyager", path), "utf8");
  // Derive coverage from the backend producers, independently of the UI map.
  const enumBody = source("adapters/protocols.py").split("class AdapterFailureCode(StrEnum):")[1]?.split("\n\n")[0];
  expect(enumBody).toBeDefined();
  const adapterCodes = [...enumBody!.matchAll(/^\s+[A-Z_]+ = "([a-z_]+)"$/gm)].map((match) => match[1]);
  const payloadCodes = [...source("tasks/policy.py").matchAll(/raise AdapterPayloadError\("([a-z_]+)"\)/g)].map((match) => match[1]);
  const workerCodes = [...source("tasks/worker.py").matchAll(/await repository\.fail\(\s*claim,\s*self\._worker_id,\s*"([a-z_]+)"/g)].map((match) => match[1]);
  expect(adapterCodes.length).toBeGreaterThan(0);
  expect(payloadCodes.length).toBeGreaterThan(0);
  expect(workerCodes.length).toBeGreaterThan(0);
  return new Set([...adapterCodes, ...payloadCodes, ...workerCodes].filter((code) => code !== "unknown"));
}

afterEach(() => {
  cleanup();
  localStorage.clear();
});

it.each(["zh-CN", "en"] as const)("explains backend-produced failures in the existing %s task trail", async (locale) => {
  localStorage.setItem(PRESENTATION_LOCALE_STORAGE_KEY, locale);
  const unavailable = locale === "zh-CN" ? "状态暂不可用" : "Status unavailable";
  for (const code of backendFailureCodes()) {
    const status = code === "deadline_exceeded" ? "timed_out" : code === "required_evidence_gap" ? "needs_evidence" : "failed";
    const failed = ledger("terminal_task_failure", status);
    failed.task = { ...failed.task!, public_code: code, planning_run_id: null };
    const { container, unmount } = render(<PresentationProvider><TaskProgress ledger={failed} /></PresentationProvider>);
    await waitFor(() => expect(document.documentElement.lang).toBe(locale));
    const trail = container.querySelector("details.technical-details");
    await waitFor(() => expect(trail?.textContent).toContain(locale === "en" ? "Public result" : "公开结果"));
    expect(trail, code).not.toBeNull();
    expect(trail?.textContent, code).not.toContain(unavailable);
    expect(trail?.textContent, code).not.toContain(code);
    if (code === "invalid_schema") expect(trail?.textContent).toMatch(locale === "zh-CN" ? /结构不符合要求.*顾问/ : /invalid structure.*advisor/);
    if (code === "skill_pin_invalid") expect(trail?.textContent).toMatch(locale === "zh-CN" ? /执行版本未通过校验.*顾问/ : /pinned execution version failed validation.*advisor/);
    expect(container.querySelector("button")).toBeNull();
    unmount();
  }
});

it.each(["zh-CN", "en"] as const)("keeps unknown failure details behind the %s safe fallback", async (locale) => {
  localStorage.setItem(PRESENTATION_LOCALE_STORAGE_KEY, locale);
  for (const untrustedCode of ["unknown", "<script>private-provider-response</script>"]) {
    const failed = ledger("terminal_task_failure", "failed");
    failed.task = { ...failed.task!, public_code: untrustedCode, planning_run_id: null };
    const { container, unmount } = render(<PresentationProvider><TaskProgress ledger={failed} /></PresentationProvider>);
    await waitFor(() => expect(document.documentElement.lang).toBe(locale));
    const trail = container.querySelector("details.technical-details");
    await waitFor(() => expect(trail?.textContent).toContain(locale === "en" ? "Public result" : "公开结果"));
    expect(trail?.textContent).toContain(locale === "zh-CN" ? "状态暂不可用" : "Status unavailable");
    expect(trail?.textContent).not.toContain(untrustedCode);
    expect(container.querySelector("button")).toBeNull();
    unmount();
  }
});
