# ruff: noqa: E501
from __future__ import annotations

import argparse
import asyncio
import json
import os
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

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
    CONNECTED_DEMO_CASE_ID,
    build_demo_active_task_pin,
    build_demo_skill_seed,
    ensure_seed_allowed,
)
from night_voyager.planning.application import POLICY_VERSION
from night_voyager.planning.fixtures import ValidatedPlanningFixture, validate_planning_fixture
from night_voyager.skills.evaluation import SkillEvaluator
from night_voyager.skills.registry import SkillRuntimeRegistry

DEMO_ORG = UUID("10000000-0000-0000-0000-000000000001")
CASE_ID = UUID("40000000-0000-0000-0000-000000000001")
RUN_ID = UUID("70000000-0000-0000-0000-000000000001")
ACTORS = (
    ("advisor", "20000000-0000-0000-0000-000000000001", "Demo Advisor"),
    ("student", "20000000-0000-0000-0000-000000000002", "Demo Student"),
    ("parent", "20000000-0000-0000-0000-000000000003", "Demo Parent"),
)


async def seed_demo(
    database_url: str,
    *,
    include_planning: bool = True,
    include_collaboration: bool = True,
    include_skills: bool = True,
) -> None:
    fixture = validate_planning_fixture()
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id', :value, true)"),
                {"value": str(DEMO_ORG)},
            )
            await _seed_identity(connection)
            if include_planning:
                active_task_pin: dict[str, object] | None = None
                if include_skills:
                    _, active_task_pin = await _seed_skills(connection)
                await _seed_planning(connection, fixture)
                await connection.execute(
                    text("SELECT app.seed_case_participants(:org,:case,:advisor,:student,:parent)"),
                    {
                        "org": DEMO_ORG,
                        "case": CASE_ID,
                        "advisor": ACTORS[0][1],
                        "student": ACTORS[1][1],
                        "parent": ACTORS[2][1],
                    },
                )
                await _seed_task_case(connection, fixture)
                if include_collaboration:
                    await _seed_collaboration(
                        connection,
                        fixture,
                        active_task_pin=active_task_pin,
                    )
    finally:
        await engine.dispose()
    print("demo seed: canonical synthetic identity and planning snapshot ready")


async def _seed_skills(
    connection: AsyncConnection,
) -> tuple[dict[str, object], dict[str, object]]:
    registry = SkillRuntimeRegistry.load_packaged()
    evaluator = SkillEvaluator.load_packaged(registry)
    projection = build_demo_skill_seed(registry, evaluator)
    await connection.execute(
        text(
            "SELECT app.seed_demo_skill_registry("
            ":org,:owner,CAST(:projection AS jsonb))"
        ),
        {
            "org": DEMO_ORG,
            "owner": ACTORS[0][1],
            "projection": json.dumps(projection),
        },
    )
    return projection, build_demo_active_task_pin(registry)


async def _seed_identity(connection: AsyncConnection) -> None:
    await connection.execute(
        text(
            "INSERT INTO app.organizations (id,name,is_synthetic) VALUES (:id,'Night Voyager synthetic demo',true) ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name"
        ),
        {"id": DEMO_ORG},
    )
    for index, (role, actor_id, display_name) in enumerate(ACTORS, start=1):
        await connection.execute(
            text(
                "INSERT INTO app.actors (id,organization_id,display_name,is_synthetic) VALUES (:id,:org,:name,true) ON CONFLICT (id) DO UPDATE SET display_name=EXCLUDED.display_name"
            ),
            {"id": actor_id, "org": DEMO_ORG, "name": display_name},
        )
        await connection.execute(
            text(
                "INSERT INTO app.memberships (id,organization_id,actor_id,role) VALUES (:id,:org,:actor,:role) ON CONFLICT (organization_id,actor_id,role) DO NOTHING"
            ),
            {
                "id": f"30000000-0000-0000-0000-{index:012d}",
                "org": DEMO_ORG,
                "actor": actor_id,
                "role": role,
            },
        )
        await connection.execute(
            text(
                "INSERT INTO auth.demo_principals (demo_key,organization_id,actor_id,role) VALUES (:role,:org,:actor,:role) ON CONFLICT (demo_key) DO UPDATE SET organization_id=EXCLUDED.organization_id,actor_id=EXCLUDED.actor_id,role=EXCLUDED.role"
            ),
            {"org": DEMO_ORG, "actor": actor_id, "role": role},
        )


