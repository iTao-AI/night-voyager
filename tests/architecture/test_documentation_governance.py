from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

import pytest

ROOT = Path(__file__).resolve().parents[2]
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
CURRENT_SLICE_0_STATUS = (
    "Slice 0 permanently ended as local `evaluation_invalid` safe stop; no "
    "`MkeCaptureArtifactV2`, terminal receipt, information-gain conclusion, candidate "
    "persistence, Slice 1/2 unlock, or v0.1.6; PR #87 merged; hosted CI/publication "
    "cleanup completed"
)
HISTORICAL_SLICE_0_STATUS = (
    "Slice 0 ended in local `evaluation_invalid` safe stop; retired holdout retained; "
    "no later stage unlocked; merged PR/hosted CI/publication pending"
)
PLAN_STATUS_BINDINGS = (
    (
        "M2 identity, session, and RLS",
        "Implemented",
        "2026-07-12-m2-identity-session-rls.md",
        "**Implementation status:** Complete.",
    ),
    (
        "M3A deterministic planning",
        "Implemented",
        "2026-07-12-m3a-deterministic-planning.md",
        "**Implementation status:** Complete.",
    ),
    (
        "M3B advisor and family decision",
        "Implemented",
        "2026-07-13-m3b-advisor-family-decision.md",
        "**Implementation status:** Complete.",
    ),
    (
        "M4A durable AgentTask and SSE",
        "Implemented",
        "2026-07-13-m4a-durable-agent-task-sse.md",
        "**Implementation status:** Complete.",
    ),
    (
        "M4B MKE read-only consumer",
        "Implemented",
        "2026-07-13-m4b-mke-readonly-consumer.md",
        "**Implementation status:** Complete.",
    ),
    (
        "M5 connected advisor-to-family demo",
        "Implemented",
        "2026-07-14-m5-connected-advisor-family-demo.md",
        "**Implementation status:** Complete.",
    ),
    (
        "DRA governed candidate and mixed planning",
        "Implemented and released in v0.1.1",
        "2026-07-15-dra-governed-mixed-evidence-closure.md",
        "**Implementation status:** Complete.",
    ),
    (
        "Governed Collaboration Core v1",
        "Implemented and released in v0.1.2",
        "2026-07-16-governed-conversation-memory-authority.md",
        "**Implementation status:** Complete.",
    ),
    (
        "Governed Collaboration Core v1",
        "Implemented and released in v0.1.2",
        "2026-07-16-versioned-skill-runtime-pinning.md",
        "**Implementation status:** Complete.",
    ),
    (
        "Governed Collaboration Core v1",
        "Implemented and released in v0.1.2",
        "2026-07-16-collaboration-walkthrough-and-inspector.md",
        "**Implementation status:** Complete and released in v0.1.2.",
    ),
    (
        "Governed Fact-to-Plan Closure and bilingual presentation",
        "Implemented and released in v0.1.3",
        "2026-07-22-explicit-planning-start-authority.md",
        "**Implementation status:** Complete, merged as PR #57, and released in v0.1.3.",
    ),
    (
        "Governed Fact-to-Plan Closure and bilingual presentation",
        "Implemented and released in v0.1.3",
        "2026-07-22-governed-fact-to-plan-walkthrough.md",
        "**Implementation status:** Complete, merged as PR #58, and released in v0.1.3.",
    ),
    (
        "Governed Fact-to-Plan Closure and bilingual presentation",
        "Implemented and released in v0.1.3",
        "2026-07-22-chinese-first-portfolio-presentation.md",
        "**Implementation status:** Complete, merged as PR #59, and released in v0.1.3.",
    ),
    (
        "DRA v0.1.6 governed live closure",
        "PR A/B/C and effective-query v2 released in v0.1.4 as provider-free "
        "Night Voyager consumer evidence; "
        "two live attempts safely stopped pre-import; acceptance incomplete",
        "2026-07-25-dra-v0-1-6-live-closure-pr-a-implementation-plan.md",
        "**Implementation status:** PR A, PR B, and PR C are released in v0.1.4 "
        "as provider-free Night Voyager consumer evidence; governed live acceptance "
        "remains pending.",
    ),
    (
        "DRA v0.1.6 governed live closure",
        "PR A/B/C and effective-query v2 released in v0.1.4 as provider-free "
        "Night Voyager consumer evidence; "
        "two live attempts safely stopped pre-import; acceptance incomplete",
        "2026-07-25-dra-v0-1-6-live-closure-pr-b-implementation-plan.md",
        "**Implementation status:** PR A, PR B, PR C, and the effective-query v2 repair are\n"
        "released in v0.1.4 as provider-free Night Voyager consumer evidence. One bounded "
        "live attempt projected 25 Evidence rows, all\n"
        "`uncited`, and stopped safely before candidate import; governed live acceptance\n"
        "remains pending.",
    ),
    (
        "DRA v0.1.6 governed live closure",
        "PR A/B/C and effective-query v2 released in v0.1.4 as provider-free "
        "Night Voyager consumer evidence; "
        "two live attempts safely stopped pre-import; acceptance incomplete",
        "2026-07-25-dra-v0-1-6-live-closure-pr-c-implementation-plan.md",
        "**Implementation status:** PR A, PR B, PR C, and the effective-query v2 repair are\n"
        "released in v0.1.4 as provider-free Night Voyager consumer evidence. One bounded "
        "live attempt projected 25 Evidence rows, all\n"
        "`uncited`, and stopped safely before candidate import; governed live acceptance\n"
        "remains pending.",
    ),
    (
        "DRA strict consumer and versioned planning revision",
        "PR 1, PR 2, and PR 3 released in v0.1.4 as controlled provider-free evidence; "
        "strict live acceptance incomplete",
        "2026-07-27-dra-strict-consumer-pr-1-implementation-plan.md",
        "**Plan status:** Implementation complete and released in v0.1.4 as controlled "
        "provider-free evidence; strict live acceptance remains incomplete.",
    ),
    (
        "DRA strict consumer and versioned planning revision",
        "PR 1, PR 2, and PR 3 released in v0.1.4 as controlled provider-free evidence; "
        "strict live acceptance incomplete",
        "2026-07-27-versioned-planning-revision-pr-2-implementation-plan.md",
        "**Plan status:** Implementation complete and released in v0.1.4 as controlled "
        "provider-free evidence; strict live acceptance remains incomplete.",
    ),
    (
        "DRA strict consumer and versioned planning revision",
        "PR 1, PR 2, and PR 3 released in v0.1.4 as controlled provider-free evidence; "
        "strict live acceptance incomplete",
        "2026-07-27-planning-revision-journey-pr-3-implementation-plan.md",
        "**Plan status:** Implementation complete and released in v0.1.4 as controlled "
        "provider-free evidence; strict live acceptance remains incomplete.",
    ),
    (
        "High-End Portfolio Entry v1",
        "Implemented and released in v0.1.3",
        "2026-07-23-high-end-portfolio-entry.md",
        "**Implementation status:** Complete, merged as PR #60, and released in v0.1.3.",
    ),
)


