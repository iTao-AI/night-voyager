import { describe, expect, it, vi } from "vitest";

import {
  DEFAULT_PRESENTATION_LOCALE,
  PRESENTATION_LOCALE_STORAGE_KEY,
  SUPPORTED_PRESENTATION_LOCALES,
  isPresentationLocale,
  readPresentationLocale,
  writePresentationLocale,
} from "../../lib/presentation/locales";

describe("presentation locale contract", () => {
  it("accepts exactly zh-CN and en and defaults to Chinese", () => {
    expect(SUPPORTED_PRESENTATION_LOCALES).toEqual(["zh-CN", "en"]);
    expect(DEFAULT_PRESENTATION_LOCALE).toBe("zh-CN");
    expect(PRESENTATION_LOCALE_STORAGE_KEY).toBe(
      "night-voyager:presentation-locale:v1",
    );
    expect(isPresentationLocale("zh-CN")).toBe(true);
    expect(isPresentationLocale("en")).toBe(true);

    for (const value of [undefined, null, "", "zh", "zh-cn", "en-US", "en,zh-CN"]) {
      expect(isPresentationLocale(value)).toBe(false);
    }
  });

  it("uses Chinese for a missing preference", () => {
    const storage = { getItem: vi.fn(() => null), removeItem: vi.fn() };

    expect(readPresentationLocale(storage)).toBe("zh-CN");
    expect(storage.removeItem).not.toHaveBeenCalled();
  });

  it.each(["zh", "zh-cn", "en-US", "en,zh-CN", " EN "])(
    "removes invalid preference %s and falls back to Chinese",
    (value) => {
      const storage = { getItem: vi.fn(() => value), removeItem: vi.fn() };

      expect(readPresentationLocale(storage)).toBe("zh-CN");
      expect(storage.removeItem).toHaveBeenCalledWith(PRESENTATION_LOCALE_STORAGE_KEY);
    },
  );

  it("fails closed to Chinese when storage read or cleanup throws", () => {
    const readFailure = {
      getItem: vi.fn(() => {
        throw new Error("blocked");
      }),
      removeItem: vi.fn(),
    };
    const cleanupFailure = {
      getItem: vi.fn(() => "invalid"),
      removeItem: vi.fn(() => {
        throw new Error("blocked");
      }),
    };

    expect(() => readPresentationLocale(readFailure)).not.toThrow();
    expect(readPresentationLocale(readFailure)).toBe("zh-CN");
    expect(() => readPresentationLocale(cleanupFailure)).not.toThrow();
    expect(readPresentationLocale(cleanupFailure)).toBe("zh-CN");
  });

  it("persists only a valid explicit choice without leaking storage failures", () => {
    const storage = { setItem: vi.fn() };
    expect(writePresentationLocale(storage, "en")).toBe(true);
    expect(storage.setItem).toHaveBeenCalledWith(
      PRESENTATION_LOCALE_STORAGE_KEY,
      "en",
    );

    const failure = {
      setItem: vi.fn(() => {
        throw new Error("blocked");
      }),
    };
    expect(writePresentationLocale(failure, "zh-CN")).toBe(false);
  });
});