async def _seed_planning(connection: AsyncConnection, fixture: ValidatedPlanningFixture) -> None:
    planning_input = fixture.planning_input
    case = planning_input.case
    await connection.execute(
        text(
            "INSERT INTO app.student_cases (organization_id,id,state) VALUES (:org,:case,'planning') ON CONFLICT DO NOTHING"
        ),
        {"org": case.organization_id, "case": case.case_id},
    )
    await connection.execute(
        text(
            "INSERT INTO app.student_case_revisions (organization_id,case_id,revision,schema_version,student_preferences,family_preferences) VALUES (:org,:case,:revision,1,CAST(:student AS jsonb),CAST(:family AS jsonb)) ON CONFLICT DO NOTHING"
        ),
        {
            "org": case.organization_id,
            "case": case.case_id,
            "revision": case.revision,
            "student": json.dumps(case.student.model_dump(mode="json")),
            "family": json.dumps(case.family.model_dump(mode="json")),
        },
    )
    await connection.execute(
        text(
            "UPDATE app.student_cases SET current_revision=:revision "
            "WHERE organization_id=:org AND id=:case AND current_revision IS NULL"
        ),
        {"org": case.organization_id, "case": case.case_id, "revision": case.revision},
    )
    pack = planning_input.source_pack
    await connection.execute(
        text(
            "INSERT INTO app.source_packs (organization_id,id,version,schema_version,manifest_sha256) VALUES (:org,:pack,:version,1,:hash) ON CONFLICT DO NOTHING"
        ),
        {
            "org": pack.organization_id,
            "pack": pack.pack_id,
            "version": pack.version,
            "hash": fixture.manifest_sha256,
        },
    )
    for entry in pack.entries:
        await connection.execute(
            text(
                "INSERT INTO app.source_pack_entries (organization_id,source_pack_id,source_pack_version,id,declared_path,sha256,snapshot_date,publisher,institution,canonical_url,freshness_days,redistribution_class,evidence_class,coverage,known_gaps) VALUES (:org,:pack,:version,:id,:path,:hash,:snapshot,:publisher,:institution,:url,:freshness,:redistribution,:class,CAST(:coverage AS jsonb),CAST(:gaps AS jsonb)) ON CONFLICT DO NOTHING"
            ),
            {
                "org": pack.organization_id,
                "pack": pack.pack_id,
                "version": pack.version,
                "id": entry.entry_id,
                "path": entry.path,
                "hash": entry.sha256,
                "snapshot": entry.snapshot_date,
                "publisher": entry.publisher,
                "institution": entry.institution,
                "url": str(entry.canonical_url),
                "freshness": entry.freshness_days,
                "redistribution": entry.redistribution_class,
                "class": entry.evidence_class,
                "coverage": json.dumps(entry.coverage),
                "gaps": json.dumps(entry.known_gaps),
            },
        )
    for evidence in planning_input.evidence:
        await connection.execute(
            text(
                "INSERT INTO app.evidence_refs (organization_id,id,source_pack_id,source_pack_version,source_entry_id,claim,authority,source_sha256) VALUES (:org,:id,:pack,:version,:entry,:claim,:authority,:hash) ON CONFLICT DO NOTHING"
            ),
            {
                "org": evidence.organization_id,
                "id": evidence.evidence_id,
                "pack": evidence.source_pack_id,
                "version": evidence.source_pack_version,
                "entry": evidence.source_entry_id,
                "claim": evidence.claim,
                "authority": evidence.authority,
                "hash": evidence.source_sha256,
            },
        )
    exists = await connection.scalar(
        text(
            "SELECT EXISTS(SELECT 1 FROM app.planning_runs WHERE organization_id=:org AND id=:run)"
        ),
        {"org": planning_input.organization_id, "run": RUN_ID},
    )
    if exists:
        return
    await connection.execute(
        text(
            "INSERT INTO app.planning_runs (organization_id,id,case_id,case_revision,source_pack_id,source_pack_version,policy_version,evidence_projection_sha256,state,reason_code,output_sha256,is_current) VALUES (:org,:run,:case,:revision,:pack,:version,:policy,:evidence_hash,'synthesizing',NULL,NULL,true)"
        ),
        {
            "org": planning_input.organization_id,
            "run": RUN_ID,
            "case": case.case_id,
            "revision": case.revision,
            "pack": pack.pack_id,
            "version": pack.version,
            "policy": POLICY_VERSION,
            "evidence_hash": fixture.evidence_projection_sha256,
        },
    )
    dimension_index = 0
    for index, route in enumerate(fixture.result.routes, start=1):
        route_id = UUID(f"71000000-0000-0000-0000-{index:012d}")
        await connection.execute(
            text(
                "INSERT INTO app.planning_routes VALUES (:org,:run,:id,:country,:outcome,:reason)"
            ),
            {
                "org": planning_input.organization_id,
                "run": RUN_ID,
                "id": route_id,
                "country": route.country,
                "outcome": route.outcome,
                "reason": route.reason_code,
            },
        )
        for dimension in route.dimensions:
            dimension_index += 1
            dimension_id = UUID(f"72000000-0000-0000-0000-{dimension_index:012d}")
            await connection.execute(
                text(
                    "INSERT INTO app.comparison_dimensions VALUES (:org,:run,:route,:id,:key,:outcome,:reason)"
                ),
                {
                    "org": planning_input.organization_id,
                    "run": RUN_ID,
                    "route": route_id,
                    "id": dimension_id,
                    "key": dimension.dimension_key,
                    "outcome": dimension.outcome,
                    "reason": dimension.reason_code,
                },
            )
            for use in dimension.evidence_uses:
                await connection.execute(
                    text(
                        "INSERT INTO app.comparison_dimension_evidence_refs VALUES (:org,:run,:route,:dimension,:evidence,:role)"
                    ),
                    {
                        "org": planning_input.organization_id,
                        "run": RUN_ID,
                        "route": route_id,
                        "dimension": dimension_id,
                        "evidence": use.evidence_id,
                        "role": use.role,
                    },
                )
    for index, cost in enumerate(planning_input.costs, start=1):
        await connection.execute(
            text(
                "INSERT INTO app.cost_evidence VALUES (:org,:run,:id,:country,:intake,:period,:currency,:tuition,:living,:fx,:source,:date,:tuition_evidence,:living_evidence,:fx_evidence)"
            ),
            {
                "org": cost.organization_id,
                "run": RUN_ID,
                "id": UUID(f"73000000-0000-0000-0000-{index:012d}"),
                "country": cost.country,
                "intake": cost.intake,
                "period": cost.period,
                "currency": cost.currency,
                "tuition": cost.tuition_minor,
                "living": cost.living_minor,
                "fx": cost.fx_rate,
                "source": cost.fx_source,
                "date": cost.fx_date,
                "tuition_evidence": cost.tuition_evidence_id,
                "living_evidence": cost.living_evidence_id,
                "fx_evidence": cost.fx_evidence_id,
            },
        )
    for index, ranking in enumerate(planning_input.rankings, start=1):
        await connection.execute(
            text(
                "INSERT INTO app.ranking_evidence VALUES (:org,:run,:id,:country,:system,:rank,:year,:evidence)"
            ),
            {
                "org": ranking.organization_id,
                "run": RUN_ID,
                "id": UUID(f"74000000-0000-0000-0000-{index:012d}"),
                "country": ranking.country,
                "system": ranking.ranking_system,
                "rank": ranking.rank,
                "year": ranking.publication_year,
                "evidence": ranking.evidence_id,
            },
        )
    await connection.execute(
        text(
            "UPDATE app.planning_runs SET state=:state,reason_code=:reason,output_sha256=:hash WHERE organization_id=:org AND id=:run"
        ),
        {
            "state": fixture.result.state,
            "reason": fixture.result.reason_code,
            "hash": fixture.output_sha256,
            "org": planning_input.organization_id,
            "run": RUN_ID,
        },
    )