def test_dra_full_recovery_freeze_and_non_claims_are_documented() -> None:
    runbook = (ROOT / "docs/operations/dra-consumer-proof.md").read_text()
    reference = (ROOT / "docs/reference/dra-governed-evidence.md").read_text()
    adr = (
        ROOT / "docs/decisions/0011-dra-v0-1-6-live-consumer-boundary.md"
    ).read_text()
    combined = " ".join("\n".join((runbook, reference, adr)).split())
    for required in (
        "freeze-intent",
        "preflight-live",
        "capture-live",
        "select-and-import",
        "reconcile-create",
        "resume-poll",
        "inspect-recovery",
        "rehearse-capture",
        "promote",
        "review",
        "decide",
        "evaluate",
        "rehearse-full",
        "freeze-candidate",
        "cleanup",
        "operator_action_required",
        "same run",
        "URL-only",
        "UNTRUSTED_CANDIDATE",
        "no remote cancellation",
        "PR A, PR B, PR C, and the strict-consumer prerequisite are implemented "
        "provider-free",
        "INCOMPLETE_PENDING_LIVE_ACCEPTANCE",
        "25",
        "83",
        "uncited",
        "before candidate import",
        "night-voyager.dra-live-effective-query.v2",
        "safe-stop evidence",
        "second substantive failure",
        "snapshot",
        "Docker",
        "python",
        "frontend",
        "compose",
    ):
        assert required in combined
    assert "distinct acknowledgement" in combined
    assert "governed-live success claim" in combined


def test_current_slice_zero_status_is_separate_from_historical_plan_wording() -> None:
    index = (ROOT / "docs/superpowers/README.md").read_text(encoding="utf-8")
    row = next(
        line
        for line in index.splitlines()
        if line.startswith("| Advisor-Governed Multimodal Evidence Composition |")
    )
    assert f"| {CURRENT_SLICE_0_STATUS} |" in row
    assert "pending" not in row.lower()
    assert "release candidate" not in row.lower()

    historical_plan = (
        ROOT
        / "docs/superpowers/plans/"
        "2026-07-31-advisor-governed-multimodal-evidence-composition-implementation.md"
    ).read_text(encoding="utf-8")
    assert f"**Status:** {HISTORICAL_SLICE_0_STATUS}" in historical_plan


def test_dra_strict_prerequisite_current_docs_are_truthful() -> None:
    current_docs = {
        relative: (ROOT / relative).read_text(encoding="utf-8")
        for relative in (
            "README.md",
            "README_CN.md",
            "DESIGN.md",
            "docs/README.md",
            "docs/decisions/0011-dra-v0-1-6-live-consumer-boundary.md",
            "docs/operations/dra-consumer-proof.md",
            "docs/operations/database-roles.md",
            "docs/reference/dra-governed-evidence.md",
            "docs/reference/http-api-v1.md",
            "docs/superpowers/README.md",
            "docs/superpowers/specs/2026-07-25-dra-v0-1-6-governed-live-closure-design.md",
            "docs/superpowers/specs/2026-07-27-dra-strict-revision-lineage-design.md",
            "docs/superpowers/plans/2026-07-27-dra-strict-consumer-pr-1-implementation-plan.md",
            "docs/superpowers/plans/2026-07-27-planning-revision-journey-pr-3-implementation-plan.md",
        )
    }
    combined = "\n".join(current_docs.values())
    for required in (
        "DRA strict profile is pinned to exact post-release commit",
        "01ba21f2996769e68cbc88f4bb0596740df27f6b",
        "generic-strict-citation@1",
        "dra.strict-citation-profile.v1",
        "two bounded live attempts stopped before candidate import",
        "no third provider attempt is authorized",
        "strict live acceptance remains incomplete",
        "dra-strict-migration",
    ):
        assert required in combined
    current_runtime_docs = "\n".join(
        source
        for relative, source in current_docs.items()
        if "/superpowers/" not in relative
    )
    assert "strict profile is included in DRA `v0.1.6`" not in current_runtime_docs

    strict_spec = current_docs[
        "docs/superpowers/specs/2026-07-27-dra-strict-revision-lineage-design.md"
    ]
    strict_plan = current_docs[
        "docs/superpowers/plans/2026-07-27-dra-strict-consumer-pr-1-implementation-plan.md"
    ]
    plans_index = current_docs["docs/superpowers/README.md"]
    assert (
        "**Design status:** Approved; PR 1, PR 2, and PR 3 implemented provider-free; "
        "strict live acceptance remains incomplete."
    ) in strict_spec
    assert (
        "**Plan status:** Implementation complete and released in v0.1.4 as controlled "
        "provider-free evidence; strict live acceptance remains incomplete."
    ) in strict_plan
    assert (
        "| DRA strict consumer and versioned planning revision | "
        "PR 1, PR 2, and PR 3 released in v0.1.4 as controlled provider-free evidence; "
        "strict live acceptance incomplete |"
    ) in plans_index
MERGED_FACT_TO_PLAN_BANNERS = {
    "2026-07-22-explicit-planning-start-authority.md": (
        "**Implementation status:** Complete, merged as PR #57, and released in v0.1.3."
    ),
    "2026-07-22-governed-fact-to-plan-walkthrough.md": (
        "**Implementation status:** Complete, merged as PR #58, and released in v0.1.3."
    ),
}
STALE_FACT_TO_PLAN_STATUS = (
    "locally for authority review",
    "awaiting targeted re-review",
    "remain approved but not implemented",
    "No push, pull request, merge",
)


def tracked_markdown_files() -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "*.md"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        result = None
    if result is not None and result.returncode == 0:
        return [ROOT / relative for relative in result.stdout.splitlines()]

    ignored = {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "dist",
        "node_modules",
    }
    return sorted(
        path
        for path in ROOT.rglob("*.md")
        if not ignored.intersection(path.relative_to(ROOT).parts)
    )


