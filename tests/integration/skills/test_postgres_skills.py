from __future__ import annotations

import json
import os
from typing import Any, cast
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from night_voyager.identity.demo_seed import (
    COLLABORATION_ACTIVE_CASE_ID,
    COLLABORATION_ACTIVE_TASK_ID,
    SKILL_ACTIVATION_EVENT_ID,
    SKILL_DEFINITION_IDS,
    SKILL_VERSION_IDS,
    build_demo_active_task_pin,
    build_demo_skill_seed,
)
from night_voyager.skills.evaluation import SkillEvaluator
from night_voyager.skills.models import SkillKey
from night_voyager.skills.registry import SkillRuntimeRegistry
from tests.integration.skills.test_skill_lifecycle import (
    registration_command,
    reset_nonseed_skill_history,
)

TABLES = (
    "skill_definitions",
    "skill_versions",
    "skill_change_candidates",
    "skill_evaluation_results",
    "skill_activation_events",
)

MUTATIONS = (
    "create_skill_change_candidate",
    "record_skill_candidate_evaluation",
    "promote_skill_change_candidate",
    "rollback_skill_activation",
)

CATALOG_VERSION_FIELDS = {
    "version_id",
    "semantic_version",
    "binding_kind",
    "input_contract_id",
    "input_schema_sha256",
    "output_contract_id",
    "output_schema_sha256",
    "content_sha256",
    "tool_allowlist_sha256",
    "data_scope_sha256",
    "side_effect_level",
    "approval_policy",
    "policy_version",
    "policy_sha256",
    "evaluation_dataset_id",
    "evaluation_dataset_version",
    "evaluation_dataset_sha256",
    "runtime_manifest_id",
    "runtime_manifest_version",
    "runtime_manifest_sha256",
    "runtime_binding_sha256",
}

INSPECTOR_FIELDS = {
    "case_id",
    "operation",
    "active_skill_key",
    "active_version",
    "activation_sequence",
    "evaluator_id",
    "evaluator_version",
    "evaluation_dataset_id",
    "evaluation_dataset_version",
    "task_request_sha256_prefix",
    "version_content_sha256_prefix",
    "runtime_binding_sha256_prefix",
    "adapter_id",
    "adapter_version",
    "pin_status",
}

SECOND_ORG = UUID("19000000-0000-0000-0000-000000000001")
SECOND_OWNER = UUID("29000000-0000-0000-0000-000000000001")
SECOND_MEMBERSHIP = UUID("39000000-0000-0000-0000-000000000001")
NON_OWNER = UUID("29000000-0000-0000-0000-000000000002")
NON_OWNER_MEMBERSHIP = UUID("39000000-0000-0000-0000-000000000002")


@pytest.mark.database
@pytest.mark.asyncio
async def test_exact_skill_catalog_is_migrator_owned_forced_rls() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                        "SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity,"
                        "pg_get_userbyid(c.relowner) AS owner "
                        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                        "WHERE n.nspname='app' AND c.relname=ANY(:tables) "
                        "ORDER BY c.relname"
                    ),
                    {"tables": list(TABLES)},
                )
            ).mappings().all()
        assert tuple(row["relname"] for row in rows) == tuple(sorted(TABLES))
        assert all(row["relrowsecurity"] and row["relforcerowsecurity"] for row in rows)
        assert all(row["owner"] == "night_voyager_migrator" for row in rows)
    finally:
        await engine.dispose()


