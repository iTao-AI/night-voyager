import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import { RevisionFactEditor } from "../../components/connected-demo/RevisionFactEditor";
import { intakeFactControl } from "../../e2e/intake-locators";
import { PresentationProvider } from "../../lib/presentation/context";

const require = createRequire(import.meta.url);
type ScriptWindow = Window & { eval(source: string): unknown };
const { JSDOM } = require("jsdom") as {
  JSDOM: new (html: string, options: { runScripts: "outside-only" }) => { window: ScriptWindow };
};
const { source } = require(join(dirname(require.resolve("playwright-core/package.json")), "lib/generated/injectedScriptSource.js")) as { source: string };
interface QueryEngine {
  parseSelector(selector: string): unknown;
  querySelectorAll(selector: unknown, root: Node): Element[];
}

function fixture() {
  const caseId = "49000000-0000-0000-0000-000000000003";
  const html = renderToStaticMarkup(<PresentationProvider>
    <RevisionFactEditor expectedCaseId={caseId} expectedCaseRevision={1}
      currentFacts={{ caseId, caseRevision: 1, facts: [{
        schema_version: 1, fact_key: "student.intake", value: "2027-02", fact_version: 1,
        confirmed_at: "2026-07-01T00:00:00Z", subject_role: "student", confirming_advisor_role: "advisor",
      }] }} activeRole="student" onSubmit={() => undefined} />
  </PresentationProvider>);
  const dom = new JSDOM(html, { runScripts: "outside-only" });
  // This markup has no pseudo-element content; JSDOM provides ordinary computed styles only.
  const computedStyle = dom.window.getComputedStyle.bind(dom.window);
  dom.window.getComputedStyle = element => computedStyle(element);
  const Constructor = dom.window.eval(`var module = { exports: {} };\n${source}\nmodule.exports.InjectedScript();`) as new (window: Window, options: object) => QueryEngine;
  const engine = new Constructor(dom.window, {
    isUnderTest: true, sdkLanguage: "javascript", testIdAttributeName: "data-testid",
    stableRafCount: 1, browserName: "chromium", customEngines: [], isUtilityWorld: false,
  });
  const query = (selector: string) => engine.querySelectorAll(engine.parseSelector(selector), dom.window.document);
  return {
    dom,
    queries: {
      getByLabel: (name: string) => query(`internal:label=${JSON.stringify(name)}s`),
      getByRole: (role: "combobox", options: { name: string }) => query(`internal:role=${role}[name=${JSON.stringify(options.name)}s]`),
    },
  };
}

it("reproduces the locked Playwright label mismatch and the exact accessible-role match", () => {
  const { dom, queries } = fixture();
  try {
    const control = dom.window.document.querySelector("select")!;
    expect(control.labels![0].textContent).toBe("要修改的事实入学月份");
    expect(queries.getByLabel("要修改的事实")).toHaveLength(0);
    const accessible = queries.getByRole("combobox", { name: "要修改的事实" });
    expect(accessible).toHaveLength(1);
    expect(accessible[0].id).toBe(control.id);
  } finally { dom.window.close(); }
});

it("selects the actual intake editor through the locator used by the focused E2E", () => {
  const { dom, queries } = fixture();
  try {
    const selected = intakeFactControl(queries);
    expect(selected).toHaveLength(1);
    expect(selected[0].id).toBe("revision-fact-key");
  }
  finally { dom.window.close(); }
});
