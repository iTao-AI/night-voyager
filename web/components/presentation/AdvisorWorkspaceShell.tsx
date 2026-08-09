"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import type { PresentationCopyKey } from "../../lib/presentation/catalog";
import { usePresentation } from "../../lib/presentation/context";
import type { WorkflowProofSegment, WorkflowStage } from "../../lib/presentation/journey";
import { LocaleSwitch } from "./LocaleSwitch";
import { WorkflowRail } from "./WorkflowRail";

type AdvisorWorkspaceShellProps = {
  activeRole: "student" | "parent" | "advisor" | null;
  children: ReactNode;
  contextKey: PresentationCopyKey;
  currentStage: WorkflowStage | null;
  mainId: string;
  proofSegment: WorkflowProofSegment;
  status: ReactNode;
  supportingEvidence?: ReactNode;
  technicalEvidence?: ReactNode;
  titleKey: PresentationCopyKey;
};

const ROLE_COPY: Record<NonNullable<AdvisorWorkspaceShellProps["activeRole"]>, PresentationCopyKey> = {
  advisor: "roleAdvisor",
  student: "roleStudent",
  parent: "roleParent",
};

const PROOF_COPY: Record<WorkflowProofSegment, PresentationCopyKey> = {
  connected_same_case: "proofSegmentConnectedSameCase",
  independent_execution_scenario: "proofSegmentIndependentExecutionScenario",
};

export function AdvisorWorkspaceShell({
  activeRole,
  children,
  contextKey,
  currentStage,
  mainId,
  proofSegment,
  status,
  supportingEvidence,
  technicalEvidence,
  titleKey,
}: AdvisorWorkspaceShellProps) {
  const { copy } = usePresentation();

  return (
    <div className="advisor-workspace-shell" data-proof-segment={proofSegment}>
      <a className="skip-link workspace-skip-link" href={`#${mainId}`}>
        {copy("skipToMain")}
      </a>
      <header className="workspace-header">
        <div className="workspace-header-inner">
          <Link className="workspace-brand" href="/">
            <span className="workspace-brand-mark" aria-hidden="true"><span /></span>
            <span>{copy("productName")}</span>
          </Link>
          <p className="workspace-category">{copy("workspaceCategory")}</p>
          <div className="workspace-header-controls">
            <LocaleSwitch />
            <span className="workspace-synthetic-label">{copy("syntheticLabel")}</span>
          </div>
        </div>
      </header>
      <div className="workspace-context-bar" aria-label={copy("workspaceCaseContext")}>
        <div>
          <p className="workspace-context-label">{copy(contextKey)}</p>
          <p className="workspace-boundary">{copy("workspaceSyntheticBoundary")}</p>
        </div>
        <dl className="workspace-context-facts">
          <div>
            <dt>{copy("workspaceCurrentStage")}</dt>
            <dd>{currentStage ? copy(STAGE_COPY[currentStage]) : copy("statusUnavailable")}</dd>
          </div>
          <div>
            <dt>{copy("workspaceActiveRole")}</dt>
            <dd>{activeRole ? copy(ROLE_COPY[activeRole]) : copy("statusUnavailable")}</dd>
          </div>
          <div>
            <dt>{copy("workspaceProofBoundary")}</dt>
            <dd>{copy(PROOF_COPY[proofSegment])}</dd>
          </div>
        </dl>
      </div>
      <main id={mainId} tabIndex={-1}>
        <div className="workspace-layout">
          <aside className="workspace-stage-column">
            <WorkflowRail currentStage={currentStage} copy={copy} />
          </aside>
          <div className="workspace-content-column">
            <div className="workspace-route-heading">
              <p className="workspace-route-context">{copy(contextKey)}</p>
              <h1>{copy(titleKey)}</h1>
              <div className="workspace-status">{status}</div>
            </div>
            <section className="workspace-current-work" data-section="current-action" aria-labelledby="workspace-current-work-title">
              <h2 id="workspace-current-work-title">{copy("workspaceCurrentStage")}</h2>
              {children}
            </section>
            {supportingEvidence ? (
              <aside className="workspace-supporting-evidence" aria-labelledby="workspace-supporting-evidence-title">
                <h2 id="workspace-supporting-evidence-title">{copy("workspaceSupportingEvidence")}</h2>
                {supportingEvidence}
              </aside>
            ) : null}
            <details className="workspace-technical-evidence">
              <summary>{copy("workspaceTechnicalEvidence")}</summary>
              {technicalEvidence ?? <p>{copy("statusUnavailable")}</p>}
            </details>
          </div>
        </div>
      </main>
      <footer className="workspace-footer">
        <p>{copy("workspaceFooter")}</p>
      </footer>
    </div>
  );
}

const STAGE_COPY: Record<WorkflowStage, PresentationCopyKey> = {
  consultation_intake: "workflowStageConsultationIntake",
  client_fact_review: "workflowStageClientFactReview",
  route_analysis: "workflowStageRouteAnalysis",
  client_confirmation: "workflowStageClientConfirmation",
  execution_followup: "workflowStageExecutionFollowup",
};