@pytest.mark.database
@pytest.mark.asyncio
async def test_fresh_head_seed_creates_exact_pinned_active_task_fixture() -> None:
    if os.environ.get("NIGHT_VOYAGER_SKILL_SEED_PATH") != "fresh_head":
        pytest.skip("fresh-head seed regression runs in the lifecycle main project")
    registry = SkillRuntimeRegistry.load_packaged()
    expected_binding = registry.get(
        SkillKey.STUDY_DESTINATION_COMPARE, "1.0.0"
    ).runtime_binding_sha256
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": "10000000-0000-0000-0000-000000000001"},
            )
            task = (
                (
                    await connection.execute(
                        text(
                            "SELECT state,skill_definition_id,skill_version_id,"
                            "skill_activation_event_id,skill_activation_sequence,"
                            "runtime_binding_sha256 FROM app.agent_tasks "
                            "WHERE organization_id=:org AND id=:task"
                        ),
                        {
                            "org": "10000000-0000-0000-0000-000000000001",
                            "task": COLLABORATION_ACTIVE_TASK_ID,
                        },
                    )
                )
                .mappings()
                .one()
            )
            assert dict(task) == {
                "state": "waiting_review",
                "skill_definition_id": SKILL_DEFINITION_IDS[
                    SkillKey.STUDY_DESTINATION_COMPARE
                ],
                "skill_version_id": SKILL_VERSION_IDS[
                    SkillKey.STUDY_DESTINATION_COMPARE
                ],
                "skill_activation_event_id": SKILL_ACTIVATION_EVENT_ID,
                "skill_activation_sequence": 1,
                "runtime_binding_sha256": expected_binding,
            }
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.agent_task_events "
                        "WHERE organization_id=:org AND task_id=:task "
                        "AND event_sequence=1 AND event_code='waiting_review' "
                        "AND public_code='review_required'"
                    ),
                    {
                        "org": "10000000-0000-0000-0000-000000000001",
                        "task": COLLABORATION_ACTIVE_TASK_ID,
                    },
                )
                == 1
            )
    finally:
        await engine.dispose()


@pytest.mark.database
@pytest.mark.asyncio
async def test_pinned_active_task_seed_mismatch_has_no_partial_task_or_event() -> None:
    if os.environ.get("NIGHT_VOYAGER_SKILL_SEED_PATH") != "fresh_head":
        pytest.skip("fresh-head seed regression runs in the lifecycle main project")
    registry = SkillRuntimeRegistry.load_packaged()
    pin = build_demo_active_task_pin(registry)
    pin["runtime_binding_sha256"] = "f" * 64
    mismatched_task_id = UUID("48000000-0000-0000-0000-000000000099")
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": "10000000-0000-0000-0000-000000000001"},
            )
            savepoint = await connection.begin_nested()
            with pytest.raises(DBAPIError):
                await connection.execute(
                    text(
                        "SELECT app.seed_demo_pinned_collaboration_task("
                        ":org,:case,:task,:advisor,CAST(:pin AS jsonb))"
                    ),
                    {
                        "org": "10000000-0000-0000-0000-000000000001",
                        "case": COLLABORATION_ACTIVE_CASE_ID,
                        "task": mismatched_task_id,
                        "advisor": "20000000-0000-0000-0000-000000000001",
                        "pin": json.dumps(pin),
                    },
                )
            await savepoint.rollback()
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.agent_tasks "
                        "WHERE organization_id=:org AND id=:task"
                    ),
                    {
                        "org": "10000000-0000-0000-0000-000000000001",
                        "task": mismatched_task_id,
                    },
                )
                == 0
            )
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.agent_task_events "
                        "WHERE organization_id=:org AND task_id=:task"
                    ),
                    {
                        "org": "10000000-0000-0000-0000-000000000001",
                        "task": mismatched_task_id,
                    },
                )
                == 0
            )
            await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.mark.database
@pytest.mark.asyncio
async def test_runtime_roles_have_no_direct_skill_table_dml_or_truncate() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                        "SELECT table_name,grantee,privilege_type "
                        "FROM information_schema.role_table_grants "
                        "WHERE table_schema='app' AND table_name=ANY(:tables) "
                        "AND grantee=ANY(:roles)"
                    ),
                    {
                        "tables": list(TABLES),
                        "roles": ["night_voyager_api", "night_voyager_worker", "PUBLIC"],
                    },
                )
            ).mappings().all()
        assert rows == []
    finally:
        await engine.dispose()


