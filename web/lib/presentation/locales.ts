export const SUPPORTED_PRESENTATION_LOCALES = ["zh-CN", "en"] as const;
export type PresentationLocale = (typeof SUPPORTED_PRESENTATION_LOCALES)[number];

export const DEFAULT_PRESENTATION_LOCALE: PresentationLocale = "zh-CN";
export const PRESENTATION_LOCALE_STORAGE_KEY =
  "night-voyager:presentation-locale:v1";

interface LocaleReadableStorage {
  getItem(key: string): string | null;
  removeItem(key: string): void;
}

interface LocaleWritableStorage {
  setItem(key: string, value: string): void;
}

export function isPresentationLocale(value: unknown): value is PresentationLocale {
  return value === "zh-CN" || value === "en";
}

export function readPresentationLocale(storage: LocaleReadableStorage): PresentationLocale {
  try {
    const value = storage.getItem(PRESENTATION_LOCALE_STORAGE_KEY);
    if (value === null) return DEFAULT_PRESENTATION_LOCALE;
    if (isPresentationLocale(value)) return value;
    try {
      storage.removeItem(PRESENTATION_LOCALE_STORAGE_KEY);
    } catch {
      // A blocked cleanup must not prevent the deterministic Chinese fallback.
    }
  } catch {
    // Storage access is presentation-only and must fail closed without surfacing.
  }
  return DEFAULT_PRESENTATION_LOCALE;
}

export function writePresentationLocale(
  storage: LocaleWritableStorage,
  locale: PresentationLocale,
): boolean {
  try {
    storage.setItem(PRESENTATION_LOCALE_STORAGE_KEY, locale);
    return true;
  } catch {
    return false;
  }
}
