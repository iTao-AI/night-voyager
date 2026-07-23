import { expect, test } from "@playwright/test";

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
