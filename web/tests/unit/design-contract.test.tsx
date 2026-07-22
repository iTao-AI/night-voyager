import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import DemoPage from "../../app/demo/page";
import { PresentationProvider } from "../../lib/presentation/context";

afterEach(cleanup);

describe("M5 connected demo design contract", () => {
  it("starts fail closed with one connected advisor action", () => {
    render(<PresentationProvider><DemoPage /></PresentationProvider>);

    expect(screen.getByText("本地合成演示")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "顾问到家庭的决策流程" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "开始顾问流程" })).toBeEnabled();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });
});
