import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useEffect } from "react";
import { renderToString } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  PresentationProvider,
  usePresentation,
} from "../../lib/presentation/context";

function Probe({ onMount = () => undefined }: { onMount?: () => void }) {
  const { locale, copy, setLocale } = usePresentation();
  useEffect(onMount, [onMount]);
  return (
    <div>
      <span>{locale}</span>
      <span>{copy("productPromise")}</span>
      <button type="button" onClick={() => setLocale(locale === "zh-CN" ? "en" : "zh-CN")}>
        switch
      </button>
    </div>
  );
}

beforeEach(() => {
  localStorage.clear();
  document.documentElement.lang = "zh-CN";
  document.title = "Night Voyager｜把家庭事实变成可追溯的留学决策与行动计划";
  document.head.innerHTML = '<meta name="description" content="中文默认描述">';
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("PresentationProvider", () => {
  it("server-renders deterministic Chinese without browser negotiation", () => {
    const html = renderToString(
      <PresentationProvider>
        <Probe />
      </PresentationProvider>,
    );
    expect(html).toContain("zh-CN");
    expect(html).toContain("把家庭事实变成可追溯的留学决策与行动计划");
    expect(html).not.toContain("navigator.language");
  });

  it("hydrates a valid English preference and updates document presentation", async () => {
    localStorage.setItem("night-voyager:presentation-locale:v1", "en");
    render(<PresentationProvider><Probe /></PresentationProvider>);

    await waitFor(() => expect(screen.getByText("en")).toBeInTheDocument());
    expect(document.documentElement.lang).toBe("en");
    expect(document.title).toBe("Night Voyager | Traceable study-abroad decisions");
    expect(document.querySelector('meta[name="description"]')).toHaveAttribute(
      "content",
      "A local synthetic portfolio workflow from confirmed family facts to a reviewed plan and receipt.",
    );
  });

  it("removes invalid preference and keeps Chinese usable", async () => {
    localStorage.setItem("night-voyager:presentation-locale:v1", "en-US");
    render(<PresentationProvider><Probe /></PresentationProvider>);

    await waitFor(() => expect(screen.getByText("zh-CN")).toBeInTheDocument());
    expect(localStorage.getItem("night-voyager:presentation-locale:v1")).toBeNull();
    expect(document.documentElement.lang).toBe("zh-CN");
  });

  it("switches only presentation state and preserves mounted children", () => {
    const onMount = vi.fn();
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    const pushState = vi.spyOn(history, "pushState");
    const replaceState = vi.spyOn(history, "replaceState");

    render(<PresentationProvider><Probe onMount={onMount} /></PresentationProvider>);
    fireEvent.click(screen.getByRole("button", { name: "switch" }));

    expect(screen.getByText("en")).toBeInTheDocument();
    expect(onMount).toHaveBeenCalledTimes(1);
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(pushState).not.toHaveBeenCalled();
    expect(replaceState).not.toHaveBeenCalled();
    expect(localStorage.getItem("night-voyager:presentation-locale:v1")).toBe("en");
  });

  it("keeps the selected presentation usable when storage writes fail", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    render(<PresentationProvider><Probe /></PresentationProvider>);

    fireEvent.click(screen.getByRole("button", { name: "switch" }));
    expect(screen.getByText("en")).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("en");
  });
});
