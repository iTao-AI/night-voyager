from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import textwrap
import tomllib
from pathlib import Path

from night_voyager.api import create_app

ROOT = Path(__file__).resolve().parents[2]
VERSION = "0.1.5"
DESCRIPTION = "Evidence-grounded advisor-to-family decision workflow with durable Agent tasks"
HISTORICAL_RELEASE_DIGESTS = {
    "docs/releases/v0.1.0.md": "a3251cdb572b4d982f989917f7e44d111cf887cf7fc8d75629cdd69c393d3a93",
    "docs/how-to/verify-v0.1.0-release.md": (
        "b65e18c6dc0e193e2de445ad41930230846bea3abfe43304f58f4cd133275ea3"
    ),
    "docs/releases/v0.1.1.md": "0e7724ca54a9d9c8b3ed403f6bbbd86c04dde3ee79e0644e95ee3ccf90513ab2",
    "docs/how-to/verify-v0.1.1-release.md": (
        "3e20b41e3256c275d557e6165e7e224a95a3a642286f6993da209a51aebe8f16"
    ),
    "docs/releases/v0.1.2.md": (
        "f09019619a086a8b548c3ab4a9c313a002c513308069b30162ab2816bb04e7fc"
    ),
    "docs/how-to/verify-v0.1.2-release.md": (
        "5ffba625c4eb4dd78330a0a51b96065de763f5aab8f0a32928c3bf65cd0f3060"
    ),
    "docs/releases/v0.1.3.md": (
        "aa1f7eb6e709641cb8fe5155a95d892ac1f5f441610f431a6f430c784ee6f3c2"
    ),
    "docs/how-to/verify-v0.1.3-release.md": (
        "1f62ca4b1c8db8caa0613df3851ea79b48afb6c5696b590d8b6cc5caa4986162"
    ),
    "docs/releases/v0.1.4.md": (
        "cf13ff4cdee937ba111186bbc73258712695a190d8317d9085024344b799f3da"
    ),
    "docs/how-to/verify-v0.1.4-release.md": (
        "6fab5465f24c6765910814a7f554c9c57971c6e6c613d194f1a25e8a9ddf0f45"
    ),
}


def _gate_bash_blocks(how_to: str, gate: str) -> list[str]:
    section = how_to.split(f"## Gate {gate}", 1)[1].split("\n## ", 1)[0]
    return re.findall(r"```bash\n(.*?)```", section, flags=re.DOTALL)


