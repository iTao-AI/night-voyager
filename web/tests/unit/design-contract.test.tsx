import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import DemoPage from "../../app/demo/page";

afterEach(cleanup);

describe("M5 connected demo design contract", () => {
  it("starts fail closed with one connected advisor action", () => {
    render(<DemoPage />);

    expect(screen.getByText(/synthetic demo/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Connected advisor-to-family demo/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Start advisor walkthrough/i })).toBeEnabled();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });
});