async def _seed_task_case(connection: AsyncConnection, fixture: ValidatedPlanningFixture) -> None:
    source_case = fixture.planning_input.case
    await connection.execute(
        text(
            "INSERT INTO app.student_cases (organization_id,id,state) "
            "VALUES (:org,:case,'planning') ON CONFLICT DO NOTHING"
        ),
        {"org": DEMO_ORG, "case": CONNECTED_DEMO_CASE_ID},
    )
    await connection.execute(
        text(
            "INSERT INTO app.student_case_revisions "
            "(organization_id,case_id,revision,schema_version,student_preferences,family_preferences) "
            "VALUES (:org,:case,1,1,CAST(:student AS jsonb),CAST(:family AS jsonb)) "
            "ON CONFLICT DO NOTHING"
        ),
        {
            "org": DEMO_ORG,
            "case": CONNECTED_DEMO_CASE_ID,
            "student": json.dumps(source_case.student.model_dump(mode="json")),
            "family": json.dumps(source_case.family.model_dump(mode="json")),
        },
    )
    await connection.execute(
        text(
            "UPDATE app.student_cases SET current_revision=1 "
            "WHERE organization_id=:org AND id=:case AND current_revision IS NULL"
        ),
        {"org": DEMO_ORG, "case": CONNECTED_DEMO_CASE_ID},
    )
    await connection.execute(
        text("SELECT app.seed_case_participants(:org,:case,:advisor,:student,:parent)"),
        {
            "org": DEMO_ORG,
            "case": CONNECTED_DEMO_CASE_ID,
            "advisor": ACTORS[0][1],
            "student": ACTORS[1][1],
            "parent": ACTORS[2][1],
        },
    )


