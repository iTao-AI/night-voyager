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
        "PR 1 and PR 2 merged; PR 3 implemented locally for authority review",
        "2026-07-22-explicit-planning-start-authority.md",
        "**Implementation status:** Implemented locally for authority review.",
    ),
    (
        "Governed Fact-to-Plan Closure and bilingual presentation",
        "PR 1 and PR 2 merged; PR 3 implemented locally for authority review",
        "2026-07-22-governed-fact-to-plan-walkthrough.md",
        "**Implementation status:** Complete locally for authority review.",
    ),
    (
        "Governed Fact-to-Plan Closure and bilingual presentation",
        "PR 1 and PR 2 merged; PR 3 implemented locally for authority review",
        "2026-07-22-chinese-first-portfolio-presentation.md",
        "**Implementation status:** Complete locally for authority review.",
    ),
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


def test_fact_to_plan_status_tracks_merged_pr1_pr2_and_local_pr3() -> None:
    spec = (
        ROOT
        / "docs/superpowers/specs/2026-07-22-governed-fact-to-plan-closure-design.md"
    ).read_text(encoding="utf-8")
    plan = (
        ROOT
        / "docs/superpowers/plans/2026-07-22-explicit-planning-start-authority.md"
    ).read_text(encoding="utf-8")
    index = (ROOT / "docs/superpowers/README.md").read_text(encoding="utf-8")
    docs_index = (ROOT / "docs/README.md").read_text(encoding="utf-8")
    normalized_spec = " ".join(spec.split())
    normalized_plan = " ".join(plan.split())
    normalized_docs_index = " ".join(docs_index.split())

    assert "PR 1 is merged" in normalized_spec
    assert "PR 2 is merged" in normalized_spec
    assert "PR 3 is implemented locally for authority review" in normalized_spec
    assert (
        "**Implementation status:** Implemented locally for authority review."
        in normalized_plan
    )
    assert (
        "| Governed Fact-to-Plan Closure and bilingual presentation | "
        "PR 1 and PR 2 merged; PR 3 implemented locally for authority review |"
    ) in index
    assert "PR 1 and PR 2 are merged" in normalized_docs_index
    assert "PR 3 is implemented locally for authority review" in normalized_docs_index

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
        "The secondary collaboration route has its own closed lifecycle:", 1
    )[1].split("The fresh UI defaults", 1)[0]
    documented = set(re.findall(r"\| `([a-z_]+)` \|", matrix_block))
    assert executable == expected_persisted
    assert approved == expected_persisted
    assert '"handoff_validating"' in reducer
    assert documented == expected_persisted | {"handoff_validating"}
