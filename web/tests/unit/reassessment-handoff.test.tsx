import { afterEach, expect, it } from "vitest";
import { cleanup } from "@testing-library/react";

import { parsePlanExecutionContext, parseTimelineExecutionView } from "../../lib/plan-execution/contracts";
import { buildReassessmentHandoff } from "../../lib/plan-execution/reassessment-handoff";
import { handoffFixture, handoffId } from "../fixtures/reassessment-handoff";

afterEach(() => { cleanup(); window.localStorage.clear(); });

it("consumes complete accepted read DTOs and exports saved source identities without actors", () => {
  const { context, view } = handoffFixture();
  const summary = buildReassessmentHandoff(
    parsePlanExecutionContext(context), parseTimelineExecutionView(view), "zh-CN",
  );
  expect(summary?.text).toContain("申请提交");
  expect(summary?.text).toContain("缺少必需输入");
  expect(summary?.text).toContain("2026-10-15");
  expect(summary?.text).toContain("保存时的数据库日期：2026-10-07");
  expect(summary?.text).toContain("当前视图所见日期：2026-10-09");
  expect(summary?.text).toContain(handoffId(1));
  expect(summary?.text).toContain(handoffId(4));
  expect(summary?.text).toContain(handoffId(5));
  expect(summary?.text).toContain(handoffId(11));
  expect(summary?.text).toContain(handoffId(30));
  expect(summary?.text).toContain("pending_future_authorization");
  expect(summary?.text).not.toMatch(/actor|csrf|token|cookie|header/i);
  expect(summary?.text).not.toContain(handoffId(90));
  expect(summary?.text).not.toContain(handoffId(91));
});

it("uses the saved checkpoint rather than the independently projected current checkpoint", () => {
  const { context, view } = handoffFixture();
  view.current_checkpoint = view.checkpoints[0];
  const summary = buildReassessmentHandoff(context, view, "en");
  expect(summary?.facts).toContainEqual({ label: "Saved checkpoint", value: "Application" });
  expect(summary?.facts).toContainEqual({ label: "Due date", value: "2026-10-15" });
  expect(summary?.text).not.toContain("2026-09-01");
});

it.each(["reference", "checkpoint", "execution", "kind", "missing"] as const)(
  "does not attribute a blocker reason from a %s mismatch", (mismatch) => {
    const { context, view } = handoffFixture();
    if (mismatch === "missing") view.latest_attestation = null;
    else if (mismatch === "reference") view.latest_attestation!.attestation_id = handoffId(99);
    else if (mismatch === "checkpoint") view.latest_attestation!.checkpoint_id = handoffId(10);
    else if (mismatch === "execution") view.latest_attestation!.execution_id = handoffId(99);
    else view.latest_attestation!.attestation_kind = "progress";
    const summary = buildReassessmentHandoff(context, view, "en");
    expect(summary?.text).toContain("Matching blocked attestation details are unavailable in this view.");
    expect(summary?.text).not.toContain("Missing required input");
  },
);

it("reports saved deadline acceptance and both server dates without attributing an unrelated blocker", () => {
  const { context, view } = handoffFixture("deadline_elapsed");
  view.latest_attestation = handoffFixture().view.latest_attestation;
  const summary = buildReassessmentHandoff(context, parseTimelineExecutionView(view), "en");
  expect(summary?.text).toContain("Accepted database date: 2026-10-16");
  expect(summary?.text).toContain("View observed date: 2026-10-20");
  expect(summary?.text).toContain("The server accepted the saved checkpoint's elapsed deadline. No further reason was provided.");
  expect(summary?.text).not.toContain("Missing required input");
  expect(summary?.text).toContain("Saved projection reference only; the browser has not revalidated the trigger.");
});

it.each(["case_id", "case_revision", "decision_id", "decision_receipt_id", "timeline_plan_id", "execution_id"] as const)(
  "removes the summary when the current context changes %s", (field) => {
    const { context, view } = handoffFixture();
    const changed = { ...context, [field]: field === "case_revision" ? 3 : handoffId(99) };
    expect(buildReassessmentHandoff(changed, view, "en")).toBeNull();
  },
);

it("does not export an active execution or unsaved reassessment", () => {
  const { context, view } = handoffFixture();
  view.execution.state = "active";
  expect(buildReassessmentHandoff(context, view, "en")).toBeNull();
  view.execution.state = "reassessment_required";
  view.reassessment = null;
  expect(buildReassessmentHandoff(context, view, "en")).toBeNull();
});
