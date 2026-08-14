"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import type { PresentationCopyKey } from "../../lib/presentation/catalog";
import { usePresentation } from "../../lib/presentation/context";
import type { WorkflowProofSegment, WorkflowStage } from "../../lib/presentation/journey";
import { AdvisorProductFrame } from "./AdvisorProductFrame";
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
  authority?: ReactNode;
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
  authority,
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
            <span>{copy("productName")}</span>
          </Link>
          <p className="workspace-category">{copy("workspaceCategory")}</p>
          <div className="workspace-header-controls">
            <LocaleSwitch />
            <span className="workspace-synthetic-label">{copy("syntheticLabel")}</span>
          </div>
        </div>
      </header>
      <main id={mainId} tabIndex={-1}>
        <div className="workspace-page">
          <AdvisorProductFrame
            topBand={
              <div className="workspace-top-band-grid">
                <div>
                  <span>{copy("workspaceCaseContext")}</span>
                  <strong>{copy(contextKey)}</strong>
                </div>
                <div>
                  <span>{copy("workspaceCurrentStage")}</span>
                  <strong>{currentStage ? copy(STAGE_COPY[currentStage]) : copy("statusUnavailable")}</strong>
                </div>
                <div>
                  <span>{copy("workspaceCurrentStatus")}</span>
                  <div className="workspace-top-band-status">{status}</div>
                </div>
                <div>
                  <span>{copy("workspaceProofBoundary")}</span>
                  <strong>{copy(PROOF_COPY[proofSegment])}</strong>
                </div>
              </div>
            }
            workflow={<WorkflowRail currentStage={currentStage} copy={copy} />}
            context={
              <div className="workspace-context-plane">
                <p className="workspace-context-label">{copy("workspaceCaseContext")}</p>
                <p className="workspace-context-value">{copy(contextKey)}</p>
                <p className="workspace-boundary">{copy("workspaceSyntheticBoundary")}</p>
                <dl className="workspace-context-facts">
                  <div>
                    <dt>{copy("workspaceActiveRole")}</dt>
                    <dd>{activeRole ? copy(ROLE_COPY[activeRole]) : copy("statusUnavailable")}</dd>
                  </div>
                  <div>
                    <dt>{copy("workspaceCurrentStage")}</dt>
                    <dd>{currentStage ? copy(STAGE_COPY[currentStage]) : copy("statusUnavailable")}</dd>
                  </div>
                </dl>
              </div>
            }
            currentWork={
              <div className="workspace-current-work-content">
                <div className="workspace-route-heading">
                  <p className="workspace-route-context">{copy(contextKey)}</p>
                  <h1>{copy(titleKey)}</h1>
                  <div className="workspace-status">{status}</div>
                </div>
                <section className="workspace-current-work" data-section="current-action" aria-labelledby="workspace-current-work-title">
                  <h2 id="workspace-current-work-title">{copy("workspaceCurrentWork")}</h2>
                  {children}
                </section>
              </div>
            }
            evidence={
              supportingEvidence ? (
                <div className="workspace-supporting-evidence-content">
                  <h2>{copy("workspaceSupportingEvidence")}</h2>
                  {supportingEvidence}
                </div>
              ) : undefined
            }
            authority={
              <div className="workspace-authority-plane">
                <p className="workspace-authority-label">{copy("workspaceHumanAuthority")}</p>
                <p className="workspace-authority-role">{activeRole ? copy(ROLE_COPY[activeRole]) : copy("statusUnavailable")}</p>
                {authority ?? <p className="workspace-authority-status">{copy("workspaceAwaitingAction")}</p>}
              </div>
            }
            technical={technicalEvidence ?? <p>{copy("statusUnavailable")}</p>}
            technicalLabel={copy("workspaceTechnicalEvidence")}
          />
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