@pytest.mark.database
@pytest.mark.asyncio
async def test_canonical_seed_has_exact_catalog_versions_evaluations_and_activation() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": "10000000-0000-0000-0000-000000000001"},
            )
            row = (
                await connection.execute(
                    text(
                        "SELECT "
                        "(SELECT count(*) FROM app.skill_definitions) AS definitions,"
                        "(SELECT count(*) FROM app.skill_versions) AS versions,"
                        "(SELECT count(*) FROM app.skill_evaluation_results) AS evaluations,"
                        "(SELECT count(*) FROM app.skill_activation_events) AS activations,"
                        "(SELECT array_agg(skill_key ORDER BY skill_key) "
                        "FROM app.skill_definitions) AS skill_keys,"
                        "(SELECT array_agg(semantic_version ORDER BY skill_key) "
                        "FROM app.skill_versions) AS semantic_versions"
                    )
                )
            ).mappings().one()
            activation = (
                await connection.execute(
                    text(
                        "SELECT d.skill_key,v.semantic_version,e.event_kind,"
                        "e.activation_sequence "
                        "FROM app.skill_activation_events e "
                        "JOIN app.skill_definitions d "
                        "ON d.organization_id=e.organization_id "
                        "AND d.id=e.definition_id "
                        "JOIN app.skill_versions v "
                        "ON v.organization_id=e.organization_id "
                        "AND v.id=e.activated_version_id"
                    )
                )
            ).one()
        assert dict(row) == {
            "definitions": 6,
            "versions": 6,
            "evaluations": 6,
            "activations": 1,
            "skill_keys": [
                "application-timeline-guard",
                "document-evidence-retrieval",
                "evidence-research",
                "family-decision-brief",
                "student-profile-intake",
                "study-destination-compare",
            ],
            "semantic_versions": ["1.0.0"] * 6,
        }
        assert activation == (
            "study-destination-compare",
            "1.0.0",
            "seed",
            1,
        )
    finally:
        await engine.dispose()


@pytest.mark.database
@pytest.mark.asyncio
async def test_catalog_detail_and_inspector_return_exact_public_safe_shapes() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            for setting, value in (
                ("night_voyager.organization_id", "10000000-0000-0000-0000-000000000001"),
                ("night_voyager.actor_id", "20000000-0000-0000-0000-000000000001"),
                ("night_voyager.role", "advisor"),
            ):
                await connection.execute(
                    text("SELECT set_config(:setting,:value,true)"),
                    {"setting": setting, "value": value},
                )
            detail = cast(
                dict[str, Any],
                await connection.scalar(
                    text("SELECT app.get_skill_catalog_item(:org,:actor,:skill_key)"),
                    {
                        "org": "10000000-0000-0000-0000-000000000001",
                        "actor": "20000000-0000-0000-0000-000000000001",
                        "skill_key": "study-destination-compare",
                    },
                ),
            )
            not_created = cast(
                dict[str, Any],
                await connection.scalar(
                    text("SELECT app.inspect_planning_skill(:org,:actor,:case)"),
                    {
                        "org": "10000000-0000-0000-0000-000000000001",
                        "actor": "20000000-0000-0000-0000-000000000001",
                        "case": "40000000-0000-0000-0000-000000000002",
                    },
                ),
            )
            legacy = cast(
                dict[str, Any],
                await connection.scalar(
                    text("SELECT app.inspect_planning_skill(:org,:actor,:case)"),
                    {
                        "org": "10000000-0000-0000-0000-000000000001",
                        "actor": "20000000-0000-0000-0000-000000000001",
                        "case": "41000000-0000-0000-0000-000000000002",
                    },
                ),
            )
        assert set(detail) == {
            "skill_key",
            "definition_id",
            "owner_actor_id",
            "binding_kind",
            "versions",
            "activation_events",
        }
        assert len(cast(list[object], detail["versions"])) == 1
        assert set(cast(list[dict[str, Any]], detail["versions"])[0]) == (
            CATALOG_VERSION_FIELDS
        )
        active_status = (
            "matched"
            if os.environ.get("NIGHT_VOYAGER_SKILL_SEED_PATH") == "fresh_head"
            else "legacy_unpinned"
        )
        for projection, status in (
            (not_created, "not_created"),
            (legacy, active_status),
        ):
            assert set(projection) == INSPECTOR_FIELDS
            assert projection["pin_status"] == status
            assert len(cast(str, projection["version_content_sha256_prefix"])) == 12
            assert len(cast(str, projection["runtime_binding_sha256_prefix"])) == 12
            assert "skill_definition_id" not in projection
            assert "runtime_binding_sha256" not in projection
        assert not_created["operation"] is None
        assert not_created["task_request_sha256_prefix"] is None
        assert legacy["operation"] == "generate_planning_run_v1"
        assert len(cast(str, legacy["task_request_sha256_prefix"])) == 12
    finally:
        await engine.dispose()


