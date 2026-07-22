"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { getPresentationCopy, type PresentationCopyKey } from "./catalog";
import {
  DEFAULT_PRESENTATION_LOCALE,
  readPresentationLocale,
  writePresentationLocale,
  type PresentationLocale,
} from "./locales";

interface PresentationContextValue {
  locale: PresentationLocale;
  copy(key: PresentationCopyKey): string;
  setLocale(locale: PresentationLocale): void;
}

const PresentationContext = createContext<PresentationContextValue | null>(null);

function readBrowserPresentationLocale(): PresentationLocale {
  try {
    return readPresentationLocale(window.localStorage);
  } catch {
    return DEFAULT_PRESENTATION_LOCALE;
  }
}

function writeBrowserPresentationLocale(locale: PresentationLocale): void {
  try {
    writePresentationLocale(window.localStorage, locale);
  } catch {
    // Storage acquisition and writes are presentation-only and fail closed.
  }
}

function applyDocumentPresentation(locale: PresentationLocale): void {
  document.documentElement.lang = locale;
  document.title = getPresentationCopy(locale, "documentTitle");
  document
    .querySelector('meta[name="description"]')
    ?.setAttribute("content", getPresentationCopy(locale, "documentDescription"));
}

export function PresentationProvider({ children }: { children: ReactNode }) {
  const [locale, updateLocale] = useState<PresentationLocale>(
    DEFAULT_PRESENTATION_LOCALE,
  );

  useEffect(() => {
    const stored = readBrowserPresentationLocale();
    applyDocumentPresentation(stored);
    let active = true;
    queueMicrotask(() => {
      if (active) updateLocale(stored);
    });
    return () => {
      active = false;
    };
  }, []);

  const setLocale = useCallback((nextLocale: PresentationLocale) => {
    updateLocale(nextLocale);
    writeBrowserPresentationLocale(nextLocale);
    applyDocumentPresentation(nextLocale);
  }, []);

  const copy = useCallback(
    (key: PresentationCopyKey) => getPresentationCopy(locale, key),
    [locale],
  );
  const value = useMemo(
    () => ({ locale, copy, setLocale }),
    [copy, locale, setLocale],
  );

  return (
    <PresentationContext.Provider value={value}>
      {children}
    </PresentationContext.Provider>
  );
}

export function usePresentation(): PresentationContextValue {
  const value = useContext(PresentationContext);
  if (value === null) {
    throw new Error("PresentationProvider is required");
  }
  return value;
}
