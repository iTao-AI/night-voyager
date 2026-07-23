import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { PortfolioRouteAtlas } from "../../components/presentation/PortfolioRouteAtlas";
import { PresentationProvider } from "../../lib/presentation/context";

afterEach(cleanup);

describe("PortfolioRouteAtlas", () => {
  it("renders one canonical accessible route description and closed route data", () => {
    const { container } = render(
      <PresentationProvider>
        <PortfolioRouteAtlas />
      </PresentationProvider>,
    );

    const graphic = screen.getByRole("img", { name: "留学路线比较" });
    expect(container.querySelectorAll(".portfolio-route-copy-veil")).toHaveLength(0);
    expect(container.querySelectorAll(".portfolio-route-label-veil")).toHaveLength(0);
    expect(container.querySelectorAll(".portfolio-route-reason-veil")).toHaveLength(0);
    expect(
      container.querySelectorAll(".portfolio-route-destination rect"),
    ).toHaveLength(0);
    expect(container.querySelector(".portfolio-route-dark-field")).not.toBeNull();
    expect(graphic).toHaveAccessibleDescription(
      "学生希望学习数据科学，预算 30–40 万元。澳大利亚为推荐路线，日本为备选路线，马来西亚暂不推荐。",
    );
    expect(screen.getByText("预算 30–40 万元")).toBeVisible();
    expect(container.querySelectorAll("svg title")).toHaveLength(1);
    expect(container.querySelectorAll("svg desc")).toHaveLength(1);
    expect(container.querySelectorAll("[data-route-stop]")).toHaveLength(6);
    expect(screen.getAllByText("澳大利亚")).toHaveLength(2);
    expect(screen.getAllByText("日本")).toHaveLength(2);
    expect(screen.getAllByText("马来西亚")).toHaveLength(2);
    expect(screen.getAllByText("专业衔接与预算区间更匹配")).toHaveLength(2);
    expect(screen.getAllByText("保留语言与时间准备弹性")).toHaveLength(2);
    expect(screen.getAllByText("当前专业选择不足以支撑优先级")).toHaveLength(2);
    expect(container.querySelector(".portfolio-route-summary")).toHaveAttribute(
      "aria-hidden",
      "true",
    );
  });
});
