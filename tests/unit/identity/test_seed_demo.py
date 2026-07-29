from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

from night_voyager.identity.demo_seed import (
    COLLABORATION_ACTIVE_CASE_ID,
    COLLABORATION_ACTIVE_TASK_ID,
    COLLABORATION_CASE_ID,
    COLLABORATION_EXPIRED_CANDIDATE_ID,
    COLLABORATION_EXPIRED_CASE_ID,
    COLLABORATION_EXPIRED_MESSAGE_ID,
    COLLABORATION_STALE_CANDIDATE_ID,
    COLLABORATION_STALE_CASE_ID,
    COLLABORATION_STALE_MESSAGE_ID,
    COLLABORATION_THREAD_IDS,
    SKILL_ACTIVATION_EVENT_ID,
    SKILL_DEFINITION_IDS,
    SKILL_EVALUATION_IDS,
    SKILL_VERSION_IDS,
    build_demo_active_task_pin,
    build_demo_skill_seed,
    ensure_seed_allowed,
)
from night_voyager.skills.evaluation import SkillEvaluator
from night_voyager.skills.models import SkillKey
from night_voyager.skills.registry import SkillRuntimeRegistry

ROOT = Path(__file__).resolve().parents[3]


def _load_seed_script() -> ModuleType:
    path = ROOT / "scripts/seed_demo.py"
    spec = importlib.util.spec_from_file_location("night_voyager_seed_demo", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_demo_seed_fails_closed_without_nonproduction_demo_mode() -> None:
    with pytest.raises(ValueError, match="development or test"):
        ensure_seed_allowed("production", True)
    with pytest.raises(ValueError, match="demo mode"):
        ensure_seed_allowed("test", False)

    ensure_seed_allowed("development", True)
    ensure_seed_allowed("test", True)


def test_collaboration_seed_ids_are_fixed_and_cases_are_isolated() -> None:
    assert COLLABORATION_CASE_ID.hex == "41000000000000000000000000000001"
    assert COLLABORATION_ACTIVE_CASE_ID.hex == "41000000000000000000000000000002"
    assert COLLABORATION_STALE_CASE_ID.hex == "41000000000000000000000000000003"
    assert COLLABORATION_EXPIRED_CASE_ID.hex == "41000000000000000000000000000004"
    assert len(set(COLLABORATION_THREAD_IDS.values())) == 4
    assert COLLABORATION_STALE_MESSAGE_ID != COLLABORATION_EXPIRED_MESSAGE_ID
    assert COLLABORATION_STALE_CANDIDATE_ID != COLLABORATION_EXPIRED_CANDIDATE_ID
    assert COLLABORATION_ACTIVE_TASK_ID.hex == "48000000000000000000000000000002"


def test_skill_seed_is_exact_deterministic_and_excludes_compatibility_version() -> None:
    registry = SkillRuntimeRegistry.from_json(
        (ROOT / "fixtures/skills/runtime-manifest-v1.json").read_bytes()
    )
    evaluator = SkillEvaluator.from_json(
        (ROOT / "fixtures/skills/eval-manifest-v1.json").read_bytes(), registry
    )

    first = build_demo_skill_seed(registry, evaluator)
    second = build_demo_skill_seed(registry, evaluator)

    assert first == second
    assert first["runtime_manifest_id"] == "night-voyager.skill-runtime-manifest"
    assert first["runtime_manifest_version"] == "1.0.0"
    assert first["runtime_manifest_sha256"] == registry.manifest.manifest_sha256
    entries_value = first["entries"]
    assert isinstance(entries_value, list)
    entries = cast(list[dict[str, Any]], entries_value)
    assert len(entries) == 6
    identities = {
        (entry["manifest"]["skill_key"], entry["manifest"]["version"])
        for entry in entries
    }
    assert identities == {
        (key.value, "1.0.0") for key in SKILL_DEFINITION_IDS
    }
    assert all(entry["is_seed"] is True for entry in entries)
    assert all(entry["evaluation"]["status"] == "passed" for entry in entries)
    assert all(
        "activation_event_id" not in entry
        for entry in entries
        if entry["manifest"]["skill_key"] != "study-destination-compare"
    )
    planning = next(
        entry
        for entry in entries
        if entry["manifest"]["skill_key"] == "study-destination-compare"
    )
    assert planning["activation_event_id"] == str(SKILL_ACTIVATION_EVENT_ID)
    assert {entry["definition_id"] for entry in entries} == {
        str(value) for value in SKILL_DEFINITION_IDS.values()
    }
    assert {entry["version_id"] for entry in entries} == {
        str(value) for value in SKILL_VERSION_IDS.values()
    }
    assert {entry["evaluation_id"] for entry in entries} == {
        str(value) for value in SKILL_EVALUATION_IDS.values()
    }
    planning_pin = build_demo_active_task_pin(registry)
    planning_manifest = cast(dict[str, Any], planning["manifest"])
    assert planning_pin == {
        "skill_definition_id": str(
            SKILL_DEFINITION_IDS[SkillKey.STUDY_DESTINATION_COMPARE]
        ),
        "skill_version_id": str(
            SKILL_VERSION_IDS[SkillKey.STUDY_DESTINATION_COMPARE]
        ),
        "skill_activation_event_id": str(SKILL_ACTIVATION_EVENT_ID),
        "skill_activation_sequence": 1,
        "runtime_binding_sha256": planning_manifest["runtime_binding_sha256"],
    }


def test_head_seed_preserves_legacy_task_and_creates_a_pinned_fresh_head_fixture() -> None:
    source = (ROOT / "scripts/seed_demo.py").read_text(encoding="utf-8")
    assert "active_task_pin" in source
    assert "SELECT app.seed_demo_pinned_collaboration_task(" in source
    assert "await _classify_active_task_pin(connection)" in source
    assert 'active_task_pin_state == "legacy_unpinned"' in source
    assert "await _assert_exact_legacy_active_task(connection)" in source
    assert "partial Skill runtime pin" in source
    assert "await _seed_pinned_collaboration_task(" in source
    assert 'parser.add_argument("--without-skills", action="store_true")' in source


def test_planning_revision_snapshot_replay_is_create_once_and_exact() -> None:
    source = (ROOT / "scripts/seed_demo.py").read_text(encoding="utf-8")
    fixture_seed = source.split(
        "async def _seed_planning_revision_cases(", 1
    )[1].split("\n\nasync def _clone_planning_snapshot(", 1)[0]
    clone = source.split("async def _clone_planning_snapshot(", 1)[1].split(
        "\n\nasync def _seed_collaboration(", 1
    )[0]

    assert "ON CONFLICT DO NOTHING RETURNING id" in fixture_seed
    assert "await _assert_exact_planning_revision_fixture(" in fixture_seed
    assert fixture_seed.index("if inserted_case_id is None:") < fixture_seed.index(
        "SELECT app.seed_case_participants("
    )
    assert fixture_seed.index("continue") < fixture_seed.index(
        "SELECT app.seed_case_participants("
    )
    assert "ON CONFLICT DO NOTHING RETURNING id" in clone
    assert "await _assert_exact_planning_snapshot(" in clone
    assert "demo planning revision snapshot seed mismatch" in source
    assert "demo planning revision fixture seed mismatch" in source
    assert clone.index("if inserted_run_id is None:") < clone.index(
        "for table, columns, projection in clone_specs:"
    )


@pytest.mark.asyncio
async def test_plan_execution_seed_requires_explicit_historical_opt_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_script = _load_seed_script()

    class Connection:
        async def execute(self, *_args: object, **_kwargs: object) -> None:
            return None

    class Transaction:
        async def __aenter__(self) -> Connection:
            return Connection()

        async def __aexit__(self, *_args: object) -> None:
            return None

    class Engine:
        def begin(self) -> Transaction:
            return Transaction()

        async def dispose(self) -> None:
            return None

    async def no_op(*_args: object, **_kwargs: object) -> None:
        return None

    plan_execution_calls = 0

    async def record_plan_execution(*_args: object, **_kwargs: object) -> None:
        nonlocal plan_execution_calls
        plan_execution_calls += 1

    def create_engine(_url: str) -> Engine:
        return Engine()

    monkeypatch.setattr(seed_script, "create_async_engine", create_engine)
    monkeypatch.setattr(seed_script, "validate_planning_fixture", object)
    monkeypatch.setattr(seed_script, "_seed_identity", no_op)
    monkeypatch.setattr(seed_script, "_seed_planning", no_op)
    monkeypatch.setattr(seed_script, "_seed_task_case", no_op)
    monkeypatch.setattr(
        seed_script,
        "_seed_plan_execution_scenario",
        record_plan_execution,
    )

    common = {
        "include_collaboration": False,
        "include_planning_revision": False,
        "include_skills": False,
    }
    await seed_script.seed_demo(
        "postgresql+asyncpg://unused",
        include_plan_execution=False,
        **common,
    )
    assert plan_execution_calls == 0

    await seed_script.seed_demo("postgresql+asyncpg://unused", **common)
    assert plan_execution_calls == 1


def test_plan_execution_cli_defaults_strict_and_forwards_explicit_opt_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_script = _load_seed_script()
    forwarded: list[bool] = []

    async def record_seed(
        _database_url: str,
        *,
        include_planning: bool = True,
        include_collaboration: bool = True,
        include_planning_revision: bool = True,
        include_skills: bool = True,
        include_plan_execution: bool = True,
    ) -> None:
        assert include_planning is True
        assert include_collaboration is True
        assert include_planning_revision is True
        assert include_skills is True
        forwarded.append(include_plan_execution)

    monkeypatch.setattr(seed_script, "seed_demo", record_seed)
    monkeypatch.setenv("NIGHT_VOYAGER_ENVIRONMENT", "test")
    monkeypatch.setenv("NIGHT_VOYAGER_DEMO_MODE", "true")
    monkeypatch.setenv(
        "NIGHT_VOYAGER_MIGRATION_DATABASE_URL",
        "postgresql+asyncpg://unused",
    )

    seed_script.main([])
    seed_script.main(["--without-plan-execution"])

    assert forwarded == [True, False]
