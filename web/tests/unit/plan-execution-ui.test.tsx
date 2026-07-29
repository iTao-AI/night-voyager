import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";

import { PlanExecutionWorkspace } from "../../components/plan-execution/PlanExecutionWorkspace";
import { PresentationProvider } from "../../lib/presentation/context";
import { contextFixture, viewFixture } from "./plan-execution-contracts.test";

afterEach(cleanup);

it("renders the current action first without raw hashes or row versions", () => {
  const controller = {
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
});
