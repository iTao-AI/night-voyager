from __future__ import annotations

import hashlib
import importlib.util
import shutil
import struct
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load_verifier():
    path = ROOT / "scripts/verify_release.py"
    spec = importlib.util.spec_from_file_location("verify_release", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def copy_release_surface(destination: Path) -> None:
    for relative in (
        "pyproject.toml",
        "README.md",
        "README_CN.md",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "docs/README.md",
        "docs/releases/v0.1.0.md",
        "docs/how-to/verify-v0.1.0-release.md",
        "docs/releases/v0.1.1.md",
        "docs/how-to/verify-v0.1.1-release.md",
        "docs/releases/v0.1.2.md",
        "docs/how-to/verify-v0.1.2-release.md",
        "docs/releases/v0.1.3.md",
        "docs/how-to/verify-v0.1.3-release.md",
    ):
        source = ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def test_release_verifier_checks_the_public_v0_1_3_surface(
    capsys: pytest.CaptureFixture[str],
) -> None:
    verifier = load_verifier()

    verifier.verify_release_surface()

    output = capsys.readouterr().out
    assert "proof release surface: v0.1.3 local synthetic portfolio contract confirmed" in output


def test_release_verifier_checks_the_governed_mixed_planning_surface(
    capsys: pytest.CaptureFixture[str],
) -> None:
    verifier = load_verifier()

    verifier.verify_dra_surface()

    output = capsys.readouterr().out
    assert "proof DRA surface: offline governed mixed decision closure confirmed" in output


@pytest.mark.parametrize(
    ("relative", "required", "message"),
    (
        (
            "docs/how-to/verify-v0.1.1-release.md",
            "git cat-file -t v0.1.1",
            "published release document drift",
        ),
        (
            "docs/how-to/verify-v0.1.1-release.md",
            "https://github.com/iTao-AI/night-voyager/archive/refs/tags/v0.1.1.tar.gz",
            "published release document drift",
        ),
        (
            "docs/how-to/verify-v0.1.1-release.md",
            "Do not force-move `v0.1.1`",
            "published release document drift",
        ),
        (
            "docs/releases/v0.1.1.md",
            "## Risk / Impact",
            "published release document drift",
        ),
        (
            "docs/releases/v0.1.1.md",
            "UNTRUSTED_CANDIDATE",
            "published release document drift",
        ),
        (
            "docs/releases/v0.1.1.md",
            "australia_program_fit",
            "published release document drift",
        ),
        (
            "docs/releases/v0.1.1.md",
            "Live provider proof was not run",
            "published release document drift",
        ),
    ),
)
def test_release_verifier_rejects_missing_publication_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    relative: str,
    required: str,
    message: str,
) -> None:
    verifier = load_verifier()
    copy_release_surface(tmp_path)
    target = tmp_path / relative
    source = target.read_text(encoding="utf-8")
    assert required in source
    target.write_text(source.replace(required, "", 1), encoding="utf-8")
    monkeypatch.setattr(verifier, "ROOT", tmp_path)

    with pytest.raises(SystemExit, match=message):
        verifier.verify_release_surface()


@pytest.mark.parametrize(
    "relative",
    (
        "docs/releases/v0.1.0.md",
        "docs/how-to/verify-v0.1.0-release.md",
        "docs/releases/v0.1.1.md",
        "docs/how-to/verify-v0.1.1-release.md",
    ),
)
def test_release_verifier_rejects_mutated_published_release_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relative: str
) -> None:
    verifier = load_verifier()
    copy_release_surface(tmp_path)
    target = tmp_path / relative
    target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    monkeypatch.setattr(verifier, "ROOT", tmp_path)

    with pytest.raises(SystemExit, match="published release document drift"):
        verifier.verify_release_surface()