async def _seed_collaboration(
    connection: AsyncConnection,
    fixture: ValidatedPlanningFixture,
    *,
    active_task_pin: object | None,
) -> None:
    source_case = fixture.planning_input.case
    default_before = (
        (
            await connection.execute(
                text(
                    "SELECT selected_case.state,selected_case.current_revision,"
                    "revision.student_preferences,revision.family_preferences "
                    "FROM app.student_cases selected_case "
                    "JOIN app.student_case_revisions revision "
                    "ON revision.organization_id=selected_case.organization_id "
                    "AND revision.case_id=selected_case.id "
                    "AND revision.revision=selected_case.current_revision "
                    "WHERE selected_case.organization_id=:org AND selected_case.id=:case"
                ),
                {"org": DEMO_ORG, "case": CASE_ID},
            )
        )
        .mappings()
        .one()
    )
    case_specs = (
        (COLLABORATION_CASE_ID, "intake"),
        (COLLABORATION_ACTIVE_CASE_ID, "planning"),
        (COLLABORATION_STALE_CASE_ID, "intake"),
        (COLLABORATION_EXPIRED_CASE_ID, "intake"),
    )
    for case_id, state in case_specs:
        await connection.execute(
            text(
                "INSERT INTO app.student_cases(organization_id,id,state) "
                "VALUES(:org,:case,:state) ON CONFLICT DO NOTHING"
            ),
            {"org": DEMO_ORG, "case": case_id, "state": state},
        )
        await connection.execute(
            text(
                "INSERT INTO app.student_case_revisions("
                "organization_id,case_id,revision,schema_version,"
                "student_preferences,family_preferences) "
                "VALUES(:org,:case,1,1,CAST(:student AS jsonb),CAST(:family AS jsonb)) "
                "ON CONFLICT DO NOTHING"
            ),
            {
                "org": DEMO_ORG,
                "case": case_id,
                "student": json.dumps(source_case.student.model_dump(mode="json")),
                "family": json.dumps(source_case.family.model_dump(mode="json")),
            },
        )
        await connection.execute(
            text(
                "UPDATE app.student_cases SET current_revision=1 "
                "WHERE organization_id=:org AND id=:case AND current_revision IS NULL"
            ),
            {"org": DEMO_ORG, "case": case_id},
        )
        selected_case = (
            (
                await connection.execute(
                    text(
                        "SELECT state,current_revision FROM app.student_cases "
                        "WHERE organization_id=:org AND id=:case"
                    ),
                    {"org": DEMO_ORG, "case": case_id},
                )
            )
            .mappings()
            .one()
        )
        expected_revision = 2 if case_id == COLLABORATION_STALE_CASE_ID else 1
        if selected_case["state"] != state or selected_case["current_revision"] not in {
            1,
            expected_revision,
        }:
            raise RuntimeError("demo collaboration Case seed mismatch")
        await connection.execute(
            text("SELECT app.seed_case_participants(:org,:case,:advisor,:student,:parent)"),
            {
                "org": DEMO_ORG,
                "case": case_id,
                "advisor": ACTORS[0][1],
                "student": ACTORS[1][1],
                "parent": ACTORS[2][1],
            },
        )

    skill_catalog_exists = await connection.scalar(
        text("SELECT to_regclass('app.skill_definitions') IS NOT NULL")
    )
    legacy_active_task_exists = await connection.scalar(
        text(
            "SELECT EXISTS(SELECT 1 FROM app.agent_tasks "
            "WHERE organization_id=:org AND id=:task)"
        ),
        {"org": DEMO_ORG, "task": COLLABORATION_ACTIVE_TASK_ID},
    )

    seed_specs = (
        (
            COLLABORATION_CASE_ID,
            COLLABORATION_THREAD_IDS["primary"],
            None,
            None,
            None,
            None,
            "primary",
        ),
        (
            COLLABORATION_ACTIVE_CASE_ID,
            COLLABORATION_THREAD_IDS["active_task"],
            None,
            None,
            None,
            COLLABORATION_ACTIVE_TASK_ID,
            "active_task",
        ),
        (
            COLLABORATION_STALE_CASE_ID,
            COLLABORATION_THREAD_IDS["stale"],
            ACTORS[2][1],
            COLLABORATION_STALE_MESSAGE_ID,
            COLLABORATION_STALE_CANDIDATE_ID,
            None,
            "stale",
        ),
        (
            COLLABORATION_EXPIRED_CASE_ID,
            COLLABORATION_THREAD_IDS["expired"],
            ACTORS[2][1],
            COLLABORATION_EXPIRED_MESSAGE_ID,
            COLLABORATION_EXPIRED_CANDIDATE_ID,
            None,
            "expired",
        ),
    )
    for case_id, thread_id, subject_id, message_id, candidate_id, task_id, kind in seed_specs:
        seed_pinned_task = False
        if kind == "active_task" and skill_catalog_exists:
            if legacy_active_task_exists:
                continue
            task_id = None
            kind = "primary"
            seed_pinned_task = active_task_pin is not None
        await connection.execute(
            text(
                "SELECT app.seed_demo_collaboration("
                ":org,:case,:thread,:advisor,:subject,:message,:candidate,:task,:kind)"
            ),
            {
                "org": DEMO_ORG,
                "case": case_id,
                "thread": thread_id,
                "advisor": ACTORS[0][1],
                "subject": subject_id,
                "message": message_id,
                "candidate": candidate_id,
                "task": task_id,
                "kind": kind,
            },
        )
        if seed_pinned_task:
            await _seed_pinned_collaboration_task(
                connection,
                case_id=case_id,
                task_id=COLLABORATION_ACTIVE_TASK_ID,
                active_task_pin=active_task_pin,
            )

    stale_revision = await connection.scalar(
        text(
            "SELECT current_revision FROM app.student_cases WHERE organization_id=:org AND id=:case"
        ),
        {"org": DEMO_ORG, "case": COLLABORATION_STALE_CASE_ID},
    )
    if stale_revision == 1:
        await connection.execute(
            text(
                "SELECT app.publish_case_revision("
                ":org,:case,1,2,CAST(:student AS jsonb),CAST(:family AS jsonb))"
            ),
            {
                "org": DEMO_ORG,
                "case": COLLABORATION_STALE_CASE_ID,
                "student": json.dumps(source_case.student.model_dump(mode="json")),
                "family": json.dumps(source_case.family.model_dump(mode="json")),
            },
        )
    elif stale_revision != 2:
        raise RuntimeError("demo collaboration stale Case seed mismatch")

    default_after = (
        (
            await connection.execute(
                text(
                    "SELECT selected_case.state,selected_case.current_revision,"
                    "revision.student_preferences,revision.family_preferences "
                    "FROM app.student_cases selected_case "
                    "JOIN app.student_case_revisions revision "
                    "ON revision.organization_id=selected_case.organization_id "
                    "AND revision.case_id=selected_case.id "
                    "AND revision.revision=selected_case.current_revision "
                    "WHERE selected_case.organization_id=:org AND selected_case.id=:case"
                ),
                {"org": DEMO_ORG, "case": CASE_ID},
            )
        )
        .mappings()
        .one()
    )
    if dict(default_after) != dict(default_before):
        raise RuntimeError("demo collaboration seed changed the default Case")