def relative_file_targets(source: Path) -> list[Path]:
    targets: list[Path] = []
    for match in MARKDOWN_LINK.finditer(source.read_text(encoding="utf-8")):
        raw_target = match.group(1).strip().strip("<>")
        target = unquote(raw_target.split("#", 1)[0])
        if not target or target.startswith(("http://", "https://", "mailto:", "/")):
            continue
        targets.append((source.parent / target).resolve())
    return targets


def merged_fact_to_plan_status_errors(filename: str, plan: str) -> list[str]:
    current_status = " ".join(
        plan.split("> **For agentic workers:**", 1)[0].split()
    )
    errors: list[str] = []
    expected_banner = MERGED_FACT_TO_PLAN_BANNERS[filename]
    if expected_banner not in current_status:
        errors.append(f"{filename}: missing merged PR banner")
    if "released in v0.1.3" not in current_status:
        errors.append(f"{filename}: missing v0.1.3 release boundary")
    for stale_status in STALE_FACT_TO_PLAN_STATUS:
        if stale_status in current_status:
            errors.append(f"{filename}: stale status {stale_status!r}")
    return errors


def superpowers_status_binding_errors(index: str) -> list[str]:
    rows: dict[str, tuple[str, str]] = {}
    for line in index.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[0] not in {"Scope", "---"}:
            rows[cells[0]] = (cells[1], cells[2])

    errors: list[str] = []
    plans_root = ROOT / "docs/superpowers/plans"
    for scope, expected_status, filename, expected_banner in PLAN_STATUS_BINDINGS:
        row = rows.get(scope)
        if row is None:
            errors.append(f"{scope}: missing index row")
            continue
        actual_status, links = row
        if actual_status != expected_status:
            errors.append(
                f"{scope}: index status {actual_status!r} != {expected_status!r}"
            )
        if f"](plans/{filename})" not in links:
            errors.append(f"{scope}: missing plan link for {filename}")
        plan = (plans_root / filename).read_text(encoding="utf-8")
        if expected_banner not in plan:
            errors.append(f"{scope}: plan banner drift for {filename}")
        if filename in MERGED_FACT_TO_PLAN_BANNERS:
            errors.extend(merged_fact_to_plan_status_errors(filename, plan))
    return errors


def test_tracked_public_markdown_relative_file_links_resolve() -> None:
    broken = [
        f"{source.relative_to(ROOT)} -> {target.relative_to(ROOT)}"
        for source in tracked_markdown_files()
        for target in relative_file_targets(source)
        if not target.is_file()
    ]
    assert broken == []


def test_git_free_source_archive_runs_documentation_link_check(tmp_path: Path) -> None:
    checkout = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if checkout.returncode != 0:
        pytest.skip("archive construction requires a Git checkout")

    archive = tmp_path / "source.tar"
    extracted = tmp_path / "source"
    extracted.mkdir()
    with archive.open("wb") as output:
        subprocess.run(
            ["git", "archive", "--format=tar", "HEAD"],
            cwd=ROOT,
            stdout=output,
            check=True,
        )
    shutil.unpack_archive(archive, extracted, filter="data")
    relative_test = Path("tests/architecture/test_documentation_governance.py")
    shutil.copyfile(ROOT / relative_test, extracted / relative_test)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            f"{relative_test}::test_tracked_public_markdown_relative_file_links_resolve",
        ],
        cwd=extracted,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_superpowers_index_links_every_approved_spec_and_plan() -> None:
    index = (ROOT / "docs/superpowers/README.md").read_text(encoding="utf-8")
    expected = sorted(
        path.relative_to(ROOT / "docs/superpowers").as_posix()
        for directory in ("specs", "plans")
        for path in (ROOT / "docs/superpowers" / directory).glob("*.md")
    )
    missing = [relative for relative in expected if f"]({relative})" not in index]
    assert missing == []


def test_superpowers_index_statuses_match_plan_banners() -> None:
    index = (ROOT / "docs/superpowers/README.md").read_text(encoding="utf-8")
    assert superpowers_status_binding_errors(index) == []

    counterfactual = index.replace(
        "| M3A deterministic planning | Implemented |",
        "| M3A deterministic planning | Approved but not implemented |",
        1,
    )
    errors = superpowers_status_binding_errors(counterfactual)
    assert any("M3A deterministic planning" in error for error in errors)


def test_pr_c_files_do_not_reopen_completed_adr_0006_governance() -> None:
    plan = (
        ROOT
        / "docs/superpowers/plans/2026-07-16-collaboration-walkthrough-and-inspector.md"
    ).read_text(encoding="utf-8")
    assert "- Modify: `docs/decisions/0006-connected-demo-bff-authority.md`" not in plan


def test_implemented_document_statuses_do_not_regress() -> None:
    expected = {
        "docs/decisions/0006-connected-demo-bff-authority.md": (
            "Implemented in M5.",
            "Before M5, `/demo` was a disconnected M1 visual fixture.",
        ),
        "docs/superpowers/specs/2026-07-15-dra-governed-mixed-evidence-closure-design.md": (
            "Implemented and released in v0.1.1 through PR #26 and PR #27.",
            "Live provider proof was not run.",
        ),
        "docs/superpowers/plans/2026-07-15-dra-governed-mixed-evidence-closure.md": (
            "**Implementation status:** Complete.",
            "PR #26",
            "PR #27",
            "released in v0.1.1",
        ),
        "docs/superpowers/plans/2026-07-16-governed-conversation-memory-authority.md": (
            "merged to `main`",
            "PR #30",
            "released in v0.1.2 as part of Governed Collaboration Core v1",
            "PR B and PR C were delivered under their own plans",
        ),
        "docs/superpowers/specs/2026-07-25-dra-v0-1-6-governed-live-closure-design.md": (
            "**Implementation status:** PR A, PR B, PR C, and the "
            "effective-query v2 repair are\n"
            "implemented and released in v0.1.4 as provider-free Night Voyager "
            "consumer evidence.\n"
            "Two bounded live attempts projected 25 and 83 "
            "Evidence rows,\n"
            "all `uncited`, and stopped safely before candidate import; governed live\n"
            "acceptance remains pending.",
            "INCOMPLETE_PENDING_LIVE_ACCEPTANCE",
        ),
    }
    for relative, required in expected.items():
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert all(token in source for token in required), relative


def test_repository_governance_covers_merge_cleanup_and_bounded_ci() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for token in (
        "exact base",
        "approvals",
        "unresolved review or platform blockers",
        "mergeability",
        "requires targeted re-review",
        "After a squash merge",
        "linked worktree, local branch, and remote branch",
        "Remote branch deletion requires separate explicit",
        "unique commits",
        "retained or cleaned up",
        "low frequency and for a bounded duration",
        "exact pending check or trigger",
    ):
        assert token in agents