def test_release_verifier_registers_collaboration_authority_without_version_change() -> None:
    verifier = load_verifier()
    assert verifier.VERSION == "0.1.3"
    assert {
        "collaboration_threads",
        "message_events",
        "memory_candidates",
        "memory_candidate_verifications",
        "confirmed_facts",
        "case_revision_confirmed_fact_refs",
    } == verifier.COLLABORATION_TABLES
    assert {
        "create_collaboration_thread",
        "append_collaboration_message",
        "propose_memory_candidate",
        "verify_memory_candidate",
        "read_collaboration_thread",
        "read_collaboration_messages",
        "read_memory_candidates",
        "read_confirmed_facts",
    } == verifier.COLLABORATION_API_FUNCTIONS
    source = (ROOT / "scripts/verify_release.py").read_text(encoding="utf-8")
    assert '"read_confirmed_facts": (' in source
    assert '"uuid, uuid, text, uuid, integer, text, integer, integer"' in source


def test_release_verifier_checks_the_collaboration_authority_surface(
    capsys: pytest.CaptureFixture[str],
) -> None:
    verifier = load_verifier()

    verifier.verify_collaboration_surface()

    output = capsys.readouterr().out
    assert (
        "proof collaboration surface: governed conversation and memory authority confirmed"
        in output
    )


@pytest.mark.parametrize(
    "relative",
    (
        "web/app/demo/collaboration/page.tsx",
        "web/app/api/demo/cases/[caseId]/collaboration-thread/route.ts",
        "web/app/api/demo/collaboration-threads/[threadId]/messages/route.ts",
        "web/app/api/demo/messages/[messageId]/memory-candidates/route.ts",
        "web/app/api/demo/cases/[caseId]/memory-candidates/route.ts",
        "web/app/api/demo/memory-candidates/[candidateId]/verification-decisions/route.ts",
        "web/app/api/demo/cases/[caseId]/confirmed-facts/route.ts",
        "web/app/api/demo/cases/[caseId]/planning-skill-inspector/route.ts",
        "web/components/collaboration-demo/CollaborationDemo.tsx",
        "web/components/skill-inspector/PlanningSkillInspector.tsx",
        "web/lib/collaboration-demo/use-collaboration-demo.ts",
        "web/e2e/collaboration-demo.spec.ts",
        "web/playwright.compose.config.ts",
        "docs/assets/collaboration-confirmed-fact.png",
        "README.md",
        "README_CN.md",
    ),
)
def test_pr_c_browser_verifier_rejects_each_missing_critical_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    relative: str,
) -> None:
    verifier = load_verifier()
    for item in verifier.PR_C_BROWSER_SURFACE:
        source = ROOT / item
        target = tmp_path / item
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (tmp_path / relative).unlink()
    monkeypatch.setattr(verifier, "ROOT", tmp_path)

    with pytest.raises(SystemExit, match="PR C browser proof surface incomplete"):
        verifier.verify_pr_c_browser_surface()


def test_release_verifier_freezes_the_cross_runtime_lock_order() -> None:
    source = (ROOT / "scripts/verify_release.py").read_text(encoding="utf-8")
    assert '"CREATE OR REPLACE FUNCTION app.persist_planning_result("' in source
    assert '"LEGACY_PLANNING_PERSISTENCE_SQL"' in source
    assert '"Case FOR UPDATE -> superseded PlanningRun update"' in source
    assert '"planning result lock order drift"' in source


def test_release_verifier_registers_skill_authority_without_version_change() -> None:
    verifier = load_verifier()

    assert verifier.VERSION == "0.1.3"
    assert not hasattr(verifier, "LOCKED_FASTAPI_VERSION")
    assert verifier.FASTAPI_VERSION_FLOOR == (0, 139, 2)
    assert verifier.FASTAPI_VERSION_CEILING == (0, 140)
    source = (ROOT / "scripts/verify_release.py").read_text(encoding="utf-8")
    assert "FastAPI >=0.139.2,<0.140" in source
    assert {
        "skill_definitions",
        "skill_versions",
        "skill_change_candidates",
        "skill_evaluation_results",
        "skill_activation_events",
    } == verifier.SKILL_TABLES
    assert {
        "create_skill_change_candidate",
        "record_skill_candidate_evaluation",
        "promote_skill_change_candidate",
        "rollback_skill_activation",
        "list_skill_catalog",
        "get_skill_catalog_item",
        "load_skill_candidate_context",
        "inspect_planning_skill",
    } == verifier.SKILL_API_FUNCTIONS
    assert {
        "load_agent_task_skill_pin",
        "load_persisted_synthetic_planning_snapshot",
    } == verifier.SKILL_WORKER_FUNCTIONS