@pytest.mark.database
@pytest.mark.asyncio
async def test_canonical_seed_replays_exactly_and_rejects_tampered_projections() -> None:
    registry = SkillRuntimeRegistry.load_packaged()
    evaluator = SkillEvaluator.load_packaged(registry)
    canonical = build_demo_skill_seed(registry, evaluator)
    tampered_projections: list[dict[str, Any]] = []
    for mutation in ("partial", "failed_evaluation", "definition_id", "eval_manifest"):
        projection = cast(
            dict[str, Any],
            json.loads(json.dumps(canonical)),
        )
        entries = cast(list[dict[str, Any]], projection["entries"])
        if mutation == "partial":
            projection["entries"] = entries[:-1]
        elif mutation == "failed_evaluation":
            cast(dict[str, Any], entries[0]["evaluation"])["status"] = "failed"
        elif mutation == "definition_id":
            entries[0]["definition_id"] = "81000000-0000-0000-0000-000000000099"
        else:
            projection["evaluation_manifest_sha256"] = "f" * 64
        tampered_projections.append(projection)

    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": "10000000-0000-0000-0000-000000000001"},
            )
            statement = text(
                "SELECT app.seed_demo_skill_registry("
                ":org,:owner,CAST(:seed AS jsonb))"
            )
            parameters = {
                "org": "10000000-0000-0000-0000-000000000001",
                "owner": "20000000-0000-0000-0000-000000000001",
                "seed": json.dumps(canonical),
            }
            await connection.execute(statement, parameters)
            for projection in tampered_projections:
                savepoint = await connection.begin_nested()
                try:
                    with pytest.raises(DBAPIError) as captured:
                        await connection.execute(
                            statement,
                            {
                                **parameters,
                                "seed": json.dumps(projection),
                            },
                        )
                    assert getattr(captured.value.orig, "sqlstate", None) == "NV006"
                finally:
                    if savepoint.is_active:
                        await savepoint.rollback()
    finally:
        await engine.dispose()


@pytest.mark.database
@pytest.mark.asyncio
async def test_skill_tables_have_exact_tenant_policy_and_immutable_trigger() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            policies = (
                await connection.execute(
                    text(
                        "SELECT tablename,policyname FROM pg_policies "
                        "WHERE schemaname='app' AND tablename=ANY(:tables) "
                        "ORDER BY tablename,policyname"
                    ),
                    {"tables": list(TABLES)},
                )
            ).all()
            triggers = (
                await connection.execute(
                    text(
                        "SELECT c.relname,t.tgname FROM pg_trigger t "
                        "JOIN pg_class c ON c.oid=t.tgrelid "
                        "JOIN pg_namespace n ON n.oid=c.relnamespace "
                        "WHERE n.nspname='app' AND c.relname=ANY(:tables) "
                        "AND NOT t.tgisinternal ORDER BY c.relname,t.tgname"
                    ),
                    {"tables": list(TABLES)},
                )
            ).all()
        assert policies == [
            (table, f"{table}_tenant_isolation") for table in sorted(TABLES)
        ]
        assert triggers == [
            (table, f"{table}_immutable") for table in sorted(TABLES)
        ]
    finally:
        await engine.dispose()