def test_pull_request_template_matches_repository_contract() -> None:
    template = (ROOT / ".github/pull_request_template.md").read_text(encoding="utf-8")
    headings = (
        "## Summary",
        "## Completion",
        "## Verification",
        "## Scope",
        "## Risk / Impact",
        "## Documentation impact",
    )
    assert [template.index(heading) for heading in headings] == sorted(
        template.index(heading) for heading in headings
    )
    assert "默认使用简体中文填写正文" in template


def final_pr_body_reconciliation_errors(agents: str, template: str) -> list[str]:
    required_agent_semantics = {
        "satisfied_gate_checkbox": (
            "must update each corresponding checkbox to `[x]`",
        ),
        "final_reconciliation_timing": (
            "After merge and before closeout",
            "final PR body reconciliation",
        ),
        "terminal_facts": (
            "hosted checks, authorization, mergeability, review or platform blockers, "
            "and cleanup",
            "actual terminal state",
            "necessary links",
        ),
        "remaining_risk_and_non_claims": (
            "remaining risk",
            "true non-claims",
        ),
        "persisted_body_gate": (
            "Read back the persisted PR body",
            "must not claim that PR closeout is fully complete",
        ),
        "no_stale_merged_pr": (
            "A merged PR must not permanently retain a satisfied gate as unchecked",
            "authorization, CI, or cleanup is still pending",
        ),
    }
    errors = [
        name
        for name, tokens in required_agent_semantics.items()
        if not all(token in agents for token in tokens)
    ]
    template_tokens = (
        "已满足的 merge gate 必须改为 `[x]`",
        "merge 后、closeout 前必须回写并回读最终 PR body",
        "不得保留过期 pending 或 risk 文案",
    )
    if not all(token in template for token in template_tokens):
        errors.append("template_final_reconciliation")
    return errors


def test_pr_body_contract_requires_final_reconciliation() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    template = (ROOT / ".github/pull_request_template.md").read_text(encoding="utf-8")
    assert final_pr_body_reconciliation_errors(agents, template) == []

    counterfactual = agents.replace(
        "must update each corresponding checkbox to `[x]`",
        "may leave each corresponding checkbox unchecked",
        1,
    )
    assert "satisfied_gate_checkbox" in final_pr_body_reconciliation_errors(
        counterfactual, template
    )


def test_current_documentation_release_and_planning_boundaries_do_not_drift() -> None:
    docs_index = (ROOT / "docs/README.md").read_text(encoding="utf-8")
    assert "DRA closure was released in v0.1.1" in docs_index
    assert "collaboration PR A, versioned Skill PR B" in docs_index
    assert "browser walkthrough/inspector PR C are" in docs_index
    assert "connected [demo storyboard](design/demo-storyboard.md)" in docs_index

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_cn = (ROOT / "README_CN.md").read_text(encoding="utf-8")
    assert "[Connected demo storyboard](docs/design/demo-storyboard.md)" in readme
    assert "[Connected demo storyboard](docs/design/demo-storyboard.md)" in readme_cn

    spec = (
        ROOT
        / "docs/superpowers/specs/2026-07-16-governed-collaboration-core-design.md"
    ).read_text(encoding="utf-8")
    plan = (
        ROOT
        / "docs/superpowers/plans/2026-07-16-collaboration-walkthrough-and-inspector.md"
    ).read_text(encoding="utf-8")
    assert "at most three independent bounded lanes" not in spec
    assert "no fixed lane count" in spec
    assert "ADR 0006 already records M5 as implemented" in spec
    assert "ADR 0006 already records M5 as implemented" in plan


def test_versioned_planning_revision_authority_is_documented() -> None:
    adr = (
        ROOT / "docs/decisions/0012-versioned-planning-revision-authority.md"
    ).read_text(encoding="utf-8")
    operations = "\n".join(
        (ROOT / relative).read_text(encoding="utf-8")
        for relative in (
            "docs/operations/database-roles.md",
            "docs/operations/worker-and-sse.md",
        )
    )
    references = "\n".join(
        (ROOT / relative).read_text(encoding="utf-8")
        for relative in (
            "docs/reference/agent-tasks-and-events.md",
            "docs/reference/collaboration-and-confirmed-facts.md",
            "docs/reference/http-api-v1.md",
            "docs/design/projection-matrix.md",
            "docs/design/state-and-interaction-matrix.md",
        )
    )
    combined = " ".join(f"{adr}\n{operations}\n{references}".split())
    for required in (
        "request_revision review -> fact revision -> frozen task predecessor",
        "worker never infers predecessor from current PlanningRun",
        "one predecessor -> at most one successor",
        "old run retained but non-authoritative",
        "comparison is deterministic and country-keyed",
        "V1 read routes remain default",
        "contract_version=2",
        "journey-status is participant-safe recovery authority",
        "PR 3 browser journey is implemented provider-free",
        "read_connected_journey_fact_pending",
        "Migration `0012` remains the runtime lineage authority",
        "Migration `0013` adds only the closed provider-free demo seed helper",
        "zero runtime grants",
        "planning-revision-seed-migration",
    ):
        assert required in combined
    for mode in ("authority", "worker", "projection", "all"):
        assert f"planning-revision {mode}" in operations

    plans_index = (ROOT / "docs/superpowers/README.md").read_text(encoding="utf-8")
    pr2_plan = (
        ROOT
        / "docs/superpowers/plans/"
        "2026-07-27-versioned-planning-revision-pr-2-implementation-plan.md"
    ).read_text(encoding="utf-8")
    assert "PR 1, PR 2, and PR 3 released in v0.1.4 as controlled provider-free evidence" in (
        plans_index
    )
    assert (
        "**Plan status:** Implementation complete and released in v0.1.4 as controlled "
        "provider-free evidence; strict live acceptance remains incomplete."
        in pr2_plan
    )

    verifier = (ROOT / "scripts/verify_release.py").read_text(encoding="utf-8")
    assert 'heads != {"0015"}' in verifier
    assert '"read_connected_journey_fact_pending"' in verifier


def test_root_readmes_bind_current_development_migration_head() -> None:
    current_graph = (
        "`0001 -> 0002 -> 0003 -> 0004 -> 0005 -> 0006 -> 0007 -> 0008 -> "
        "0009 -> 0010 -> 0011 -> 0012 -> 0013 -> 0014 -> 0015`"
    )
    stale_graph = (
        "`0001 -> 0002 -> 0003 -> 0004 -> 0005 -> 0006 -> 0007 -> 0008 -> "
        "0009 -> 0010 -> 0011 -> 0012 -> 0013 -> 0014`"
    )
    for relative in ("README.md", "README_CN.md"):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert source.count(current_graph) == 1, relative
        assert stale_graph not in source, relative
        assert "v0.1.3 migration `0009`" in source, relative


