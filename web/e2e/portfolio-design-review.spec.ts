import { expect, test, type Page } from "@playwright/test";

const DESKTOP_ROUTE_TEXT =
  ".portfolio-route-destination .portfolio-svg-route-label, " +
  ".portfolio-route-destination .portfolio-svg-route-reason";
const MOBILE_ROUTE_TEXT =
  ".portfolio-route-summary li strong, " +
  ".portfolio-route-summary li em, " +
  ".portfolio-route-summary li small";

function relativeLuminance(rgb: readonly number[]) {
  const [red, green, blue] = rgb.map((value) => {
    const channel = value / 255;
    return channel <= 0.04045
      ? channel / 12.92
      : ((channel + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

function contrastRatio(foreground: readonly number[], background: readonly number[]) {
  const foregroundLuminance = relativeLuminance(foreground);
  const backgroundLuminance = relativeLuminance(background);
  return (
    (Math.max(foregroundLuminance, backgroundLuminance) + 0.05) /
    (Math.min(foregroundLuminance, backgroundLuminance) + 0.05)
  );
}

async function waitForPortfolioBackdrop(page: Page) {
  await expect
    .poll(() =>
      page
        .locator(".portfolio-backdrop img")
        .evaluate(
          (image) =>
            (image as HTMLImageElement).complete &&
            (image as HTMLImageElement).naturalWidth > 0,
        ),
    )
    .toBe(true);
}

async function renderedTextContrast(
  page: Page,
  selector: string,
  paintProperty: "color" | "fill",
) {
  const targets = await page.locator(selector).evaluateAll(
    (elements, property) =>
      elements
        .map((element) => {
          const rect = element.getBoundingClientRect();
          const values = (
            property === "fill"
              ? getComputedStyle(element).fill
              : getComputedStyle(element).color
          ).match(/[\d.]+/g);
          if (!values || values.length < 3 || rect.width === 0 || rect.height === 0) {
            return null;
          }

          let inheritedOpacity = 1;
          for (
            let current: Element | null = element;
            current;
            current = current.parentElement
          ) {
            inheritedOpacity *= Number.parseFloat(
              getComputedStyle(current).opacity || "1",
            );
          }

          const routeStop =
            element.closest("[data-route-stop]")?.getAttribute("data-route-stop") ??
            "unknown";
          const role = element.matches(
            ".portfolio-svg-route-label, strong",
          )
            ? "label"
            : element.matches("em")
              ? "status"
              : "reason";
          const supportingVeil = element
            .closest(".portfolio-route-destination")
            ?.querySelector(
              role === "label"
                ? ".portfolio-route-label-veil"
                : ".portfolio-route-reason-veil",
            );
          const supportingVeilRect = supportingVeil?.getBoundingClientRect();

          return {
            alpha: (values[3] ? Number(values[3]) : 1) * inheritedOpacity,
            foreground: values.slice(0, 3).map(Number),
            height: rect.height,
            name: `${routeStop}-${role}`,
            width: rect.width,
            x: rect.left + window.scrollX,
            y: rect.top + window.scrollY,
            supportingVeil: supportingVeilRect
              ? {
                  height: supportingVeilRect.height,
                  width: supportingVeilRect.width,
                  x: supportingVeilRect.left + window.scrollX,
                  y: supportingVeilRect.top + window.scrollY,
                }
              : null,
          };
        })
        .filter((target) => target !== null),
    paintProperty,
  );

  expect(targets.length).toBeGreaterThan(0);
  const screenshot = await page.screenshot({
    animations: "disabled",
    fullPage: true,
    scale: "css",
    style: `${selector} { visibility: hidden !important; }`,
  });

  return page.evaluate(
    async ({ imageUrl, sampledTargets }) => {
      const image = new Image();
      image.src = imageUrl;
      await image.decode();

      const canvas = document.createElement("canvas");
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      const context = canvas.getContext("2d", { willReadFrequently: true });
      if (!context) {
        throw new Error("Canvas 2D context unavailable");
      }
      context.drawImage(image, 0, 0);

      const luminance = (rgb: readonly number[]) => {
        const [red, green, blue] = rgb.map((value) => {
          const channel = value / 255;
          return channel <= 0.04045
            ? channel / 12.92
            : ((channel + 0.055) / 1.055) ** 2.4;
        });
        return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
      };
      const ratio = (foreground: readonly number[], background: readonly number[]) => {
        const foregroundLuminance = luminance(foreground);
        const backgroundLuminance = luminance(background);
        return (
          (Math.max(foregroundLuminance, backgroundLuminance) + 0.05) /
          (Math.min(foregroundLuminance, backgroundLuminance) + 0.05)
        );
      };

      return sampledTargets.map((target) => {
        const left = Math.max(0, Math.floor(target.x));
        const top = Math.max(0, Math.floor(target.y));
        const width = Math.max(
          1,
          Math.min(canvas.width - left, Math.ceil(target.width)),
        );
        const height = Math.max(
          1,
          Math.min(canvas.height - top, Math.ceil(target.height)),
        );
        const pixels = context.getImageData(left, top, width, height).data;
        let minimum = Number.POSITIVE_INFINITY;
        let minimumAt = { x: left, y: top };
        let minimumBackground = [0, 0, 0];
        let total = 0;
        let count = 0;

        for (let offset = 0; offset < pixels.length; offset += 4) {
          const background = [
            pixels[offset],
            pixels[offset + 1],
            pixels[offset + 2],
          ];
          const foreground = target.foreground.map(
            (channel, index) =>
              channel * target.alpha + background[index] * (1 - target.alpha),
          );
          const measured = ratio(foreground, background);
          if (measured < minimum) {
            const pixelIndex = offset / 4;
            minimum = measured;
            minimumAt = {
              x: left + (pixelIndex % width),
              y: top + Math.floor(pixelIndex / width),
            };
            minimumBackground = background;
          }
          total += measured;
          count += 1;
        }

        return {
          average: total / count,
          minimum,
          minimumAt,
          minimumBackground,
          name: target.name,
          samples: count,
          targetBounds: {
            height: target.height,
            width: target.width,
            x: target.x,
            y: target.y,
          },
          supportingVeil: target.supportingVeil,
        };
      });
    },
    {
      imageUrl: `data:image/png;base64,${screenshot.toString("base64")}`,
      sampledTargets: targets,
    },
  );
}

async function expectReadableRouteText(
  page: Page,
  selector: string,
  paintProperty: "color" | "fill",
  viewport: string,
  locale: string,
) {
  const measurements = await renderedTextContrast(page, selector, paintProperty);
  for (const measurement of measurements) {
    expect.soft(
      measurement.minimum,
      `${viewport} ${locale} ${measurement.name}: ` +
        `min=${measurement.minimum.toFixed(2)} ` +
        `avg=${measurement.average.toFixed(2)} ` +
        `background=${measurement.minimumBackground.join(",")} ` +
        `at=${measurement.minimumAt.x},${measurement.minimumAt.y} ` +
        `bounds=${measurement.targetBounds.x.toFixed(0)},` +
        `${measurement.targetBounds.y.toFixed(0)},` +
        `${measurement.targetBounds.width.toFixed(0)}x` +
        `${measurement.targetBounds.height.toFixed(0)} ` +
        `veil=${
          measurement.supportingVeil
            ? `${measurement.supportingVeil.x.toFixed(0)},` +
              `${measurement.supportingVeil.y.toFixed(0)},` +
              `${measurement.supportingVeil.width.toFixed(0)}x` +
              `${measurement.supportingVeil.height.toFixed(0)}`
            : "none"
        } ` +
        `samples=${measurement.samples}`,
    ).toBeGreaterThanOrEqual(4.5);
  }
}

test("keeps the primary portfolio action readable in both locales", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");

  for (const locale of ["zh-CN", "en"] as const) {
    if (locale === "en") {
      await page.getByRole("button", { name: "English", exact: true }).click();
      await expect(page.locator("html")).toHaveAttribute("lang", "en");
    }

    const colors = await page
      .locator(".portfolio-button-primary")
      .evaluate((element) => {
        const style = getComputedStyle(element);
        const parseRgb = (value: string) =>
          (value.match(/[\d.]+/g) ?? []).slice(0, 3).map(Number);
        return {
          foreground: parseRgb(style.color),
          background: parseRgb(style.backgroundColor),
        };
      });

    expect(colors.foreground).toHaveLength(3);
    expect(colors.background).toHaveLength(3);
    expect(contrastRatio(colors.foreground, colors.background)).toBeGreaterThanOrEqual(
      4.5,
    );
  }
});

test("keeps every desktop route label and reason readable over the rendered background", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");
  await waitForPortfolioBackdrop(page);

  for (const locale of ["zh-CN", "en"] as const) {
    if (locale === "en") {
      await page.getByRole("button", { name: "English", exact: true }).click();
      await expect(page.locator("html")).toHaveAttribute("lang", "en");
    }
    await expectReadableRouteText(
      page,
      DESKTOP_ROUTE_TEXT,
      "fill",
      "1440x1000",
      locale,
    );
  }
});

test("keeps every mobile route label, status, and reason readable over the rendered background", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await waitForPortfolioBackdrop(page);

  for (const locale of ["zh-CN", "en"] as const) {
    if (locale === "en") {
      await page.getByRole("button", { name: "English", exact: true }).click();
      await expect(page.locator("html")).toHaveAttribute("lang", "en");
    }
    await expectReadableRouteText(
      page,
      MOBILE_ROUTE_TEXT,
      "color",
      "390x844",
      locale,
    );
  }
});
