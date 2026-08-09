"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { usePresentation } from "../../lib/presentation/context";
import { LocaleSwitch } from "./LocaleSwitch";

export function PortfolioShell({ children }: { children: ReactNode }) {
  const { copy } = usePresentation();

  return (
    <div className="advisor-portfolio-shell">
      <a className="skip-link portfolio-skip-link" href="#main-content">
        {copy("skipToMain")}
      </a>
      <header className="portfolio-header">
        <div className="portfolio-header-inner">
          <Link className="portfolio-brand" href="/">
            <span className="portfolio-brand-mark" aria-hidden="true"><span /></span>
            <span>{copy("productName")}</span>
          </Link>
          <p className="portfolio-category">{copy("workspaceCategory")}</p>
          <nav className="portfolio-primary-navigation" aria-label={copy("rootNavigationLabel")}>
            <a href="#journey">{copy("rootNavApproach")}</a>
            <a href="#route-atlas">{copy("rootNavRoutes")}</a>
            <a href="#portfolio-engineering-title">{copy("rootNavEvidence")}</a>
          </nav>
          <div className="portfolio-header-actions">
            <LocaleSwitch />
            <Link className="portfolio-header-action" href="/demo/collaboration">
              {copy("rootHeaderAction")}
            </Link>
          </div>
        </div>
      </header>
      <main id="main-content" tabIndex={-1}>
        {children}
      </main>
      <footer className="portfolio-footer">
        <p>{copy("footerBoundary")}</p>
      </footer>
    </div>
  );
}