def test_current_release_and_candidate_freeze_status_surfaces_do_not_regress() -> None:
    readmes = [
        (ROOT / "README.md").read_text(encoding="utf-8"),
        (ROOT / "README_CN.md").read_text(encoding="utf-8"),
    ]
    for source in readmes:
        assert "v0.1.5" in source
        assert "PR #87" in source
        assert "evaluation_invalid" in source
        assert "`0015`" in source
        assert "release candidate" not in source.lower()
        assert "sharp 0.35.3" in source
        assert "GHSA-f88m-g3jw-g9cj" in source
        assert "16.3.0" in source
        assert "after merge" in source
        assert "audit-zero" in source
        assert "postcss@8.5.23" in source
        assert "nanoid@3.3.18" in source
        assert "postcss@8.5.18" not in source
        assert "nanoid@3.3.16" not in source
        assert "zero advisory objects" in source
        assert "js-yaml" not in source
        assert "brace-expansion" not in source
        assert "minimatch" not in source
        assert (
            "Fresh full and runtime/omit-dev npm audits report zero advisory objects"
            in source
            or "Fresh full 与 runtime/omit-dev npm audits 均报告 zero advisory objects"
            in source
        )
        assert "direct" in source
        assert "override" in source
        assert "0.34.5" not in source
        assert not re.search(r"Dependabot #7[^.\n]{0,100}FIXED", source, re.IGNORECASE)
        assert "immutable" in source or "不可变" in source
        for trigger in (
            "public deployment",
            "untrusted image path",
            "advisory change",
        ):
            assert trigger in source
        assert "compatible upstream support for sharp >=0.35" not in source


def test_current_security_policy_tracks_the_development_dependency_path() -> None:
    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")

    assert "16.3.0" in security
    assert "sharp 0.35.3" in security
    assert "GHSA-f88m-g3jw-g9cj" in security
    assert "no direct postcss, nanoid, or sharp dependency" in security
    assert "no npm override" in security
    assert "Dependabot #7" in security
    assert "after merge" in security
    assert not re.search(r"Dependabot #7[^.\n]{0,100}FIXED", security, re.IGNORECASE)
    assert "v0.1.5" in security
    assert "immutable" in security
    assert "not an audit-zero claim" in security
    assert "postcss@8.5.23" in security
    assert "nanoid@3.3.18" in security
    assert "cryptography==50.0.0" in security
    assert "mcp" in security
    assert "PyJWT[crypto]" in security
    assert "first patched version" in security
    assert (
        "The local graph is outside the affected range; hosted alert closure is "
        "evaluated only after merge and is not claimed by local validation."
    ) in security
    assert "the alert remains open until post-merge" not in security
    assert "Post-merge GitHub readback" in security
    assert "no Night Voyager use of cryptography's PKCS#7 decryption" in security
    assert "finite-field Diffie-Hellman APIs" in security
    assert "postcss@8.5.18" not in security
    assert "nanoid@3.3.16" not in security
    assert "zero advisory objects" in security
    assert "js-yaml" not in security
    assert "brace-expansion" not in security
    assert "minimatch" not in security
    assert "Fresh full and runtime/omit-dev npm audits report zero advisory objects" in security
    assert "0.34.5" not in security

    docs_index = (ROOT / "docs/README.md").read_text(encoding="utf-8")
    assert "PR #87 is merged; hosted CI and publication cleanup are complete" in docs_index
    assert "release candidate" not in docs_index.lower()

    adr = (
        ROOT / "docs/decisions/0014-advisor-governed-multimodal-evidence-composition.md"
    ).read_text(encoding="utf-8")
    assert "PR #87 is merged; hosted CI and publication cleanup are complete" in adr
    assert "still-pending" not in adr

    operations = (ROOT / "docs/operations/database-roles.md").read_text(encoding="utf-8")
    assert "The released v0.1.5 migration graph ends at exact head `0015`" in operations


def test_timeline_execution_adr_separates_release_history_from_current_head() -> None:
    adr = (
        ROOT / "docs/decisions/0013-governed-timeline-execution-authority.md"
    ).read_text(encoding="utf-8")
    normalized = " ".join(adr.split())

    assert "Historical v0.1.4 ended at migration `0013`" in normalized
    assert "the released v0.1.5 current migration graph ends at migration `0015`" in normalized
    assert "timeline transition authority remains owned by migration `0014`" in normalized
    assert "migration `0015` only closes deterministic demo identity" in normalized


def test_planning_revision_journey_docs_are_current_and_claim_bounded() -> None:
    current_docs = {
        relative: (ROOT / relative).read_text(encoding="utf-8")
        for relative in (
            "README.md",
            "README_CN.md",
            "DESIGN.md",
            "docs/README.md",
            "docs/design/demo-storyboard.md",
            "docs/design/projection-matrix.md",
            "docs/design/route-map.md",
            "docs/design/state-and-interaction-matrix.md",
            "docs/operations/collaboration-authority.md",
            "docs/operations/collaboration-walkthrough.md",
            "docs/operations/connected-demo.md",
            "docs/operations/database-roles.md",
            "docs/operations/worker-and-sse.md",
            "docs/decisions/0012-versioned-planning-revision-authority.md",
            "docs/reference/agent-tasks-and-events.md",
            "docs/reference/collaboration-and-confirmed-facts.md",
            "docs/reference/http-api-v1.md",
            "docs/superpowers/README.md",
            "docs/superpowers/specs/2026-07-27-dra-strict-revision-lineage-design.md",
            "docs/superpowers/plans/2026-07-27-planning-revision-journey-pr-3-implementation-plan.md",
        )
    }
    combined = " ".join("\n".join(current_docs.values()).split())
    for required in (
        "request revision",
        "student preferred-country change",
        "retained predecessor",
        "successor PlanningRun",
        "deterministic old/new comparison",
        "fresh advisor authorization",
        "only the current family decision",
        "blocked budget counterfactual",
        "01ba21f2996769e68cbc88f4bb0596740df27f6b",
        "strict live acceptance remains incomplete",
        "released in v0.1.4",
        "no third provider attempt",
        "25 and 83",
        "zero cited rows",
        "controlled provider-free evidence",
        "night-voyager-planning-revision.png",
        "planning-revision",
        "UPDATE_PORTFOLIO_SCREENSHOTS",
        "UPDATE_PLANNING_REVISION_SCREENSHOT",
        "Amendments 26 and 27",
        "Migration `0012` remains the runtime lineage authority",
        "Migration `0013` adds only the closed provider-free demo seed helper",
    ):
        assert required in combined
    assert "PR 3 browser journey remains unimplemented" not in combined

    verifier = (ROOT / "scripts/verify_release.py").read_text(encoding="utf-8")
    for required in (
        "PLANNING_REVISION_CURRENT_DOCS",
        "PLANNING_REVISION_SCREENSHOT",
        "released in v0.1.4",
        "strict live acceptance remains incomplete",
        "no third provider attempt",
        "25 and 83",
        "zero cited rows",
        "controlled provider-free evidence",
    ):
        assert required in verifier


