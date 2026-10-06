import { createHash } from "node:crypto";
import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import type { Page, Request, Response } from "@playwright/test";

export const DIAGNOSTIC_STAGES = ["started", "request-revision", "fact-confirmation", "create-task", "lost-ack-intercepted", "lost-ack-committed", "lost-ack-aborted", "replay-action", "replay-post-observed", "helper-unrouted", "student-handoff-assertion", "student-handoff-observed"] as const;
export type DiagnosticStage = typeof DIAGNOSTIC_STAGES[number];
const phases = ["task_ready", "active_task", "review_required", "revision_requested", "revision_fact_pending", "replan_required", "revision_task_active", "revision_review_required", "revision_blocked", "family_review", "plan_ready", "terminal_task_failure"];
const codes = ["bff_upstream_unavailable", "bff_session_recovery_required", "authentication_failed", "resource_unavailable", "request_validation_failed", "stale_revision", "intake_evidence_unavailable"];
const actions = {
  request_revision: ["Request revision", "请求修订"],
  reconnect: ["Reconnect advisor flow", "重新连接顾问流程"],
  continue_student: ["Continue as student", "以学生身份继续"],
  continue_advisor: ["Continue as advisor", "以顾问身份继续"],
  continue_parent: ["Continue as parent", "以家长身份继续"],
} as const;
type HttpEvent = { method: string; path: string; status: number | null; elapsed_ms: number; outcome: "pending" | "failed" | "response"; phase: string | null; role: string | null; code: string | null };

export function safePlanningRevisionPath(raw: string): string | null {
  let url: URL;
  try { url = new URL(raw, "http://127.0.0.1:3000"); }
  catch { return null; }
  if (url.origin !== "http://127.0.0.1:3000") return null;
  if (["/api/demo/session-bootstrap", "/api/demo/sessions", "/api/demo/session"].includes(url.pathname)) return url.pathname;
  const match = url.pathname.match(/^\/api\/demo\/cases\/49000000-0000-0000-0000-00000000000[12]\/(advisor-reviews|journey-status|advisor-ledger|confirmed-facts|collaboration-thread|memory-candidates|agent-tasks)$/);
  return match ? `/api/demo/cases/:case/${match[1]}` : null;
}

