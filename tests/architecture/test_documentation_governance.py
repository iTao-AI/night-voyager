from __future__ import annotations

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
        "PR A, PR B, and PR C implemented post-v0.1.1; unreleased",
        "2026-07-16-governed-conversation-memory-authority.md",
        "**Implementation status:** Complete.",
    ),
    (
        "Governed Collaboration Core v1",
        "PR A, PR B, and PR C implemented post-v0.1.1; unreleased",
        "2026-07-16-versioned-skill-runtime-pinning.md",
        "**Implementation status:** Implemented locally",
    ),
    (
        "Governed Collaboration Core v1",
        "PR A, PR B, and PR C implemented post-v0.1.1; unreleased",
        "2026-07-16-collaboration-walkthrough-and-inspector.md",
        "**Implementation status:** Implemented locally",
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
            "unreleased post-v0.1.1 backend capability",
            "PR B, PR C, and live-provider work remain unimplemented",
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