def test_explicit_planning_start_documents_match_0009_authority() -> None:
    adr = (
        ROOT / "docs/decisions/0010-explicit-planning-start-authority.md"
    ).read_text(encoding="utf-8")
    task_reference = (
        ROOT / "docs/reference/agent-tasks-and-events.md"
    ).read_text(encoding="utf-8")
    http_reference = (ROOT / "docs/reference/http-api-v1.md").read_text(
        encoding="utf-8"
    )
    database_roles = (ROOT / "docs/operations/database-roles.md").read_text(
        encoding="utf-8"
    )
    worker = (ROOT / "docs/operations/worker-and-sse.md").read_text(
        encoding="utf-8"
    )
    docs_index = (ROOT / "docs/README.md").read_text(encoding="utf-8")
    normalized_task_reference = " ".join(task_reference.split())
    normalized_database_roles = " ".join(database_roles.split())
    normalized_worker = " ".join(worker.split())

    for token in (
        "Status: Accepted",
        "migration `0009`",
        "task creation",
        "`intake -> planning`",
        "confirmation",
        "no separate planning-start endpoint",
    ):
        assert token in adr
    assert "decisions/0010-explicit-planning-start-authority.md" in docs_index
    assert "first deterministic planning task" in normalized_task_reference
    assert "confirmation alone" in normalized_task_reference.lower()
    assert (
        "mixed operation from `intake` remains rejected" in normalized_task_reference
    )
    assert "request and response schemas are unchanged" in http_reference
    assert "No planning-start endpoint" in http_reference
    assert "Migration `0009`" in normalized_database_roles
    assert "night_voyager_api" in normalized_database_roles
    assert (
        "night_voyager_worker` and `PUBLIC` cannot execute it"
        in normalized_database_roles
    )
    assert "`0009 -> 0008 -> 0009`" in normalized_database_roles
    assert "revision N+1" in normalized_worker
    assert "same five-field Skill pin" in normalized_worker


def test_fact_to_plan_status_tracks_all_three_merged_prs() -> None:
    pr_1_plan = (
        ROOT
        / "docs/superpowers/plans/2026-07-22-explicit-planning-start-authority.md"
    ).read_text(encoding="utf-8")
    pr_2_plan = (
        ROOT
        / "docs/superpowers/plans/2026-07-22-governed-fact-to-plan-walkthrough.md"
    ).read_text(encoding="utf-8")
    index = (ROOT / "docs/superpowers/README.md").read_text(encoding="utf-8")
    docs_index = (ROOT / "docs/README.md").read_text(encoding="utf-8")
    normalized_docs_index = " ".join(docs_index.split())

    for filename, plan, pull_request in (
        (
            "2026-07-22-explicit-planning-start-authority.md",
            pr_1_plan,
            57,
        ),
        (
            "2026-07-22-governed-fact-to-plan-walkthrough.md",
            pr_2_plan,
            58,
        ),
    ):
        current_status = plan.split("> **For agentic workers:**", 1)[0]
        normalized_status = " ".join(current_status.split())
        assert merged_fact_to_plan_status_errors(filename, plan) == []

        counterfactual = normalized_status.replace(
            f"**Implementation status:** Complete, merged as PR #{pull_request}, and "
            "released in v0.1.3.",
            "**Implementation status:** Complete locally for authority review.",
            1,
        )
        counterfactual_errors = merged_fact_to_plan_status_errors(
            filename, counterfactual
        )
        assert any("missing merged PR banner" in error for error in counterfactual_errors)
        assert any("stale status" in error for error in counterfactual_errors)
    assert (
        "| Governed Fact-to-Plan Closure and bilingual presentation | "
        "Implemented and released in v0.1.3 |"
    ) in index
    assert "PRs #57–#59 are released in v0.1.3" in normalized_docs_index

    adr = (ROOT / "docs/decisions/0010-explicit-planning-start-authority.md").read_text(
        encoding="utf-8"
    )
    task_reference = (
        ROOT / "docs/reference/agent-tasks-and-events.md"
    ).read_text(encoding="utf-8")
    http_reference = (ROOT / "docs/reference/http-api-v1.md").read_text(
        encoding="utf-8"
    )
    combined = "\n".join((adr, task_reference, http_reference))
    assert "planning starts automatically after confirmation" not in combined
    assert "POST /api/v1/cases/{case_id}/planning-start" not in combined


def test_chinese_first_portfolio_docs_are_discoverable_and_truthful() -> None:
    readmes = "\n".join(
        (ROOT / relative).read_text(encoding="utf-8")
        for relative in ("README.md", "README_CN.md")
    )
    docs = "\n".join(
        (ROOT / relative).read_text(encoding="utf-8")
        for relative in (
            "DESIGN.md",
            "docs/README.md",
            "docs/operations/connected-demo.md",
            "docs/operations/collaboration-walkthrough.md",
            "docs/design/demo-storyboard.md",
            "docs/design/route-map.md",
            "docs/design/state-and-interaction-matrix.md",
            "docs/design/projection-matrix.md",
        )
    )
    combined = " ".join((readmes, docs))

    for asset in (
        "night-voyager-portfolio-entry.png",
        "m5-advisor-ledger.png",
        "m5-family-receipt-timeline.png",
        "collaboration-confirmed-fact.png",
    ):
        assert asset in combined
    for token in (
        "zh-CN",
        "night-voyager:presentation-locale:v1",
        "/demo",
        "/demo/collaboration",
        "local synthetic",
        "provider-free",
    ):
        assert token in combined