@pytest.mark.database
@pytest.mark.asyncio
async def test_skill_mutations_are_api_only_and_seed_is_migrator_only() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                            "SELECT p.proname,"
                            "has_function_privilege('night_voyager_api',p.oid,'EXECUTE') AS api,"
                            "has_function_privilege("
                            "'night_voyager_worker',p.oid,'EXECUTE') AS worker,"
                            "EXISTS (SELECT 1 FROM aclexplode("
                            "COALESCE(p.proacl,acldefault('f',p.proowner))) acl "
                            "WHERE acl.grantee=0 AND acl.privilege_type='EXECUTE') AS public "
                        "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                        "WHERE n.nspname='app' AND p.proname=ANY(:names) ORDER BY p.proname"
                    ),
                    {"names": [*MUTATIONS, "seed_demo_skill_registry"]},
                )
            ).mappings().all()
        assert tuple(row["proname"] for row in rows) == tuple(
            sorted((*MUTATIONS, "seed_demo_skill_registry"))
        )
        for row in rows:
            if row["proname"] == "seed_demo_skill_registry":
                assert row["api"] is False
                assert row["worker"] is False
                assert row["public"] is False
            else:
                assert row["api"] is True
                assert row["worker"] is False
                assert row["public"] is False
    finally:
        await engine.dispose()


@pytest.mark.database
@pytest.mark.asyncio
async def test_task_and_execution_pin_constraints_are_relational() -> None:
    required = {
        "agent_tasks_skill_pin_all_or_none",
        "agent_tasks_skill_version_fk",
        "agent_tasks_skill_activation_fk",
        "agent_tasks_skill_pin_identity_unique",
        "agent_executions_skill_pin_all_or_none",
        "agent_executions_task_skill_pin_fk",
    }
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            constraints = set(
                (
                    await connection.execute(
                        text(
                            "SELECT conname FROM pg_constraint "
                            "WHERE conrelid IN "
                            "('app.agent_tasks'::regclass,'app.agent_executions'::regclass)"
                        )
                    )
                ).scalars()
            )
            index_definition = await connection.scalar(
                text(
                    "SELECT pg_get_indexdef(indexrelid) FROM pg_index "
                    "WHERE indexrelid='app.agent_tasks_one_effective_operation'::regclass"
                )
            )
        assert required <= constraints
        assert isinstance(index_definition, str)
        for field in (
            "skill_definition_id",
            "skill_version_id",
            "skill_activation_event_id",
            "skill_activation_sequence",
            "runtime_binding_sha256",
        ):
            assert field in index_definition
    finally:
        await engine.dispose()


@pytest.mark.database
@pytest.mark.asyncio
async def test_candidate_evaluation_and_activation_identity_is_relational() -> None:
    required = {
        "skill_change_candidates_identity_version_unique",
        "skill_evaluation_results_candidate_version_fk",
        "skill_evaluation_results_identity_version_unique",
        "skill_evaluation_results_identity_candidate_unique",
        "skill_activation_events_candidate_version_fk",
        "skill_activation_events_evaluation_version_fk",
        "skill_activation_events_evaluation_candidate_fk",
    }
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            constraints = set(
                (
                    await connection.execute(
                        text(
                            "SELECT conname FROM pg_constraint WHERE conrelid IN ("
                            "'app.skill_change_candidates'::regclass,"
                            "'app.skill_evaluation_results'::regclass,"
                            "'app.skill_activation_events'::regclass)"
                        )
                    )
                ).scalars()
            )
        assert required <= constraints
    finally:
        await engine.dispose()