def test_release_verifier_checks_the_versioned_skill_surface(
    capsys: pytest.CaptureFixture[str],
) -> None:
    verifier = load_verifier()

    verifier.verify_skill_surface()

    output = capsys.readouterr().out
    assert (
        "proof Skill surface: six governed definitions and packaged runtime pins confirmed"
    ) in output


def test_collaboration_walkthrough_is_publicly_discoverable_and_evidenced() -> None:
    walkthrough_path = ROOT / "docs/operations/collaboration-walkthrough.md"
    screenshot_path = ROOT / "docs/assets/collaboration-confirmed-fact.png"

    assert walkthrough_path.is_file()
    assert screenshot_path.is_file()

    png = screenshot_path.read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", png[16:24])
    assert width == 1440
    assert height >= 900

    readmes = "\n".join(
        (ROOT / relative).read_text(encoding="utf-8")
        for relative in ("README.md", "README_CN.md")
    )
    docs_index = (ROOT / "docs/README.md").read_text(encoding="utf-8")
    assert "complete governed walkthrough" in readmes
    assert "focused advisor-family/evidence route" in readmes
    assert "collaboration-confirmed-fact.png" in readmes
    assert "collaboration-walkthrough.md" in docs_index
    assert "PR C" in docs_index and "implemented" in docs_index
    assert "released in v0.1.2" in docs_index


def test_fact_to_plan_walkthrough_is_publicly_discoverable_and_evidenced() -> None:
    required_artifacts = (
        "scripts/verify_fact_to_plan_flow.py",
        "tests/integration/connected_demo/test_fact_to_plan_flow.py",
        "web/e2e/fact-to-plan.spec.ts",
    )
    assert all((ROOT / relative).is_file() for relative in required_artifacts)

    readmes = "\n".join(
        (ROOT / relative).read_text(encoding="utf-8")
        for relative in ("README.md", "README_CN.md")
    )
    docs_index = (ROOT / "docs/README.md").read_text(encoding="utf-8")
    walkthrough = (
        ROOT / "docs/operations/collaboration-walkthrough.md"
    ).read_text(encoding="utf-8")
    connected = (ROOT / "docs/operations/connected-demo.md").read_text(
        encoding="utf-8"
    )
    combined = " ".join((readmes, docs_index, walkthrough, connected))

    assert "same-Case" in combined
    assert "Continue to governed planning" in combined
    assert "local synthetic" in combined
    assert "provider-free" in combined
    assert "released in v0.1.3" in combined
    assert "creates no task" in combined or "zero task" in combined


def test_chinese_first_portfolio_screenshots_and_historical_release_artifacts() -> None:
    screenshots = (
        "docs/assets/night-voyager-portfolio-entry.png",
        "docs/assets/m5-advisor-ledger.png",
        "docs/assets/m5-family-receipt-timeline.png",
        "docs/assets/collaboration-confirmed-fact.png",
    )
    for relative in screenshots:
        png = (ROOT / relative).read_bytes()
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        width, height = struct.unpack(">II", png[16:24])
        assert width == 1440
        assert height >= 900

    browser_source = "\n".join(
        (ROOT / relative).read_text(encoding="utf-8")
        for relative in (
            "web/e2e/fact-to-plan.spec.ts",
            "web/e2e/connected-demo.spec.ts",
            "web/e2e/collaboration-demo.spec.ts",
        )
    )
    for token in (
        "当前决策阶段",
        "需要重新规划",
        "家庭决定回执",
        "行动时间线",
        "night-voyager-portfolio-entry.png",
        "m5-advisor-ledger.png",
        "m5-family-receipt-timeline.png",
        "collaboration-confirmed-fact.png",
    ):
        assert token in browser_source

    immutable_hashes = {
        "docs/releases/v0.1.2.md": (
            "f09019619a086a8b548c3ab4a9c313a002c513308069b30162ab2816bb04e7fc"
        ),
        "docs/how-to/verify-v0.1.2-release.md": (
            "5ffba625c4eb4dd78330a0a51b96065de763f5aab8f0a32928c3bf65cd0f3060"
        ),
    }
    for relative, expected in immutable_hashes.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected


