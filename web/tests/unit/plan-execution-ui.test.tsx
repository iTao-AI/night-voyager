import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";

import { PlanExecutionWorkspace } from "../../components/plan-execution/PlanExecutionWorkspace";
import { PresentationProvider } from "../../lib/presentation/context";
import { PRESENTATION_LOCALE_STORAGE_KEY } from "../../lib/presentation/locales";
import { contextFixture, viewFixture } from "./plan-execution-contracts.test";

afterEach(() => {
  cleanup();
  window.localStorage.clear();
});

function activeController() {
  return {
    state: {
      value: "checkpoint_active" as const,
      context: contextFixture,
      view: viewFixture(),
      receipt: null,
      error: null,
    },
    busy: false,
    connect: async () => undefined,
    switchRole: async () => undefined,
    start: async () => undefined,
    attest: async () => undefined,
    verify: async () => undefined,
    recover: async () => undefined,
  };
}

it("renders the current action first without raw hashes or row versions", () => {
  const controller = activeController();
  const { container } = render(
    <PresentationProvider>
      <PlanExecutionWorkspace controller={controller} />
    </PresentationProvider>,
  );
  expect(screen.getByRole("heading", { name: "当前行动" })).toBeInTheDocument();
  expect(container.querySelector("[data-section='current-action']"))
    .toBe(container.querySelector("main section"));
  expect(container.textContent).not.toMatch(/[0-9a-f]{64}/);
  expect(container.textContent).not.toContain("row_version");
  expect(screen.getByRole("button", { name: "记录进行中" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "提交完成状态给顾问" })).toBeInTheDocument();
});

it("routes every core execution control through the English catalog", async () => {
  window.localStorage.setItem(PRESENTATION_LOCALE_STORAGE_KEY, "en");
  render(
    <PresentationProvider>
      <PlanExecutionWorkspace controller={activeController()} />
    </PresentationProvider>,
  );
  await waitFor(() => {
    expect(screen.getByRole("heading", { name: "Current action" })).toBeInTheDocument();
  });
  expect(screen.getByRole("button", { name: "Record progress" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Submit completion to advisor" })).toBeInTheDocument();
  expect(screen.getByText("Due date")).toBeInTheDocument();
  expect(screen.getByText("Owner role")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Activity" })).toBeInTheDocument();
  expect(screen.queryByText("记录进行中")).not.toBeInTheDocument();
  expect(screen.queryByText("负责角色")).not.toBeInTheDocument();
});