@pytest.mark.database
@pytest.mark.asyncio
async def test_catalog_only_version_cannot_satisfy_activation_foreign_key_path() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": "10000000-0000-0000-0000-000000000001"},
            )
            selected = (
                await connection.execute(
                    text(
                        "SELECT d.id AS definition_id,v.id AS version_id,e.id AS evaluation_id,"
                        "d.owner_actor_id "
                        "FROM app.skill_definitions d "
                        "JOIN app.skill_versions v "
                        "ON v.organization_id=d.organization_id "
                        "AND v.definition_id=d.id "
                        "JOIN app.skill_evaluation_results e "
                        "ON e.organization_id=v.organization_id "
                        "AND e.version_id=v.id "
                        "WHERE d.organization_id=:org "
                        "AND d.skill_key='student-profile-intake'"
                    ),
                    {"org": "10000000-0000-0000-0000-000000000001"},
                )
            ).mappings().one()
            savepoint = await connection.begin_nested()
            try:
                with pytest.raises(DBAPIError) as captured:
                    await connection.execute(
                        text(
                            "INSERT INTO app.skill_activation_events("
                            "organization_id,id,definition_id,activated_version_id,"
                            "evaluation_id,event_kind,owner_actor_id,reason,"
                            "request_sha256,activation_sequence) VALUES("
                            ":org,'89000000-0000-0000-0000-000000000001',"
                            ":definition,:version,:evaluation,'seed',:owner,"
                            "'invalid catalog activation',repeat('a',64),1)"
                        ),
                        {
                            "org": "10000000-0000-0000-0000-000000000001",
                            "definition": selected["definition_id"],
                            "version": selected["version_id"],
                            "evaluation": selected["evaluation_id"],
                            "owner": selected["owner_actor_id"],
                        },
                    )
                assert getattr(captured.value.orig, "sqlstate", None) == "23503"
            finally:
                if savepoint.is_active:
                    await savepoint.rollback()
    finally:
        await engine.dispose()


@pytest.mark.database
@pytest.mark.asyncio
async def test_designated_owner_is_enforced_for_registered_version_candidates() -> None:
    await reset_nonseed_skill_history()
    registered = registration_command(
        "--skill-key",
        "study-destination-compare",
        "--version",
        "1.0.1",
    )
    assert registered.returncode == 0, registered.stderr
    registry = SkillRuntimeRegistry.load_packaged()
    manifest = registry.get(SkillKey.STUDY_DESTINATION_COMPARE, "1.0.1").model_dump(
        mode="json", exclude_none=True
    )

    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    try:
        async with migrator.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": "10000000-0000-0000-0000-000000000001"},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.actors("
                    "id,organization_id,display_name,is_synthetic) "
                    "VALUES(:actor,:org,'Synthetic non-owner advisor',true) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {
                    "actor": NON_OWNER,
                    "org": "10000000-0000-0000-0000-000000000001",
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO app.memberships("
                    "id,organization_id,actor_id,role) "
                    "VALUES(:membership,:org,:actor,'advisor') "
                    "ON CONFLICT (organization_id,actor_id,role) DO NOTHING"
                ),
                {
                    "membership": NON_OWNER_MEMBERSHIP,
                    "org": "10000000-0000-0000-0000-000000000001",
                    "actor": NON_OWNER,
                },
            )

        async with api.connect() as connection:
            transaction = await connection.begin()
            try:
                for setting, value in (
                    (
                        "night_voyager.organization_id",
                        "10000000-0000-0000-0000-000000000001",
                    ),
                    ("night_voyager.actor_id", str(NON_OWNER)),
                    ("night_voyager.role", "advisor"),
                ):
                    await connection.execute(
                        text("SELECT set_config(:setting,:value,true)"),
                        {"setting": setting, "value": value},
                    )
                with pytest.raises(DBAPIError) as captured:
                    await connection.execute(
                        text(
                            "SELECT * FROM app.create_skill_change_candidate("
                            ":org,:actor,'study-destination-compare',"
                            "'89000000-0000-0000-0000-000000000020',"
                            "'1.0.1','maintainer_proposal','wrong owner',NULL,"
                            "CAST(:manifest AS jsonb),repeat('a',64),repeat('b',64))"
                        ),
                        {
                            "org": "10000000-0000-0000-0000-000000000001",
                            "actor": NON_OWNER,
                            "manifest": json.dumps(manifest),
                        },
                    )
                assert getattr(captured.value.orig, "sqlstate", None) == "NV007"
            finally:
                await transaction.rollback()
    finally:
        await api.dispose()
        await migrator.dispose()
        await reset_nonseed_skill_history()