def test_release_verifier_checks_the_high_end_portfolio_entry(
    capsys: pytest.CaptureFixture[str],
) -> None:
    verifier = load_verifier()

    verifier.verify_portfolio_entry_surface()

    assert (
        "proof portfolio entry: static components, bounded imagery, "
        "real Chromium screenshot, and README discovery confirmed"
        in capsys.readouterr().out
    )


def test_high_end_portfolio_screenshot_replaces_the_superseded_capture() -> None:
    screenshot = ROOT / "docs/assets/night-voyager-portfolio-entry.png"
    assert hashlib.sha256(screenshot.read_bytes()).hexdigest() != (
        "195c1a0d5fe1ff9d4c0ac3870b5b871419b7ac8b7f88daab0b5fc3513c756a81"
    )


def test_release_verifier_installed_wheel_loads_exact_skill_manifests() -> None:
    source = (ROOT / "scripts/verify_release.py").read_text(encoding="utf-8")

    for token in (
        "SkillRuntimeRegistry.load_packaged()",
        "SkillEvaluator.load_packaged(registry)",
        "len(registry.entries) == 7",
        "len(evaluator.manifest.datasets) == 7",
    ):
        assert token in source


def copy_planning_start_gate_surface(destination: Path) -> None:
    migrations = destination / "migrations/versions"
    migrations.mkdir(parents=True)
    for source in sorted((ROOT / "migrations/versions").glob("[0-9][0-9][0-9][0-9]_*.py")):
        shutil.copyfile(source, migrations / source.name)
    scripts = destination / "scripts"
    scripts.mkdir()
    shutil.copyfile(ROOT / "scripts/run_db_tests.sh", scripts / "run_db_tests.sh")


def test_release_verifier_accepts_exactly_one_0009_alembic_head(
    capsys: pytest.CaptureFixture[str],
) -> None:
    verifier = load_verifier()

    verifier.verify_alembic_contract()

    assert "proof migrations: exact Alembic head 0009" in capsys.readouterr().out


@pytest.mark.parametrize("mutation", ("remove_0009", "add_second_head"))
def test_release_verifier_rejects_alembic_head_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    verifier = load_verifier()
    copy_planning_start_gate_surface(tmp_path)
    if mutation == "remove_0009":
        (tmp_path / "migrations/versions/0009_explicit_planning_start_authority.py").unlink()
    else:
        (tmp_path / "migrations/versions/0099_test_branch.py").write_text(
            'revision = "0099"\ndown_revision = "0008"\n', encoding="utf-8"
        )
    monkeypatch.setattr(verifier, "ROOT", tmp_path)

    with pytest.raises(SystemExit, match="exactly one Alembic head 0009"):
        verifier.verify_alembic_contract()


@pytest.mark.parametrize(
    "required",
    (
        "inside-planning-start-migration",
        "tests/integration/tasks/test_planning_start_migration.py",
        'run_lane "${BASE_PROJECT_NAME}-planning-start-migration"',
    ),
)
def test_release_verifier_rejects_missing_planning_start_gate_node(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    required: str,
) -> None:
    verifier = load_verifier()
    copy_planning_start_gate_surface(tmp_path)
    script = tmp_path / "scripts/run_db_tests.sh"
    source = script.read_text(encoding="utf-8")
    assert required in source
    script.write_text(source.replace(required, "", 1), encoding="utf-8")
    monkeypatch.setattr(verifier, "ROOT", tmp_path)

    with pytest.raises(SystemExit, match="planning-start migration gate drift"):
        verifier.verify_alembic_contract()