async def _seed_pinned_collaboration_task(
    connection: AsyncConnection,
    *,
    case_id: UUID,
    task_id: UUID,
    active_task_pin: object,
) -> None:
    await connection.execute(
        text(
            "SELECT app.seed_demo_pinned_collaboration_task("
            ":org,:case,:task,:advisor,CAST(:pin AS jsonb))"
        ),
        {
            "org": DEMO_ORG,
            "case": case_id,
            "task": task_id,
            "advisor": ACTORS[0][1],
            "pin": json.dumps(active_task_pin),
        },
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--identity-only", action="store_true")
    parser.add_argument("--without-collaboration", action="store_true")
    parser.add_argument("--without-skills", action="store_true")
    arguments = parser.parse_args(argv)
    fixture = validate_planning_fixture()
    if arguments.validate_only:
        print(f"planning fixture valid: {fixture.snapshot()}")
        return
    ensure_seed_allowed(
        os.environ.get("NIGHT_VOYAGER_ENVIRONMENT", "development"),
        os.environ.get("NIGHT_VOYAGER_DEMO_MODE", "false").lower() == "true",
    )
    database_url = os.environ.get("NIGHT_VOYAGER_MIGRATION_DATABASE_URL")
    if not database_url:
        raise SystemExit("NIGHT_VOYAGER_MIGRATION_DATABASE_URL is required")
    asyncio.run(
        seed_demo(
            database_url,
            include_planning=not arguments.identity_only,
            include_collaboration=not arguments.without_collaboration,
            include_skills=not arguments.without_skills,
        )
    )


if __name__ == "__main__":
    main()
