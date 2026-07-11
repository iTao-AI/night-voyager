import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Home from "./page";

describe("bootstrap page", () => {
  it("labels the current milestone without claiming product behavior", () => {
    render(<Home />);
    expect(screen.getByRole("heading", { name: "Night Voyager" })).toBeInTheDocument();
    expect(screen.getByText(/Product decision workflows are intentionally not implemented/)).toBeInTheDocument();
  });
});