def test_high_end_portfolio_docs_describe_the_current_v0_1_3_surface() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_cn = (ROOT / "README_CN.md").read_text(encoding="utf-8")
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    docs_index = (ROOT / "docs/README.md").read_text(encoding="utf-8")
    storyboard = (ROOT / "docs/design/demo-storyboard.md").read_text(
        encoding="utf-8"
    )
    route_map = (ROOT / "docs/design/route-map.md").read_text(encoding="utf-8")
    plans_index = (ROOT / "docs/superpowers/README.md").read_text(encoding="utf-8")
    previous_plan = (
        ROOT
        / "docs/superpowers/plans/2026-07-22-chinese-first-portfolio-presentation.md"
    ).read_text(encoding="utf-8")
    current_plan = (
        ROOT
        / "docs/superpowers/plans/2026-07-23-high-end-portfolio-entry.md"
    ).read_text(encoding="utf-8")

    for current_readme in (readme, readme_cn):
        for token in (
            "static",
            "local synthetic",
            "provider-free",
            "/demo/collaboration",
            "/demo",
            "AVIF",
            "WebP",
            "source PNG",
            "v0.1.3",
        ):
            assert token in current_readme
    assert "complete governed walkthrough begins at `/demo/collaboration`" in readme
    assert "focused advisor-family/evidence route remains at `/demo`" in readme
    assert "完整 governed walkthrough 从 `/demo/collaboration` 开始" in readme_cn
    assert "focused advisor-family/evidence route 保留在 `/demo`" in readme_cn

    for token in (
        "Virtual Night Voyage",
        "deep navy",
        "ivory",
        "champagne",
        "route atlas",
        "warm-paper ledger",
        "/demo",
        "/demo/collaboration",
    ):
        assert token in design
    assert "complete governed walkthrough" in storyboard
    assert "focused advisor-family/evidence route" in storyboard
    assert "complete governed walkthrough" in route_map
    assert "focused advisor-family/evidence route" in route_map

    for token in (
        "v0.1.5 is the current local synthetic portfolio release",
        "PRs #57–#59 are released in v0.1.3",
        "PR #60 and the route-presentation follow-up are released in v0.1.3",
    ):
        assert token in docs_index
    assert (
        "| Governed Fact-to-Plan Closure and bilingual presentation | "
        "Implemented and released in v0.1.3 |"
    ) in plans_index
    assert (
        "| High-End Portfolio Entry v1 | Implemented and released in v0.1.3 |"
        in plans_index
    )
    assert (
        "**Implementation status:** Complete, merged as PR #59, and released in v0.1.3."
        in previous_plan
    )
    current_status = current_plan.split("> **For agentic workers:**", 1)[0]
    normalized_current_status = " ".join(current_status.replace(">", "").split())
    for token in (
        "**Implementation status:** Complete, merged as PR #60, and released in v0.1.3.",
        "30–40 万元",
        "CNY 300,000–400,000",
        "305,500–400,000 CNY",
        "historical approved examples",
    ):
        assert token in normalized_current_status
    assert "Complete locally for authority review" not in current_status
    assert "complete on a local, unreleased branch for authority review" not in current_plan
    assert "completed [implementation plan]" in docs_index
    assert "PR #60 and the route-presentation follow-up are released in v0.1.3" in docs_index
    assert "complete locally for authority review" not in docs_index


def test_current_guidance_uses_complete_and_focused_route_roles() -> None:
    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    connected = (ROOT / "docs/operations/connected-demo.md").read_text(
        encoding="utf-8"
    )
    collaboration = (
        ROOT / "docs/operations/collaboration-walkthrough.md"
    ).read_text(encoding="utf-8")
    state_matrix = (
        ROOT / "docs/design/state-and-interaction-matrix.md"
    ).read_text(encoding="utf-8")
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    storyboard = (ROOT / "docs/design/demo-storyboard.md").read_text(
        encoding="utf-8"
    )

    assert "Keep `/demo` task-owning" in contributing
    assert "focused `/demo` route" in connected
    assert "complete governed walkthrough begins" in collaboration
    assert "task-free collaboration route" in state_matrix
    assert "task-free `/demo/collaboration` route" in design
    assert "task-owning `/demo` lifecycle" in design
    assert "focused demo's real task" in " ".join(storyboard.split())


def test_high_end_portfolio_evidence_is_bounded_and_release_verifiable() -> None:
    verifier = (ROOT / "scripts/verify_release.py").read_text(encoding="utf-8")
    screenshot = ROOT / "docs/assets/night-voyager-portfolio-entry.png"
    screenshot_sha256 = hashlib.sha256(screenshot.read_bytes()).hexdigest()

    for token in (
        "PORTFOLIO_ENTRY_SURFACE",
        "PORTFOLIO_SOURCE_SHA256",
        "PORTFOLIO_PRODUCTION_ASSETS",
        "verify_portfolio_entry_surface",
    ):
        assert token in verifier
    assert screenshot_sha256 != (
        "195c1a0d5fe1ff9d4c0ac3870b5b871419b7ac8b7f88daab0b5fc3513c756a81"
    )


def test_fact_to_plan_walkthrough_documents_same_case_explicit_authority() -> None:
    collaboration = (
        ROOT / "docs/operations/collaboration-walkthrough.md"
    ).read_text(encoding="utf-8")
    connected = (ROOT / "docs/operations/connected-demo.md").read_text(
        encoding="utf-8"
    )
    storyboard = (ROOT / "docs/design/demo-storyboard.md").read_text(
        encoding="utf-8"
    )
    route_map = (ROOT / "docs/design/route-map.md").read_text(encoding="utf-8")
    state_matrix = (
        ROOT / "docs/design/state-and-interaction-matrix.md"
    ).read_text(encoding="utf-8")
    projection_matrix = (ROOT / "docs/design/projection-matrix.md").read_text(
        encoding="utf-8"
    )
    facts_reference = (
        ROOT / "docs/reference/collaboration-and-confirmed-facts.md"
    ).read_text(encoding="utf-8")
    task_reference = (ROOT / "docs/reference/agent-tasks-and-events.md").read_text(
        encoding="utf-8"
    )
    skill_reference = (
        ROOT / "docs/reference/versioned-skills-and-runtime-pins.md"
    ).read_text(encoding="utf-8")

    normalized = {
        "collaboration": " ".join(collaboration.split()),
        "connected": " ".join(connected.split()),
        "storyboard": " ".join(storyboard.split()),
        "route_map": " ".join(route_map.split()),
        "state_matrix": " ".join(state_matrix.split()),
        "projection_matrix": " ".join(projection_matrix.split()),
        "facts_reference": " ".join(facts_reference.split()),
        "task_reference": " ".join(task_reference.split()),
        "skill_reference": " ".join(skill_reference.split()),
    }

    assert "Continue to governed planning" in normalized["collaboration"]
    assert "same Case" in normalized["collaboration"]
    assert "zero task" in normalized["collaboration"]
    assert "continued Case" in normalized["connected"]
    assert "ledger.canonical_task_inputs" in normalized["connected"]
    assert "one active `EventSource`" in normalized["connected"]
    assert "same Case" in normalized["storyboard"]
    assert "explicit task action" in normalized["storyboard"]
    assert "same-Case handoff" in normalized["route_map"]
    assert "no new BFF" in normalized["route_map"]
    assert "`handoff_validating`" in normalized["state_matrix"]
    assert "transient" in normalized["state_matrix"]
    assert "current confirmed facts" in normalized["projection_matrix"]
    assert "Case revision" in normalized["projection_matrix"]
    assert "does not create a task" in normalized["facts_reference"]
    assert "same Case" in normalized["facts_reference"]
    assert "task identity only from `advisor-ledger`" in normalized["task_reference"]
    assert "handoff itself never resolves a Skill pin" in normalized["skill_reference"]

    all_functional_docs = "\n".join(normalized.values())
    assert "planning starts automatically after confirmation" not in all_functional_docs
    assert "POST /api/v1/cases/{case_id}/planning-start" not in all_functional_docs


