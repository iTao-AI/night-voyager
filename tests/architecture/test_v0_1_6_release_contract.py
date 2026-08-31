from __future__ import annotations

import ast
import hashlib
import json
import re
import tomllib
from pathlib import Path

from night_voyager.api import create_app

ROOT = Path(__file__).resolve().parents[2]
VERSION = "0.1.6"
DESCRIPTION = "Evidence-grounded advisor-to-family decision workflow with durable Agent tasks"
RELEASE_DOCUMENTS = (
    "docs/releases/v0.1.6.md",
    "docs/how-to/verify-v0.1.6-release.md",
)
RELEASE_HEADINGS = (
    "## Summary",
    "## Completion",
    "## Verification",
    "## Scope",
    "## Risk / Impact",
    "## Documentation impact",
)
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
    "docs/releases/v0.1.5.md": (
        "2064dbd68d2058a8f0d8f0886a09cd980953f2191a54f1bc0349dbda586e9179"
    ),
    "docs/how-to/verify-v0.1.5-release.md": (
        "d5e935c5d51f4492ea2f897540ce596bdc73e07b8999e4fc3afe066abef533ec"
    ),
}
ROOT_IDENTITY_BASELINE_DIGESTS = {
    "pyproject.toml": "bf5787b9aa88b5665fc99e29664f50ebac74996635390317f869bd74a1900805",
    "uv.lock": "370ed4ef110cb8e050e276a9baf752c0e2cfe8c50e7ee143115b113b5a4bd253",
    "web/package.json": "de78770cde96ffc5e1041bb348d21c273be0f72eb1b404bf7aa0a7c8ba4d3051",
    "web/package-lock.json": (
        "a197ff7f16618ff920de6fc83d14cea97476f4ed1fff6a9abd41aa49d76e71dc"
    ),
}


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _gate_blocks(how_to: str, gate: str) -> list[str]:
    section = how_to.split(f"## Gate {gate}", 1)[1].split("\n## ", 1)[0]
    return re.findall(r"```bash\n(.*?)```", section, flags=re.DOTALL)


def test_v0_1_6_identity_changes_only_night_voyager_root_versions() -> None:
    pyproject = tomllib.loads(_read("pyproject.toml"))
    uv_lock = tomllib.loads(_read("uv.lock"))
    package = json.loads(_read("web/package.json"))
    package_lock = json.loads(_read("web/package-lock.json"))
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

    version_replacements = {
        "pyproject.toml": ('version = "0.1.6"', 'version = "0.1.5"'),
        "uv.lock": ('version = "0.1.6"', 'version = "0.1.5"'),
        "web/package.json": ('"version": "0.1.6"', '"version": "0.1.5"'),
        "web/package-lock.json": ('"version": "0.1.6"', '"version": "0.1.5"'),
    }
    for relative, (current, baseline) in version_replacements.items():
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert current in source, relative
        restored = source.replace(current, baseline)
        assert hashlib.sha256(restored.encode("utf-8")).hexdigest() == (
            ROOT_IDENTITY_BASELINE_DIGESTS[relative]
        ), relative


def test_v0_1_6_release_records_and_historical_documents_are_bound() -> None:
    for relative in RELEASE_DOCUMENTS:
        assert (ROOT / relative).is_file(), relative

    for relative, expected in HISTORICAL_RELEASE_DIGESTS.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected, relative

    verifier = _read("scripts/verify_release.py")
    assert 'VERSION = "0.1.6"' in verifier
    assert "docs/releases/v0.1.5.md" in verifier
    assert "docs/how-to/verify-v0.1.5-release.md" in verifier
    assert "2064dbd68d2058a8f0d8f0886a09cd980953f2191a54f1bc0349dbda586e9179" in verifier
    assert "d5e935c5d51f4492ea2f897540ce596bdc73e07b8999e4fc3afe066abef533ec" in verifier


def test_v0_1_6_release_notes_use_approved_capabilities_and_non_claims() -> None:
    release = _read(RELEASE_DOCUMENTS[0])
    positions = [release.index(heading) for heading in RELEASE_HEADINGS]
    assert positions == sorted(positions)
    for heading, start in zip(RELEASE_HEADINGS, positions, strict=True):
        end = len(release)
        next_positions = [position for position in positions if position > start]
        if next_positions:
            end = min(next_positions)
        assert re.search(r"[\u4e00-\u9fff]", release[start:end]), heading

    for token in (
        "local synthetic portfolio release",
        "governed complementary-evidence Slice 0 safe stop",
        "evaluation_invalid",
        "PR #87",
        "information gain",
        "MkeCaptureArtifactV2",
        "candidate persistence",
        "Slice 1/2",
        "successful cross-project evidence loop",
        "advisor-centered presentation",
        "PR #94",
        "PR #95",
        "PR #97",
        "PR #98",
        "presentation evidence",
        "connected same-Case",
        "PR #103",
        "provider-free",
        "independent seeded Happy and Blocked scenarios",
        "no new migration",
        "no mutation authority",
        "no state transition",
        "no automatic retry",
        "no automatic successor",
        "PR #78",
        "Next.js `16.3.3`",
        "CodeQL",
        "not audit-zero",
        "INCOMPLETE_PENDING_LIVE_ACCEPTANCE",
        "no third DRA provider attempt",
        "no production deployment",
        "no real student records",
        "no real institutional coverage",
        "no advisor-team adoption",
        "no admissions outcome",
        "no business-benefit claim",
        "no HA/SLA",
        "GitHub-generated source archive",
        "release-prep does not change",
    ):
        assert token in release
    assert "all vulnerabilities" not in release.lower()


