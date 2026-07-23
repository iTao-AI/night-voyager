"use client";

import { usePresentation } from "../../lib/presentation/context";
import { PORTFOLIO_ROUTE_STOPS } from "../../lib/presentation/portfolio";

const DESTINATIONS = {
  australia: { x: 770, y: 118, labelY: 95, reasonY: 124 },
  japan: { x: 808, y: 326, labelY: 303, reasonY: 332 },
  malaysia: { x: 774, y: 528, labelY: 505, reasonY: 534 },
} as const;

export function PortfolioRouteAtlas() {
  const { copy } = usePresentation();

  return (
    <section id="route-atlas" className="portfolio-route-atlas">
      <svg
        className="portfolio-atlas-graphic"
        viewBox="0 0 920 680"
        role="img"
        aria-labelledby="portfolio-atlas-title"
        aria-describedby="portfolio-atlas-description"
        focusable="false"
      >
        <title id="portfolio-atlas-title">{copy("rootRouteAtlasTitle")}</title>
        <desc id="portfolio-atlas-description">
          {copy("rootRouteAtlasDescription")}
        </desc>
        <defs>
          <linearGradient
            id="portfolio-route-gradient"
            x1="0"
            y1="1"
            x2="1"
            y2="0"
          >
            <stop offset="0%" stopColor="#fff3ce" />
            <stop offset="62%" stopColor="#e9c675" />
            <stop offset="100%" stopColor="#9fc9c8" />
          </linearGradient>
          <filter
            id="portfolio-route-glow"
            x="-40%"
            y="-40%"
            width="180%"
            height="180%"
          >
            <feGaussianBlur stdDeviation="5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <g className="portfolio-atlas-origin">
          <text x="120" y="555" className="portfolio-svg-kicker">
            {copy("rootOriginLabel")}
          </text>
          <text x="120" y="590" className="portfolio-svg-origin">
            {copy("rootOriginField")}
          </text>
          <line x1="160" y1="604" x2="160" y2="632" />
          <text
            x="160"
            y="658"
            textAnchor="middle"
            className="portfolio-svg-budget"
          >
            {copy("rootOriginBudget")}
          </text>
        </g>

        <path
          className="portfolio-route-halo"
          d="M162 632C282 606 340 550 420 476S520 356 594 300"
        />
        <path
          className="portfolio-route-path portfolio-route-main"
          pathLength="1"
          d="M162 632C282 606 340 550 420 476S520 356 594 300"
        />
        <path
          className="portfolio-route-path portfolio-route-branch portfolio-route-branch-primary"
          pathLength="1"
          d="M594 300C656 242 704 174 770 118"
        />
        <path
          className="portfolio-route-path portfolio-route-branch"
          pathLength="1"
          d="M594 300C660 314 718 322 808 326"
        />
        <path
          className="portfolio-route-path portfolio-route-branch portfolio-route-branch-muted"
          pathLength="1"
          d="M594 300C652 382 710 456 774 528"
        />
        <circle
          className="portfolio-route-origin-node"
          cx="162"
          cy="632"
          r="5"
        />
        <circle
          className="portfolio-route-junction"
          cx="594"
          cy="300"
          r="7"
        />

        {PORTFOLIO_ROUTE_STOPS.map((stop) => {
          const destination = DESTINATIONS[stop.id];
          return (
            <g
              key={stop.id}
              className="portfolio-route-destination"
              data-route-stop={stop.id}
              data-emphasis={stop.emphasis}
            >
              <circle cx={destination.x} cy={destination.y} r="5" />
              <text
                x="882"
                y={destination.labelY}
                textAnchor="end"
                className="portfolio-svg-route-label"
              >
                <tspan>{copy(stop.countryKey)}</tspan>
                <tspan> · {copy(stop.statusKey)}</tspan>
              </text>
              <text
                x="882"
                y={destination.reasonY}
                textAnchor="end"
                className="portfolio-svg-route-reason"
              >
                {copy(stop.reasonKey)}
              </text>
            </g>
          );
        })}
      </svg>

      <ol
        className="portfolio-route-summary"
        aria-label={copy("rootRouteSummaryLabel")}
        aria-hidden="true"
      >
        {PORTFOLIO_ROUTE_STOPS.map((stop, index) => (
          <li
            key={stop.id}
            data-route-stop={stop.id}
            data-emphasis={stop.emphasis}
          >
            <span>{String(index + 1).padStart(2, "0")}</span>
            <strong>{copy(stop.countryKey)}</strong>
            <em>{copy(stop.statusKey)}</em>
            <small>{copy(stop.reasonKey)}</small>
          </li>
        ))}
      </ol>
    </section>
  );
}