@pytest.mark.database
@pytest.mark.asyncio
async def test_dual_tenant_catalog_isolation_and_size_one_pool_context_cleanup() -> None:
    registry = SkillRuntimeRegistry.load_packaged()
    evaluator = SkillEvaluator.load_packaged(registry)
    canonical = build_demo_skill_seed(registry, evaluator)
    migrator = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    api = create_async_engine(
        os.environ["NIGHT_VOYAGER_API_DATABASE_URL"],
        pool_size=1,
        max_overflow=0,
    )
    try:
        async with migrator.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(SECOND_ORG)},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.organizations(id,name,is_synthetic) "
                    "VALUES(:org,'Second synthetic Skill tenant',true) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {"org": SECOND_ORG},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.actors("
                    "id,organization_id,display_name,is_synthetic) "
                    "VALUES(:actor,:org,'Second synthetic owner',true) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {"actor": SECOND_OWNER, "org": SECOND_ORG},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.memberships("
                    "id,organization_id,actor_id,role) "
                    "VALUES(:membership,:org,:actor,'advisor') "
                    "ON CONFLICT (organization_id,actor_id,role) DO NOTHING"
                ),
                {
                    "membership": SECOND_MEMBERSHIP,
                    "org": SECOND_ORG,
                    "actor": SECOND_OWNER,
                },
            )
            await connection.execute(
                text("SELECT app.seed_demo_skill_registry(:org,:owner,CAST(:seed AS jsonb))"),
                {
                    "org": SECOND_ORG,
                    "owner": SECOND_OWNER,
                    "seed": json.dumps(canonical),
                },
            )
            counts: list[int] = []
            for organization_id in (
                UUID("10000000-0000-0000-0000-000000000001"),
                SECOND_ORG,
            ):
                await connection.execute(
                    text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                    {"org": str(organization_id)},
                )
                count = await connection.scalar(text("SELECT count(*) FROM app.skill_definitions"))
                assert isinstance(count, int)
                counts.append(count)
            assert counts == [6, 6]

        async with api.begin() as connection:
            assert (
                await connection.scalar(
                    text("SELECT NULLIF(current_setting('night_voyager.organization_id',true),'')")
                )
                is None
            )
            for setting, value in (
                ("night_voyager.organization_id", str(SECOND_ORG)),
                ("night_voyager.actor_id", str(SECOND_OWNER)),
                ("night_voyager.role", "advisor"),
            ):
                await connection.execute(
                    text("SELECT set_config(:setting,:value,true)"),
                    {"setting": setting, "value": value},
                )
            projection = cast(
                list[object],
                await connection.scalar(
                    text("SELECT app.list_skill_catalog(:org,:actor)"),
                    {"org": SECOND_ORG, "actor": SECOND_OWNER},
                ),
            )
            assert len(projection) == 6

        async with api.connect() as connection:
            transaction = await connection.begin()
            try:
                assert (
                    await connection.scalar(
                        text(
                            "SELECT NULLIF(current_setting("
                            "'night_voyager.organization_id',true),'')"
                        )
                    )
                    is None
                )
                for setting, value in (
                    (
                        "night_voyager.organization_id",
                        "10000000-0000-0000-0000-000000000001",
                    ),
                    (
                        "night_voyager.actor_id",
                        "20000000-0000-0000-0000-000000000001",
                    ),
                    ("night_voyager.role", "advisor"),
                ):
                    await connection.execute(
                        text("SELECT set_config(:setting,:value,true)"),
                        {"setting": setting, "value": value},
                    )
                with pytest.raises(DBAPIError) as captured:
                    await connection.execute(
                        text("SELECT app.list_skill_catalog(:org,:actor)"),
                        {"org": SECOND_ORG, "actor": SECOND_OWNER},
                    )
                assert getattr(captured.value.orig, "sqlstate", None) == "NV007"
            finally:
                await transaction.rollback()
    finally:
        await api.dispose()
        await migrator.dispose()
