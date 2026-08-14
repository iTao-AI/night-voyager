"use client";

import { useEffect, useRef, useState } from "react";

import { usePresentation } from "../../lib/presentation/context";
import type { PresentationCopyKey } from "../../lib/presentation/catalog";
import { WORKFLOW_STAGES, type WorkflowStage } from "../../lib/presentation/journey";
import type { PortfolioStoryScene } from "../../lib/presentation/portfolio";
import { AdvisorWorkspacePreview } from "./AdvisorWorkspacePreview";

const OBSERVED_SCENES = ["confirmed", "route", "outcome"] as const;
type ObservedScene = (typeof OBSERVED_SCENES)[number];

export function PortfolioStory() {
  const { copy } = usePresentation();
  const storyRef = useRef<HTMLElement | null>(null);
  const [scene, setScene] = useState<PortfolioStoryScene>("route");

  useEffect(() => {
    const story = storyRef.current;
    if (!story) return undefined;

    let observer: IntersectionObserver | undefined;
    let frameMode: "desktop" | "static" | undefined;
    const media = typeof window.matchMedia === "function"
      ? window.matchMedia("(prefers-reduced-motion: reduce)")
      : null;

    const connect = () => {
      observer?.disconnect();
      observer = undefined;
      const desktop = window.innerWidth > 860;
      const reducedMotion = media?.matches ?? false;
      const canObserve = typeof window.IntersectionObserver === "function";
      const nextMode: "desktop" | "static" = desktop && !reducedMotion && canObserve ? "desktop" : "static";
      if (frameMode === nextMode) {
        if (nextMode === "static") setScene(reducedMotion ? "outcome" : "route");
        return;
      }
      frameMode = nextMode;

      if (nextMode === "static") {
        setScene(reducedMotion ? "outcome" : "route");
        return;
      }

      setScene("route");
      const sentinels = [...story.querySelectorAll<HTMLElement>("[data-story-sentinel]")];
      observer = new IntersectionObserver(
        (entries) => {
          const visible = entries
            .filter((entry) => entry.isIntersecting)
            .sort((left, right) => right.intersectionRatio - left.intersectionRatio)[0];
          const nextScene = visible?.target.getAttribute("data-story-scene");
          if (isObservedScene(nextScene)) setScene(nextScene);
        },
        { rootMargin: "-26% 0px -54%", threshold: [0, .25, .75, 1] },
      );
      sentinels.forEach((sentinel) => observer?.observe(sentinel));
    };

    const handleResize = () => connect();
    const handleMotionChange = () => connect();
    connect();
    window.addEventListener("resize", handleResize, { passive: true });
    media?.addEventListener?.("change", handleMotionChange);

    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", handleResize);
      media?.removeEventListener?.("change", handleMotionChange);
    };
  }, []);

  return (
    <section id="product" ref={storyRef} className="portfolio-product-story" aria-labelledby="portfolio-product-story-title">
      <div className="portfolio-story-intro">
        <p className="portfolio-section-index">{copy("rootKicker")}</p>
        <h2 id="portfolio-product-story-title">{copy("rootJourneyTitleLineOne")} {copy("rootJourneyTitleLineTwo")}</h2>
        <p>{copy("rootJourneyLead")}</p>
        <ol id="journey" className="portfolio-workflow-list" aria-label={copy("workflowRailLabel")}>
          {WORKFLOW_STAGES.map((stage, index) => (
            <li key={stage} data-stage={stage}>
              <span aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
              <strong>{copy(WORKFLOW_COPY[stage])}</strong>
            </li>
          ))}
        </ol>
      </div>
      <div className="portfolio-story-layout">
        <div className="portfolio-story-chapters">
          <StoryChapter scene="confirmed" title={copy("rootChapterConfirmedTitle")} body={copy("rootChapterConfirmedBody")} />
          <StoryChapter scene="route" title={copy("rootChapterComparisonTitle")} body={copy("rootChapterComparisonBody")} />
          <StoryChapter scene="outcome" title={copy("rootChapterConfirmationTitle")} body={copy("rootChapterConfirmationBody")} />
        </div>
        <div id="route-atlas" className="portfolio-story-frame" aria-label={copy("rootPreviewTitle")}>
          <AdvisorWorkspacePreview scene={scene} />
        </div>
      </div>
    </section>
  );
}

const WORKFLOW_COPY: Record<WorkflowStage, PresentationCopyKey> = {
  consultation_intake: "workflowStageConsultationIntake",
  client_fact_review: "workflowStageClientFactReview",
  route_analysis: "workflowStageRouteAnalysis",
  client_confirmation: "workflowStageClientConfirmation",
  execution_followup: "workflowStageExecutionFollowup",
};

function StoryChapter({ scene, title, body }: { scene: ObservedScene; title: string; body: string }) {
  return (
    <article className="portfolio-story-chapter" data-story-sentinel data-story-scene={scene}>
      <span className="portfolio-story-chapter-marker" aria-hidden="true" />
      <div>
        <h3>{title}</h3>
        <p>{body}</p>
      </div>
    </article>
  );
}

function isObservedScene(value: string | null): value is ObservedScene {
  return value !== null && OBSERVED_SCENES.includes(value as ObservedScene);
}