def test_v0_1_6_verification_guide_binds_gate_identity_archive_and_teardown() -> None:
    how_to = _read(RELEASE_DOCUMENTS[1])
    positions = [how_to.index(f"## Gate {gate}") for gate in "CDE"]
    assert positions == sorted(positions)

    for token in (
        "local synthetic portfolio release",
        "reviewed HEAD and hosted checks",
        "squash tree equality",
        "exact merge-SHA default-branch CI",
        "clean-main Gate C",
        "Git-free Gate D",
        "annotated tag and GitHub Release",
        "official public source archive Gate E",
        "git fetch origin --tags --prune",
        "git status --short --branch",
        "git rev-parse HEAD",
        "git rev-parse origin/main",
        'git -C "$repo_root" describe --tags --exact-match "$expected_commit"',
        'git -C "$repo_root" cat-file -t v0.1.6',
        'git -C "$repo_root" rev-parse v0.1.6^{tag}',
        'git -C "$repo_root" rev-parse v0.1.6^{commit}',
        "https://github.com/iTao-AI/night-voyager/archive/refs/tags/v0.1.6.tar.gz",
        'wc -c "$archive"',
        'shasum -a 256 "$archive"',
        'tar -xzf "$archive" -C "$tmp_dir"',
        'cd "$tmp_dir/night-voyager-0.1.6"',
        "make doctor MODE=dev",
        "make check",
        "make proof",
        "make compose-proof",
        "scripts/verify_release.py --tree-mode release",
        "Git-free",
        "prepublication archive",
        "annotated tag",
        "GitHub Release",
        "fresh extraction",
        "public source archive",
        "Never move the tag after publication",
        "Use the extracted source archive",
        "GitHub-generated source archives remain the only release artifacts",
        "no custom assets",
        "release_view[\"body\"].encode(\"utf-8\") == expected_body",
        "release_api[\"body\"].encode(\"utf-8\") == expected_body",
        "Do not force-move `v0.1.6`",
    ):
        assert token in how_to

    for gate in "CDE":
        blocks = _gate_blocks(how_to, gate)
        assert blocks, gate
        for block in blocks:
            assert block.splitlines()[0] == "set -euo pipefail"
        for block in (blocks[0],):
            assert "docker compose down --volumes --remove-orphans --rmi local" in block
            assert "docker compose ps --all --quiet" in block
            assert "make down" not in block
    for project in (
        "night-voyager-v0-1-6-gate-c-$$",
        "night-voyager-v0-1-6-gate-d-$$",
        "night-voyager-v0-1-6-gate-e-$$",
    ):
        assert project in how_to
    assert "--prefix=night-voyager-0.1.6/" in how_to
    assert 'test ! -e "$tmp_dir/extracted/night-voyager-0.1.6/.git"' in how_to


def test_current_guidance_reconciles_to_v0_1_6_without_unlocking_or_deploying() -> None:
    current_surfaces = (
        "README.md",
        "README_CN.md",
        "DESIGN.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "docs/README.md",
        "docs/operations/connected-demo.md",
        "docs/superpowers/README.md",
    )
    for relative in current_surfaces:
        source = _read(relative)
        assert "v0.1.6" in source, relative
        assert "local synthetic" in source, relative
        assert "provider-free" in source, relative
        assert ("not deployed" in source) or ("未部署" in source), relative

    readme = _read("README.md")
    readme_cn = _read("README_CN.md")
    docs_index = _read("docs/README.md")
    plans_index = _read("docs/superpowers/README.md")
    connected = _read("docs/operations/connected-demo.md")
    assert (
        "The current release boundary is v0.1.6, a local synthetic and provider-free "
        "portfolio release."
    ) in readme
    assert "publication remains separately gated" in readme
    assert "is included in v0.1.6 and is not deployed" in readme
    assert "当前 release boundary 是 v0.1.6" in readme_cn
    assert "已纳入 v0.1.6，仍未部署。" in readme_cn
    assert "v0.1.6 is the current local synthetic portfolio release" in docs_index
    assert "included in v0.1.6" in connected
    assert "included in v0.1.6 local synthetic portfolio release" in plans_index
    assert "evaluation_invalid" in readme
    assert "MkeCaptureArtifactV2" in readme
    assert "Slice 1/2" in readme
    assert "successful cross-project evidence loop" in readme
    assert "production deployment" in readme
    assert "v0.1.6 release" in readme
    assert "not included in stable v0.1.5" not in connected


def test_migration_head_and_provider_boundaries_remain_unchanged() -> None:
    revisions: set[str] = set()
    parents: set[str] = set()
    for path in sorted((ROOT / "migrations/versions").glob("[0-9][0-9][0-9][0-9]_*.py")):
        assignments: dict[str, object] = {}
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in {"revision", "down_revision"}
            ):
                assignments[node.targets[0].id] = ast.literal_eval(node.value)
            elif (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id in {"revision", "down_revision"}
                and node.value is not None
            ):
                assignments[node.target.id] = ast.literal_eval(node.value)
        revision = assignments.get("revision")
        parent = assignments.get("down_revision")
        assert isinstance(revision, str)
        revisions.add(revision)
        if isinstance(parent, str):
            parents.add(parent)
    assert revisions - parents == {"0015"}
    assert not list((ROOT / "migrations/versions").glob("0016_*.py"))

    provider_locks = _read("src/night_voyager/evidence_loop/provider_locks.py")
    assert 'Literal["v0.1.5"]' in provider_locks
    assert "mke-v0.1.5.tar" in provider_locks
    assert "multimodal_knowledge_engine-0.1.5-py3-none-any.whl" in provider_locks