def _run_gate_c(
    tmp_path: Path,
    *,
    branch: str = "main",
    head: str = "reviewed-commit",
    origin_main: str = "reviewed-commit",
    dirty: str = "",
    down_status: int = 0,
    residue: str = "",
) -> subprocess.CompletedProcess[str]:
    how_to = (ROOT / "docs/how-to/verify-v0.1.5-release.md").read_text(
        encoding="utf-8"
    )
    block = _gate_bash_blocks(how_to, "C")[0]
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    tool_stub = textwrap.dedent(
        """\
        #!/bin/sh
        tool=$(basename "$0")
        printf '%s|%s|%s\n' "$tool" "${COMPOSE_PROJECT_NAME:-unset}" "$*" >> "$STUB_LOG"
        case "$tool:$*" in
            "git:status --porcelain") printf '%s' "$STUB_DIRTY" ;;
            "git:branch --show-current") printf '%s\n' "$STUB_BRANCH" ;;
            "git:rev-parse HEAD") printf '%s\n' "$STUB_HEAD" ;;
            "git:rev-parse origin/main") printf '%s\n' "$STUB_ORIGIN_MAIN" ;;
            "make:down") exit "$STUB_DOWN_STATUS" ;;
            "docker:compose ps --all --quiet") printf '%s' "$STUB_RESIDUE" ;;
        esac
        """
    )
    for tool in ("git", "make", "uv", "npm", "docker"):
        path = bin_dir / tool
        path.write_text(tool_stub, encoding="utf-8")
        path.chmod(0o755)
    environment = os.environ.copy()
    environment.update(
        PATH=f"{bin_dir}:/usr/bin:/bin",
        STUB_LOG=str(tmp_path / "gate.log"),
        STUB_BRANCH=branch,
        STUB_HEAD=head,
        STUB_ORIGIN_MAIN=origin_main,
        STUB_DIRTY=dirty,
        STUB_DOWN_STATUS=str(down_status),
        STUB_RESIDUE=residue,
    )
    return subprocess.run(
        ["bash", "-c", block],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_v0_1_5_copyable_bash_blocks_fail_fast_on_an_injected_prior_failure() -> None:
    how_to = (ROOT / "docs/how-to/verify-v0.1.5-release.md").read_text(
        encoding="utf-8"
    )
    blocks = [block for gate in "CDE" for block in _gate_bash_blocks(how_to, gate)]

    assert blocks
    for block in blocks:
        prologue = block.splitlines()[0]
        result = subprocess.run(
            ["bash", "-c", f"{prologue}\nfalse\ntrue"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode != 0, block


def test_gate_c_rejects_dirty_non_main_or_non_merged_identity(tmp_path: Path) -> None:
    assert _run_gate_c(tmp_path / "clean").returncode == 0
    assert _run_gate_c(tmp_path / "dirty", dirty=" M changed").returncode != 0
    assert _run_gate_c(tmp_path / "branch", branch="release-candidate").returncode != 0
    assert _run_gate_c(tmp_path / "head", head="different-commit").returncode != 0


def test_gate_c_teardown_is_fail_closed_and_reads_back_the_same_project(
    tmp_path: Path,
) -> None:
    down_failure = _run_gate_c(tmp_path / "down", down_status=9)
    residue_failure = _run_gate_c(tmp_path / "residue", residue="container-id")

    assert down_failure.returncode != 0
    assert residue_failure.returncode != 0
    for case in ("down", "residue"):
        log_lines = (tmp_path / case / "gate.log").read_text(encoding="utf-8").splitlines()
        projects = {line.split("|", 2)[1] for line in log_lines}
        assert len(projects) == 1
        assert projects.pop().startswith("night-voyager-v0-1-5-gate-c-")


def test_v0_1_5_current_authority_and_public_claims_are_unambiguous() -> None:
    adr = (
        ROOT / "docs/decisions/0013-governed-timeline-execution-authority.md"
    ).read_text(encoding="utf-8")
    release = (ROOT / "docs/releases/v0.1.5.md").read_text(encoding="utf-8")
    how_to = (ROOT / "docs/how-to/verify-v0.1.5-release.md").read_text(
        encoding="utf-8"
    )
    normalized_adr = " ".join(adr.split())

    assert "v0.1.4 remains migration `0013`" in normalized_adr
    assert "v0.1.5 release candidate current head is `0015`" in normalized_adr
    assert (
        "timeline transition authority remains owned by migration `0014`"
        in normalized_adr
    )
    assert "migration `0015` only closes deterministic demo identity" in normalized_adr
    assert "Career authority review" not in how_to
    assert "independent maintainer review" in how_to
    assert (
        "except for the declared version identities, release-prep does not change "
        "migrations, runtime behavior, backend/domain product logic, BFF/API endpoints "
        "or schemas, dependency choices, Dockerfiles, or Compose policy"
        in release
    )


def test_current_release_identity_is_v0_1_5_without_dependency_drift() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    uv_lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    package = json.loads((ROOT / "web/package.json").read_text(encoding="utf-8"))
    package_lock = json.loads(
        (ROOT / "web/package-lock.json").read_text(encoding="utf-8")
    )
    locked_project = next(
        item for item in uv_lock["package"] if item.get("name") == "night-voyager"
    )

    assert pyproject["project"]["version"] == VERSION
    assert pyproject["project"]["description"] == DESCRIPTION
    assert locked_project["version"] == VERSION
    assert package["version"] == VERSION
    assert package_lock["version"] == VERSION
    assert package_lock["packages"][""]["version"] == VERSION
    assert create_app().version == VERSION
    verifier = (ROOT / "scripts/verify_release.py").read_text(encoding="utf-8")
    assert f'VERSION = "{VERSION}"' in verifier


def test_current_release_entries_point_to_v0_1_5_and_keep_history() -> None:
    current_entries = {
        "README.md": (
            "docs/releases/v0.1.5.md",
            "docs/how-to/verify-v0.1.5-release.md",
            "local synthetic portfolio release",
        ),
        "README_CN.md": (
            "docs/releases/v0.1.5.md",
            "docs/how-to/verify-v0.1.5-release.md",
            "local synthetic portfolio release",
        ),
        "docs/README.md": (
            "releases/v0.1.5.md",
            "how-to/verify-v0.1.5-release.md",
            "local synthetic portfolio release",
        ),
        "CONTRIBUTING.md": ("v0.1.5", "local synthetic portfolio release"),
        "SECURITY.md": ("v0.1.5", "local synthetic portfolio release"),
        "DESIGN.md": ("v0.1.5", "local synthetic portfolio release"),
    }
    for relative, tokens in current_entries.items():
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert all(token in source for token in tokens), relative

    for relative in ("README.md", "README_CN.md", "docs/README.md"):
        source = (ROOT / relative).read_text(encoding="utf-8")
        for historical_version in ("v0.1.0", "v0.1.1", "v0.1.2", "v0.1.3", "v0.1.4"):
            assert historical_version in source, (relative, historical_version)


def test_v0_1_5_release_notes_define_capability_and_non_claim_scope() -> None:
    release = (ROOT / "docs/releases/v0.1.5.md").read_text(encoding="utf-8")
    headings = (
        "## Summary",
        "## Completion",
        "## Verification",
        "## Scope",
        "## Risk / Impact",
        "## Documentation impact",
    )
    assert [release.index(heading) for heading in headings] == sorted(
        release.index(heading) for heading in headings
    )
    for token in (
        "local synthetic portfolio release",
        "migration `0015`",
        "PR #80",
        "governed timeline execution",
        "PR #83",
        "recovery",
        "PR #84",
        "reassessment",
        "session",
        "task",
        "receipt",
        "reconciliation",
        "PR #85",
        "professional presentation",
        "evaluator-first DX",
        "PR #78",
        "dependency maintenance",
        "sharp",
        "GHSA-f88m-g3jw-g9cj",
        "brace-expansion",
        "minimatch",
        "not audit-zero",
        "PR #81",
        "PR #82",
        "CI verification maintenance",
        "INCOMPLETE_PENDING_LIVE_ACCEPTANCE",
        "two",
        "zero cited Evidence",
        "no third provider attempt",
        "GitHub-generated source archive",
        "no production deployment",
        "no real users",
        "no real schools or student data",
        "no admissions outcome",
        "no business-benefit claim",
        "no HA or SLA",
        "except for the declared version identities, release-prep does not change "
        "migrations, runtime behavior, backend/domain product logic, BFF/API endpoints "
        "or schemas, dependency choices, Dockerfiles, or Compose policy",
    ):
        assert token in release

    assert "all vulnerabilities" not in release.lower()
    assert "audit-zero" in release


def test_v0_1_5_verification_guide_defines_gate_c_d_and_e() -> None:
    how_to = (ROOT / "docs/how-to/verify-v0.1.5-release.md").read_text(
        encoding="utf-8"
    )
    for token in (
        "local synthetic portfolio release",
        "Gate C",
        "Gate D",
        "Gate E",
        "git fetch origin --tags --prune",
        "git status --short --branch",
        "git rev-parse HEAD",
        "git rev-parse origin/main",
        'git -C "$repo_root" describe --tags --exact-match "$expected_commit"',
        'git -C "$repo_root" cat-file -t v0.1.5',
        'git -C "$repo_root" rev-parse v0.1.5^{tag}',
        'git -C "$repo_root" rev-parse v0.1.5^{commit}',
        "https://github.com/iTao-AI/night-voyager/archive/refs/tags/v0.1.5.tar.gz",
        'cd "$tmp_dir/night-voyager-0.1.5"',
        "make doctor MODE=dev",
        "make check",
        "make proof",
        "make compose-proof",
        "make down",
        "docker compose ps --all",
        "scripts/verify_release.py --tree-mode release",
        "Git-free",
        "prepublication archive",
        "annotated tag",
        "GitHub Release",
        "fresh extraction",
        "public source archive",
        "Never move the tag after publication",
        "Use the extracted source archive",
        "Do not force-move `v0.1.5`",
        "normal pull request",
    ):
        assert token in how_to


def test_published_release_documents_remain_byte_identical() -> None:
    for relative, expected in HISTORICAL_RELEASE_DIGESTS.items():
        actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        assert actual == expected, relative


def test_release_documentation_skills_do_not_expand_authority() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for token in (
        "Every release PR must run the GStack `document-release` targeted audit before merge",
        "Invoking a Skill does not authorize push, PR mutation, merge, tag, GitHub Release",
        "Use `document-generate` only to close a concrete, in-scope documentation gap",
        "Do not generate every Diataxis quadrant mechanically",
    ):
        assert token in agents
