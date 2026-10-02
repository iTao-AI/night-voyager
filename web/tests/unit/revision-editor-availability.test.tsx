import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { RevisionFactEditor } from "../../components/connected-demo/RevisionFactEditor";
import type { BudgetValue, ConfirmedFactParticipant } from "../../lib/collaboration-demo/contracts";
import { PresentationProvider } from "../../lib/presentation/context";
import type { RevisionIntent } from "../../lib/connected-demo/revision";

const CASE_ID = "41000000-0000-0000-0000-000000000001";
const budget: BudgetValue = { schema_version: 1, currency: "CNY", period: "program_total", preferred_minor: 34000000, hard_ceiling_minor: 40000000, elasticity_bps: 1000, refused: false };
function fact(fact_key: ConfirmedFactParticipant["fact_key"], value: ConfirmedFactParticipant["value"]): ConfirmedFactParticipant {
  return { schema_version: 1, fact_key, value, fact_version: 1, confirmed_at: "2026-10-01T00:00:00Z", subject_role: fact_key === "family.budget" ? "parent" : "student", confirming_advisor_role: "advisor" };
}
const countries = fact("student.preferred_countries", ["japan", "malaysia"]);
const family = fact("family.budget", budget);
const projection = (facts: ConfirmedFactParticipant[]) => ({ caseId: CASE_ID, caseRevision: 2, facts });
const props = { expectedCaseId: CASE_ID, expectedCaseRevision: 2, onSubmit: vi.fn() };
afterEach(() => { cleanup(); localStorage.clear(); vi.clearAllMocks(); });
const mount = (extra: Partial<React.ComponentProps<typeof RevisionFactEditor>> = {}) => render(<RevisionFactEditor {...props} currentFacts={projection([family])} {...extra} />, { wrapper: PresentationProvider });

it("offers only the confirmed budget and waits for explicit parent preparation", () => {
  const prepare = vi.fn(); mount({ onPrepareFact: prepare });
  expect(screen.getByRole("combobox", { name: "要修改的事实" })).toHaveValue("family.budget");
  expect(screen.getAllByRole("option").map(item => item.getAttribute("value"))).toEqual(["family.budget"]);
  expect(screen.getByText(/意向国家尚未完成事实确认/)).toBeVisible();
  expect(screen.queryByText(/请重新加载后再提出变更/)).toBeNull();
  expect(screen.queryByLabelText("常规预算")).toBeNull();
  expect(prepare).not.toHaveBeenCalled(); expect(props.onSubmit).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "以家长编辑预算" }));
  expect(prepare).toHaveBeenCalledWith("family.budget"); expect(props.onSubmit).not.toHaveBeenCalled();
});
it("offers only confirmed countries even when the active participant is the parent", () => {
  const prepare = vi.fn(); mount({ currentFacts: projection([countries]), activeRole: "parent", onPrepareFact: prepare });
  expect(screen.getByRole("combobox")).toHaveValue("student.preferred_countries");
  expect(screen.getAllByRole("option").map(item => item.getAttribute("value"))).toEqual(["student.preferred_countries"]);
  expect(prepare).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "以学生编辑意向国家" }));
  expect(prepare).toHaveBeenCalledWith("student.preferred_countries");
});
it("retains both confirmed choices and emits the actual selected country proposal", () => {
  mount({ currentFacts: projection([countries, family]) });
  expect(screen.getAllByRole("option").map(item => item.getAttribute("value"))).toEqual(["student.preferred_countries", "family.budget"]);
  expect(screen.getByRole("combobox")).toHaveValue("student.preferred_countries");
  fireEvent.click(screen.getByRole("checkbox", { name: "日本" }));
  fireEvent.click(screen.getByRole("button", { name: "提交变更提案" }));
  expect(props.onSubmit).toHaveBeenCalledWith({ expectedCaseRevision: 2, factKey: "student.preferred_countries", value: ["malaysia"] });
});
it.each([
  ["missing", null, /当前已确认事实尚未载入/],
  ["old revision", { ...projection([countries, family]), caseRevision: 1 }, /事实投影与当前档案不一致/],
  ["wrong Case", { ...projection([countries, family]), caseId: "41000000-0000-0000-0000-000000000002" }, /事实投影与当前档案不一致/],
  ["empty", projection([]), /没有可修订的已确认事实/],
  ["refused budget", projection([fact("family.budget", { ...budget, refused: true, preferred_minor: null, hard_ceiling_minor: null })]), /没有可修订的已确认事实/],
] as const)("blocks edit and role preparation for %s with an accurate reason", (_name, currentFacts, reason) => {
  const prepare = vi.fn(); mount({ currentFacts, onPrepareFact: prepare });
  expect(screen.getByText(reason)).toBeVisible();
  expect(screen.queryByRole("combobox")).toBeNull();
  expect(screen.queryByRole("textbox")).toBeNull();
  expect(screen.queryByRole("button")).toBeNull();
  expect(prepare).not.toHaveBeenCalled(); expect(props.onSubmit).not.toHaveBeenCalled();
});
it("restores an existing budget intention for explicit parent handoff and exact submission", () => {
  const intent: RevisionIntent = { expectedCaseRevision: 2, factKey: "family.budget", value: { ...budget, preferred_minor: 30000000, hard_ceiling_minor: 39000000 } };
  const prepare = vi.fn(); const view = mount({ submittedIntent: intent, onPrepareFact: prepare });
  expect(screen.getByRole("combobox")).toHaveValue("family.budget");
  expect(screen.getByLabelText("已保存的提交意图")).toHaveTextContent(/300,000.*390,000/);
  expect(prepare).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "以家长编辑预算" }));
  view.rerender(<RevisionFactEditor {...props} currentFacts={projection([family])} activeRole="parent" submittedIntent={intent} onPrepareFact={prepare} />);
  expect(screen.getByLabelText("常规预算")).toHaveValue("300000");
  expect(screen.getByLabelText("最高预算")).toHaveValue("390000");
  fireEvent.click(screen.getByRole("button", { name: "以家长提交预算提案" }));
  expect(props.onSubmit).toHaveBeenCalledWith(intent);
});
it.each(["missing fact", "stale intention"] as const)("keeps a %s visible without replacing it with a budget mutation", (kind) => {
  const intent: RevisionIntent = { expectedCaseRevision: kind === "stale intention" ? 1 : 2, factKey: "student.preferred_countries", value: ["australia"] };
  mount({ submittedIntent: intent, activeRole: "parent", onPrepareFact: vi.fn() });
  expect(screen.getByLabelText("已保存的提交意图")).toHaveTextContent("澳大利亚");
  expect(screen.getByText(/保留已保存的提交意图/)).toBeVisible();
  expect(screen.queryByRole("combobox")).toBeNull();
  expect(screen.queryByRole("button")).toBeNull();
  expect(props.onSubmit).not.toHaveBeenCalled();
});
