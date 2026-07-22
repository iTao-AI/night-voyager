"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { usePresentation } from "../../lib/presentation/context";
import type { PresentationCopyKey } from "../../lib/presentation/catalog";
import { LocaleSwitch } from "./LocaleSwitch";

export function PresentationShell({
  children,
  contextKey,
  mainId = "main-content",
}: {
  children: ReactNode;
  contextKey: PresentationCopyKey;
  mainId?: string;
}) {
  const { copy } = usePresentation();
  return (
    <div className="presentation-shell">
      <a className="skip-link" href={`#${mainId}`}>
        {copy("skipToMain")}
      </a>
      <header className="presentation-header">
        <div>
          <Link className="product-mark" href="/">
            {copy("productName")}
          </Link>
          <p className="route-context">{copy(contextKey)}</p>
        </div>
        <div className="presentation-controls">
          <LocaleSwitch />
          <span className="synthetic-label">{copy("syntheticLabel")}</span>
        </div>
      </header>
      <main id={mainId} tabIndex={-1}>
        {children}
      </main>
      <footer className="presentation-footer">
        <p>{copy("footerBoundary")}</p>
      </footer>
    </div>
  );
}
