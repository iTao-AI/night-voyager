import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import DemoPage from "../../app/demo/page";

afterEach(cleanup);

describe("M1 demo design contract", () => {
  it("makes the synthetic advisor gate understandable before any family decision", () => {
    render(<DemoPage />);

    expect(screen.getByText(/synthetic fixture proof mode/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /advisor ledger/i })).toBeInTheDocument();

    const currentStage = screen.getByTestId("current-stage");
    expect(within(currentStage).getByText(/advisor approval required/i)).toBeInTheDocument();
    expect(within(currentStage).getByText(/evidence gap/i)).toBeInTheDocument();
    expect(within(currentStage).getByRole("link", { name: /review evidence/i })).toHaveAttribute("href", "#evidence");
  });

  it("separates family_review and decided into explicit before and after frames", () => {
    render(<DemoPage />);

    const familyReview = screen.getByTestId("frame-family-review");
    const decided = screen.getByTestId("frame-decided");

    expect(within(familyReview).getByText(/family_review/i)).toBeInTheDocument();
    expect(within(familyReview).getByRole("heading", { name: /family decision brief/i })).toBeInTheDocument();
    expect(within(familyReview).getByRole("button", { name: /confirm japan route/i })).toBeDisabled();
    expect(within(familyReview).getByText(/disabled until the family confirms/i)).toBeInTheDocument();

    expect(within(decided).getByText(/decided/i)).toBeInTheDocument();
    expect(within(decided).getByRole("heading", { name: /decision receipt/i })).toBeInTheDocument();
    expect(within(decided).getByText(/receipt nv-fixture-024/i)).toBeInTheDocument();
    expect(within(decided).getByText(/reconnect safely/i)).toBeInTheDocument();
  });

  it("renders a semantic country comparison and a blocking Malaysia negative path", () => {
    render(<DemoPage />);

    expect(screen.getByRole("table", { name: /route evidence comparison/i })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: /choose a country/i })).toBeInTheDocument();

    const malaysia = screen.getByTestId("malaysia-blocked");
    expect(within(malaysia).getByRole("heading", { name: /malaysia remains blocked/i })).toBeInTheDocument();
    expect(within(malaysia).getByText(/evidence gap/i)).toBeInTheDocument();
    expect(within(malaysia).getByRole("button", { name: /choose malaysia/i })).toBeDisabled();
  });

  it("keeps technical execution detail secondary and disclosure-based", () => {
    render(<DemoPage />);

    const details = screen.getByText(/fixture execution details/i).closest("details");
    expect(details).not.toBeNull();
    expect(details).not.toHaveAttribute("open");
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });
});
