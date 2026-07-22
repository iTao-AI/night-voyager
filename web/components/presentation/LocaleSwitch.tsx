"use client";

import { usePresentation } from "../../lib/presentation/context";

export function LocaleSwitch() {
  const { locale, copy, setLocale } = usePresentation();
  return (
    <div
      className="locale-switch"
      role="group"
      aria-label={copy("localeControlLabel")}
    >
      <button
        type="button"
        aria-pressed={locale === "zh-CN"}
        onClick={() => setLocale("zh-CN")}
      >
        {copy("localeChinese")}
      </button>
      <span aria-hidden="true">/</span>
      <button
        type="button"
        aria-pressed={locale === "en"}
        onClick={() => setLocale("en")}
      >
        {copy("localeEnglish")}
      </button>
    </div>
  );
}
