from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
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


def test_v0_1_4_release_notes_define_current_capability_and_non_claim_scope() -> None:
    release = (ROOT / "docs/releases/v0.1.4.md").read_text(encoding="utf-8")
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
        "migration `0013`",
        "capture",
        "recovery",
        "Stage 2–4",
        "evaluation",
        "semantic candidate-freeze evidence",
        "01ba21f2996769e68cbc88f4bb0596740df27f6b",
        "generic-strict-citation@1",
        "not a DRA v0.1.6 release capability",
        "versioned planning revision authority",
        "deterministic old/new comparison",
        "fresh advisor reauthorization",
        "only-current family decision",
        "zh-CN",
        "en",
        "React",
        "Next.js",
        "PostCSS",
        "Dependabot #8",
        "Dependabot #9",
        "FIXED",
        "Dependabot #7",
        "OPEN",
        "GHSA-f88m-g3jw-g9cj",
        "brace-expansion",
        "minimatch",
        "ESLint",
        "not audit-zero",
        "INCOMPLETE_PENDING_LIVE_ACCEPTANCE",
        "zero cited Evidence",
        "before candidate import",
        "no third provider attempt",
        "GitHub-generated source archive",
        "no production deployment",
        "no source-truth or provider-quality claim",
        "no real student or school coverage",
        "no advisor-team adoption",
        "no admissions outcome",
        "no HA or SLA",
        "no business-benefit claim",
        "release-prep does not change migration, API, runtime behavior, or dependency tree",
    ):
        assert token in release


def test_v0_1_4_release_notes_reject_unsupported_security_claims() -> None:
    release = (ROOT / "docs/releases/v0.1.4.md").read_text(encoding="utf-8")

    assert "not audit-zero" in release
    assert "all vulnerabilities" not in release.lower()


def test_v0_1_4_verification_guide_defines_gate_c_d_and_e() -> None:
    how_to = (ROOT / "docs/how-to/verify-v0.1.4-release.md").read_text(
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
        'git -C "$repo_root" cat-file -t v0.1.4',
        'git -C "$repo_root" rev-parse v0.1.4^{tag}',
        'git -C "$repo_root" rev-parse v0.1.4^{commit}',
        'curl --fail --location --output "$archive"',
        "https://github.com/iTao-AI/night-voyager/archive/refs/tags/v0.1.4.tar.gz",
        'wc -c "$archive"',
        'shasum -a 256 "$archive"',
        'tar -xzf "$archive" -C "$tmp_dir"',
        'cd "$tmp_dir/night-voyager-0.1.4"',
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
        "Do not force-move `v0.1.4`",
        "normal pull request",
    ):
        assert token in how_to


def test_gate_d_archive_smoke_preserves_repo_context_and_official_archive_shape() -> None:
    how_to = (ROOT / "docs/how-to/verify-v0.1.4-release.md").read_text(
        encoding="utf-8"
    )

    for token in (
        'repo_root="$(git rev-parse --show-toplevel)"',
        "--prefix=night-voyager-0.1.4/",
        'test ! -e "$tmp_dir/extracted/night-voyager-0.1.4/.git"',
        '(\n  cd "$tmp_dir/extracted/night-voyager-0.1.4"',
        'git -C "$repo_root" fetch origin --tags --prune',
        'test "$(git -C "$repo_root" rev-parse origin/main)" = "$expected_commit"',
        'test "$(git -C "$repo_root" rev-parse v0.1.4^{commit})" = "$expected_commit"',
    ):
        assert token in how_to


def test_gate_d_reads_back_exact_public_github_release_state() -> None:
    how_to = (ROOT / "docs/how-to/verify-v0.1.4-release.md").read_text(
        encoding="utf-8"
    )

    for token in (
        "gh release view v0.1.4",
        "--repo iTao-AI/night-voyager",
        "--json tagName,targetCommitish,isDraft,isPrerelease,assets,url,publishedAt,body",
        "gh api repos/iTao-AI/night-voyager/releases/tags/v0.1.4",
        'release_view["tagName"] == release_api["tag_name"] == "v0.1.4"',
        'release_view["targetCommitish"] == release_api["target_commitish"] == "main"',
        'release_view["isDraft"] is False',
        'release_api["draft"] is False',
        'release_view["isPrerelease"] is False',
        'release_api["prerelease"] is False',
        'release_view["assets"] == release_api["assets"] == []',
        'release_view["publishedAt"] == release_api["published_at"]',
        'release_view["url"] == release_api["html_url"]',
        'repo_root / "docs/releases/v0.1.4.md"',
        'release_view["body"].encode("utf-8") == expected_body',
        'release_api["body"].encode("utf-8") == expected_body',
        "GitHub-generated source archives remain the only release artifacts",
    ):
        assert token in how_to


def test_published_v0_1_4_release_keeps_exact_0013_migration_identity() -> None:
    release = (ROOT / "docs/releases/v0.1.4.md").read_text(encoding="utf-8")
    assert "当前 development 与 release identity 使用 migration `0013`；" in release
    assert (ROOT / "migrations/versions/0013_planning_revision_demo_seed.py").is_file()


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
        "duplicate existing",
    ):
        assert token in agents