def test_current_collaboration_documents_do_not_revert_to_unreleased_or_deferred() -> None:
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    skill_operations = (ROOT / "docs/operations/skill-governance.md").read_text(
        encoding="utf-8"
    )
    collaboration_adr = (
        ROOT / "docs/decisions/0008-governed-collaboration-and-memory-authority.md"
    ).read_text(encoding="utf-8")

    assert "PR A and PR B are released in `v0.1.2`" in design
    assert "adds the unreleased governed-collaboration" not in design
    assert "unreleased versioned Skill catalog" not in design

    normalized_skill_operations = " ".join(skill_operations.split())
    assert "PR C's browser walkthrough and technical inspector are implemented" in (
        normalized_skill_operations
    )
    assert "remain deferred" not in skill_operations

    assert "PR C later implemented" in collaboration_adr
    assert "released in `v0.1.2`" in collaboration_adr
    assert "are also deferred" not in collaboration_adr


def test_collaboration_state_matrix_matches_executable_and_approved_plan() -> None:
    expected_persisted = {
        "bootstrapping_parent",
        "thread_ready",
        "message_submitting",
        "proposal_pending",
        "switching_to_advisor",
        "advisor_reviewing",
        "confirmation_submitting",
        "replan_required",
        "recoverable_error",
    }
    session = (ROOT / "web/lib/connected-demo/session-storage.ts").read_text(encoding="utf-8")
    reducer = (ROOT / "web/lib/collaboration-demo/reducer.ts").read_text(encoding="utf-8")
    plan = (
        ROOT
        / "docs/superpowers/plans/2026-07-16-collaboration-walkthrough-and-inspector.md"
    ).read_text(encoding="utf-8")
    matrix = (ROOT / "docs/design/state-and-interaction-matrix.md").read_text(encoding="utf-8")
    persisted_block = session.split("export type CollaborationPersistedPhase =", 1)[
        1
    ].split(";", 1)[0]
    executable = set(re.findall(r'"([a-z_]+)"', persisted_block))
    if '"recoverable_error"' in reducer:
        executable.add("recoverable_error")
    plan_block = plan.split("The collaboration reducer states are exactly", 1)[1].split(
        "Do not enlarge", 1
    )[0]
    approved = set(re.findall(r"`([a-z_]+)`", plan_block))
    matrix_block = matrix.split(
        "The task-free collaboration route has its own closed lifecycle:", 1
    )[1].split("The fresh UI defaults", 1)[0]
    documented = set(re.findall(r"\| `([a-z_]+)` \|", matrix_block))
    assert executable == expected_persisted
    assert approved == expected_persisted
    assert '"handoff_validating"' in reducer
    assert documented == expected_persisted | {"handoff_validating"}


def test_governed_plan_execution_dx_surface_is_evaluator_first() -> None:
    paths = {
        relative: (ROOT / relative).read_text(encoding="utf-8")
        for relative in (
            "README.md",
            "README_CN.md",
            "CONTRIBUTING.md",
            "DESIGN.md",
            "docs/README.md",
            "docs/design/demo-storyboard.md",
            "docs/design/state-and-interaction-matrix.md",
            "docs/design/projection-matrix.md",
            "docs/operations/plan-execution-walkthrough.md",
            "docs/operations/timeline-execution.md",
            "docs/reference/timeline-execution-contract.md",
            "docs/reference/http-api-v1.md",
            "docs/superpowers/README.md",
            "docs/superpowers/specs/2026-07-29-governed-plan-execution-and-reassessment-design.md",
            "docs/superpowers/plans/2026-07-29-governed-plan-execution-pr-a-implementation-plan.md",
            "docs/superpowers/plans/2026-07-29-governed-plan-execution-pr-b-implementation-plan.md",
            "docs/superpowers/plans/2026-07-29-governed-plan-execution-pr-c-implementation-plan.md",
        )
    }
    combined = " ".join("\n".join(paths.values()).split())
    for token in (
        "make proof",
        "make demo",
        "make compose-proof",
        "proof configuration and installed-wheel contract confirmed",
        "proof compose: PASS",
        "migration `0015`",
        "plan-execution-current-action.png",
        "plan-execution-advisor-review.png",
        "plan-execution-reassessment-mobile.png",
        "plan-execution-recovery-mobile.png",
        "semantic assertions",
        "screenshots are review evidence",
        "PR A/B/C are implemented, reviewed, merged",
        "included in the v0.1.5 release candidate",
        "Publication remains separately gated",
    ):
        assert token in combined

    contributing = paths["CONTRIBUTING.md"]
    for mapping in (
        "Domain/model",
        "Migration/SQL",
        "FastAPI/BFF",
        "Web state/recovery",
        "Presentation",
        "Docs/release surface",
    ):
        assert mapping in contributing

    template = (
        ROOT / ".github/ISSUE_TEMPLATE/proof-failure.yml"
    ).read_text(encoding="utf-8")
    for allowed in (
        "Command",
        "Public phase marker",
        "Public problem code",
        "Expected stable marker",
        "Observed stable marker",
        "Host available space",
        "Docker VM available space",
        "Compose project name",
        "Task-resource teardown result",
    ):
        assert allowed in template
    for forbidden in (
        "credentials",
        "cookies",
        "CSRF",
        ".env",
        "database URLs",
        "private paths",
        "raw database rows",
        "content-bearing Evidence",
    ):
        assert forbidden in template
