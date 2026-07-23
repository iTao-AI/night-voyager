const STARS = [
  { x: "11%", y: "14%", size: "2px", delay: "-1.2s", duration: "5.8s" },
  { x: "18%", y: "36%", size: "1px", delay: "-3.4s", duration: "6.6s" },
  { x: "29%", y: "18%", size: "2px", delay: "-2.1s", duration: "7.2s" },
  { x: "37%", y: "31%", size: "1px", delay: "-4.6s", duration: "5.4s" },
  { x: "46%", y: "11%", size: "2px", delay: "-.8s", duration: "6.3s" },
  { x: "54%", y: "26%", size: "1px", delay: "-5.1s", duration: "7.6s" },
  { x: "63%", y: "16%", size: "2px", delay: "-2.8s", duration: "5.9s" },
  { x: "71%", y: "34%", size: "1px", delay: "-4.1s", duration: "6.9s" },
  { x: "79%", y: "12%", size: "2px", delay: "-1.7s", duration: "7.4s" },
  { x: "87%", y: "28%", size: "1px", delay: "-3.7s", duration: "5.6s" },
  { x: "92%", y: "19%", size: "2px", delay: "-.4s", duration: "6.2s" },
  { x: "68%", y: "48%", size: "1px", delay: "-5.5s", duration: "7.1s" },
] as const;

export function PortfolioBackdrop() {
  return (
    <div className="portfolio-backdrop" aria-hidden="true">
      <picture>
        <source
          type="image/avif"
          srcSet="/portfolio/night-voyager-voyage-960.avif 960w, /portfolio/night-voyager-voyage-1680.avif 1672w"
          sizes="100vw"
        />
        <source
          type="image/webp"
          srcSet="/portfolio/night-voyager-voyage-960.webp 960w, /portfolio/night-voyager-voyage-1680.webp 1672w"
          sizes="100vw"
        />
        <img
          src="/portfolio/night-voyager-voyage-1680.webp"
          width="1672"
          height="941"
          alt=""
          loading="eager"
          fetchPriority="high"
          decoding="async"
        />
      </picture>
      <div className="portfolio-star-field">
        {STARS.map((star) => (
          <span
            key={`${star.x}-${star.y}`}
            className="portfolio-star"
            style={{
              left: star.x,
              top: star.y,
              width: star.size,
              height: star.size,
              animationDelay: star.delay,
              animationDuration: star.duration,
            }}
          />
        ))}
      </div>
    </div>
  );
}
