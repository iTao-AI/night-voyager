import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { PortfolioJourney } from "../../components/presentation/PortfolioJourney";
import { LocaleSwitch } from "../../components/presentation/LocaleSwitch";
import { PresentationProvider } from "../../lib/presentation/context";

afterEach(cleanup);

describe("PortfolioJourney", () => {
  it("presents one continuous ordered Chinese journey and native boundary", () => {
    const { container } = render(
      <PresentationProvider>
        <PortfolioJourney />
      </PresentationProvider>,
    );

    expect(
      screen.getByRole("heading", {
        level: 2,
        name: "先看清自己 再决定去哪里",
      }),
    ).toBeInTheDocument();
    expect(
      screen
        .getAllByRole("heading", { level: 3 })
        .map(({ textContent }) => textContent),
    ).toEqual(["理解你的条件", "看懂理由与取舍", "形成可执行计划"]);
    expect(container.querySelector("#journey > ol")).toHaveClass(
      "portfolio-journey-track",
    );
    expect(container.querySelectorAll(".portfolio-journey-track > li")).toHaveLength(3);
    expect(container.querySelector("details > summary")).toHaveTextContent(
      "公开演示边界",
    );
    expect(screen.getByRole("link", { name: "决策依据" })).toHaveAttribute(
      "href",
      "/demo",
    );
  });

  it("keeps the same journey hierarchy in explicit English", () => {
    render(
      <PresentationProvider>
        <LocaleSwitch />
        <PortfolioJourney />
      </PresentationProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "English" }));

    expect(
      screen.getByRole("heading", {
        level: 2,
        name: "Understand yourself first then decide where to go",
      }),
    ).toBeInTheDocument();
    expect(
      screen
        .getAllByRole("heading", { level: 3 })
        .map(({ textContent }) => textContent),
    ).toEqual([
      "Understand your conditions",
      "See the reasons and trade-offs",
      "Form an actionable plan",
    ]);
  });
});