export function createPlanningRevisionDiagnostics(page: Page, root: string, locale: "en" | "zh-CN", candidate: string) {
  const directory = `${root}/diagnostics-${locale}`;
  const started = Date.now();
  const elapsed = () => Math.min(3_600_000, Math.max(0, Date.now() - started));
  const pending = new Map<Request, { at: number; method: string; path: string }>();
  const http: HttpEvent[] = [];
  const stages: Array<{ name: DiagnosticStage; elapsed_ms: number }> = [];
  let stage: DiagnosticStage = "started";
  let replay = { observed_posts: 0, same_key: null as boolean | null };
  let writes = Promise.resolve();
  const base = () => ({
    schema_version: 1, proof_mode: "synthetic-demo", candidate_head: candidate,
    locale, stage, stages: [...stages],
    http: [...http, ...[...pending.values()].map((event): HttpEvent => ({ method: event.method, path: event.path, status: null, elapsed_ms: Math.min(3_600_000, Math.max(0, Date.now() - event.at)), outcome: "pending", phase: null, role: null, code: null }))].slice(-128),
    document_lang: "unknown" as string,
    visible: Object.fromEntries(Object.keys(actions).map((key) => [key, null])) as Record<keyof typeof actions, boolean | null>,
    replay: { ...replay }, screenshot: null as { file: string; action: string; text_matches: true; sha256: string } | null,
  });
  function persistProgress() {
    const report = base();
    writes = writes.then(async () => {
      await mkdir(directory, { recursive: true });
      await writeFile(`${directory}/progress.pending`, JSON.stringify(report));
      await rename(`${directory}/progress.pending`, `${directory}/progress.json`);
    }).catch(() => { /* Preserve the original test failure if diagnostics cannot be written. */ });
  }
  function mark(next: DiagnosticStage) {
    stage = next;
    stages.push({ name: next, elapsed_ms: elapsed() });
    if (stages.length > 128) stages.shift();
    persistProgress();
  }
  const onRequest = (request: Request) => {
    const path = safePlanningRevisionPath(request.url());
    const method = request.method();
    if (!path || !["GET", "POST", "DELETE"].includes(method) || pending.size >= 128) return;
    pending.set(request, { at: Date.now(), method, path });
    persistProgress();
  };
  const record = (request: Request, status: number | null, body: unknown) => {
    const event = pending.get(request);
    if (!event) return;
    pending.delete(request);
    const value = body && typeof body === "object" ? body as Record<string, unknown> : {};
    const bounded = (field: string, allowed: string[]) => typeof value[field] === "string" && allowed.includes(value[field] as string) ? value[field] as string : null;
    http.push({ method: event.method, path: event.path, status, elapsed_ms: Math.min(3_600_000, Math.max(0, Date.now() - event.at)), outcome: status === null ? "failed" : "response", phase: bounded("phase", phases), role: bounded("active_role", ["advisor", "student", "parent"]), code: bounded("code", codes) });
    if (http.length > 128) http.shift();
    persistProgress();
  };
  const onResponse = (response: Response) => {
    if (!pending.has(response.request())) return;
    void (async () => {
      await response.finished();
      const event = pending.get(response.request());
      // Successful session/command bodies are never read. Only the authority
      // projection and error responses provide closed phase/role/error fields.
      const body: unknown = response.status() >= 400 || event?.path.endsWith("/journey-status")
        ? await response.json().catch(() => null) : null;
      record(response.request(), response.status(), body);
    })().catch(() => record(response.request(), null, null));
  };
  const onFailure = (request: Request) => record(request, null, null);
  page.on("request", onRequest);
  page.on("response", onResponse);
  page.on("requestfailed", onFailure);
  mark("started");

  return {
    mark,
    observeReplay(posts: number, sameKey: boolean | null) {
      replay = { observed_posts: Math.min(100, posts), same_key: sameKey };
      persistProgress();
    },
    inspect: base,
    async saveFailure() {
      const report = base();
      report.document_lang = await page.evaluate(() => ["en", "zh-CN"].includes(document.documentElement.lang) ? document.documentElement.lang : "unknown").catch(() => "unknown");
      await writes;
      for (const [action, labels] of Object.entries(actions)) {
        let unknown = false;
        let visible = false;
        for (const [index, label] of labels.entries()) {
          const button = page.getByRole("button", { name: label, exact: true }).first();
          const observed = await button.isVisible().catch(() => null);
          if (observed === null) unknown = true;
          if (!observed) continue;
          visible = true;
          // A public image is only an exact, static action button, never the page,
          // editor, body/headers, storage, original screenshot or raw trace.
          const safe = await button.evaluate((element, expected) => element.tagName === "BUTTON" && element.textContent?.trim() === expected && element.children.length === 0 && getComputedStyle(element).backgroundImage === "none" && ["::before", "::after"].every((pseudo) => ["none", "normal"].includes(getComputedStyle(element, pseudo).content)), label).catch(() => false);
          if (safe && report.screenshot === null) {
            try {
              const file = `${directory}/visible-action.png`;
              await button.screenshot({ path: file });
              report.screenshot = { file: "visible-action.png", action: `${action}-${index === 0 ? "en" : "zh-CN"}`, text_matches: true, sha256: createHash("sha256").update(await readFile(file)).digest("hex") };
            } catch { /* Full raw screenshots remain private in the existing mount. */ }
          }
        }
        report.visible[action as keyof typeof actions] = visible ? true : unknown ? null : false;
      }
      await writeFile(`${directory}/diagnostics.json`, JSON.stringify(report));
    },
    stop() {
      page.off("request", onRequest);
      page.off("response", onResponse);
      page.off("requestfailed", onFailure);
    },
  };
}

export type PlanningRevisionDiagnostics = ReturnType<typeof createPlanningRevisionDiagnostics>;
