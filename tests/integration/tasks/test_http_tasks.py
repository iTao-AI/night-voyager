# ruff: noqa: E501
from __future__ import annotations

import os
from uuid import UUID

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from night_voyager.api import create_app
from night_voyager.config import Settings
from night_voyager.identity.models import DemoActorChoice
from night_voyager.identity.repository import IdentityRepository
from night_voyager.identity.service import IdentityService, IssuedSession
from night_voyager.skills.models import SkillKey
from night_voyager.skills.registry import SkillRuntimeRegistry
from tests.integration.dra.test_postgres_mixed_snapshot import approved_pack

pytestmark = pytest.mark.database
ORIGIN = "http://127.0.0.1:3000"
ORG = UUID("10000000-0000-0000-0000-000000000001")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
PARENT = UUID("20000000-0000-0000-0000-000000000003")
CASE = UUID("40000000-0000-0000-0000-000000000220")
UNASSIGNED_CASE = UUID("40000000-0000-0000-0000-000000000221")
INTAKE_CASE = UUID("40000000-0000-0000-0000-000000000222")
PACK = UUID("50000000-0000-0000-0000-000000000001")


def runtime_entry():
    return SkillRuntimeRegistry.load_packaged().get(
        SkillKey.STUDY_DESTINATION_COMPARE, "1.0.0"
    )


async def mint(
    sessions: async_sessionmaker[AsyncSession], choice: DemoActorChoice
) -> IssuedSession:
    async with sessions() as session, session.begin():
        return await IdentityService(IdentityRepository(session), "test-session-secret").mint(
            choice
        )


async def seed_task_cases() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            for case_id in (CASE, UNASSIGNED_CASE, INTAKE_CASE):
                await connection.execute(
                    text(
                        "SELECT app.publish_case_revision(:org,:case,NULL,1,'{}'::jsonb,'{}'::jsonb)"
                    ),
                    {"org": ORG, "case": case_id},
                )
                if case_id != INTAKE_CASE:
                    await connection.execute(
                        text("SELECT app.transition_case(:org,:case,'intake','planning')"),
                        {"org": ORG, "case": case_id},
                    )
            await connection.execute(
                text(
                    "INSERT INTO app.student_case_participants(organization_id,case_id,actor_id,role) "
                    "VALUES(:org,:case,:advisor,'advisor'),(:org,:case,:parent,'parent'),"
                    "(:org,:intake_case,:advisor,'advisor'),(:org,:intake_case,:parent,'parent') "
                    "ON CONFLICT DO NOTHING"
                ),
                {
                    "org": ORG,
                    "case": CASE,
                    "intake_case": INTAKE_CASE,
                    "advisor": ADVISOR,
                    "parent": PARENT,
                },
            )
    finally:
        await engine.dispose()


def create_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "operation": "generate_planning_run_v1",
        "expected_case_revision": 1,
        "source_pack_id": str(PACK),
        "source_pack_version": 1,
        "policy_version": "m3a-policy-v1",
    }
    payload.update(overrides)
    return payload


def mutation_headers(session: IssuedSession, key: str) -> dict[str, str]:
    return {
        "Origin": ORIGIN,
        "X-CSRF-Token": session.raw_csrf_token,
        "Idempotency-Key": key,
    }


@pytest.mark.asyncio
async def test_real_http_task_create_read_cancel_contract() -> None:
    await seed_task_cases()
    url = os.environ["NIGHT_VOYAGER_API_DATABASE_URL"]
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings.model_validate(
        {
            "environment": "test",
            "database_url": url,
            "demo_mode": True,
            "demo_allow_insecure_cookie": True,
            "allowed_origins": [ORIGIN],
            "secret_key": "test-session-secret",
        }
    )
    try:
        advisor = await mint(sessions, DemoActorChoice.ADVISOR)
        parent = await mint(sessions, DemoActorChoice.PARENT)
        app = create_app(settings=settings, session_factory=sessions)
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            rejected_origin = await client.post(
                f"/api/v1/cases/{CASE}/agent-tasks",
                headers={"Origin": "https://evil.invalid", "Idempotency-Key": "origin"},
                json=create_payload(),
            )
            assert rejected_origin.status_code == 403
            assert rejected_origin.headers["content-type"].startswith("application/problem+json")

            client.cookies.set("night_voyager_session", "invalid")
            invalid_session = await client.post(
                f"/api/v1/cases/{CASE}/agent-tasks",
                headers={
                    "Origin": ORIGIN,
                    "X-CSRF-Token": "invalid",
                    "Idempotency-Key": "session",
                },
                json=create_payload(),
            )
            assert invalid_session.status_code == 401

            client.cookies.set("night_voyager_session", parent.raw_session_token)
            role_denied = await client.post(
                f"/api/v1/cases/{CASE}/agent-tasks",
                headers=mutation_headers(parent, "parent-denied"),
                json=create_payload(),
            )
            assert role_denied.status_code == 404

            client.cookies.set("night_voyager_session", advisor.raw_session_token)
            unassigned = await client.post(
                f"/api/v1/cases/{UNASSIGNED_CASE}/agent-tasks",
                headers=mutation_headers(advisor, "unassigned"),
                json=create_payload(),
            )
            assert unassigned.status_code == 404

            extra_field = await client.post(
                f"/api/v1/cases/{CASE}/agent-tasks",
                headers=mutation_headers(advisor, "extra"),
                json=create_payload(organization_id=str(ORG)),
            )
            assert extra_field.status_code == 422

            stale = await client.post(
                f"/api/v1/cases/{CASE}/agent-tasks",
                headers=mutation_headers(advisor, "stale-pins"),
                json=create_payload(expected_case_revision=2),
            )
            assert stale.status_code == 409

            intake_created = await client.post(
                f"/api/v1/cases/{INTAKE_CASE}/agent-tasks",
                headers=mutation_headers(advisor, "intake-create-task"),
                json=create_payload(),
            )
            assert intake_created.status_code == 202, intake_created.text
            assert set(intake_created.json()) == {
                "schema_version",
                "task_id",
                "row_version",
                "status",
                "public_code",
                "attempt_count",
                "planning_run_id",
                "created_at",
                "updated_at",
                "skill_pin",
                "leaf_binding",
                "replayed",
            }
            assert "planning_started" not in intake_created.json()
            intake_cancelled = await client.post(
                f"/api/v1/tasks/{intake_created.json()['task_id']}/cancel",
                headers=mutation_headers(advisor, "intake-cancel-task"),
                json={"schema_version": 1, "expected_row_version": 1},
            )
            assert intake_cancelled.status_code == 200, intake_cancelled.text
            assert intake_cancelled.json()["status"] == "cancelled"

            created = await client.post(
                f"/api/v1/cases/{CASE}/agent-tasks",
                headers=mutation_headers(advisor, "create-task"),
                json=create_payload(),
            )
            assert created.status_code == 202, created.text
            assert created.headers["cache-control"] == "no-store"
            assert created.json()["schema_version"] == 1
            assert created.json()["status"] == "preparing"
            assert created.json()["replayed"] is False
            assert created.json()["skill_pin"] == {
                "skill_definition_id": "81000000-0000-0000-0000-000000000002",
                "skill_version_id": "82000000-0000-0000-0000-000000000002",
                "skill_activation_event_id": "84000000-0000-0000-0000-000000000001",
                "skill_activation_sequence": 1,
                "runtime_binding_sha256": runtime_entry().runtime_binding_sha256,
            }
            assert created.json()["leaf_binding"] == {
                "operation": "generate_planning_run_v1",
                "adapter_id": "deterministic_planning",
                "adapter_version": "m4a-v1",
            }
            task_id = created.json()["task_id"]
            assert set(created.json()) == {
                "schema_version",
                "task_id",
                "row_version",
                "status",
                "public_code",
                "attempt_count",
                "planning_run_id",
                "created_at",
                "updated_at",
                "skill_pin",
                "leaf_binding",
                "replayed",
            }

            replay = await client.post(
                f"/api/v1/cases/{CASE}/agent-tasks",
                headers=mutation_headers(advisor, "create-task"),
                json=create_payload(),
            )
            assert replay.status_code == 202
            assert replay.json()["task_id"] == task_id
            assert replay.json()["replayed"] is True

            mismatch = await client.post(
                f"/api/v1/cases/{CASE}/agent-tasks",
                headers=mutation_headers(advisor, "create-task"),
                json=create_payload(source_pack_version=2),
            )
            assert mismatch.status_code == 409
            assert mismatch.headers["content-type"].startswith(
                "application/problem+json"
            )
            assert mismatch.json()["code"] == "idempotency_conflict"
            assert (
                mismatch.json()["type"]
                == "https://night-voyager.invalid/problems/idempotency_conflict"
            )
            assert "nv008" not in mismatch.text.lower()
            duplicate = await client.post(
                f"/api/v1/cases/{CASE}/agent-tasks",
                headers=mutation_headers(advisor, "duplicate-effective"),
                json=create_payload(),
            )
            assert duplicate.status_code == 409

            current = await client.get(f"/api/v1/tasks/{task_id}")
            assert current.status_code == 200
            assert current.headers["cache-control"] == "no-store"
            assert current.json()["status"] == "preparing"
            assert "state" not in current.json()
            assert "lease_owner" not in current.json()

            client.cookies.set("night_voyager_session", parent.raw_session_token)
            hidden = await client.get(f"/api/v1/tasks/{task_id}")
            assert hidden.status_code == 404
            client.cookies.set("night_voyager_session", advisor.raw_session_token)
            missing = await client.get("/api/v1/tasks/80000000-0000-0000-0000-000000000999")
            assert missing.status_code == 404

            stale_cancel = await client.post(
                f"/api/v1/tasks/{task_id}/cancel",
                headers=mutation_headers(advisor, "cancel-stale"),
                json={"schema_version": 1, "expected_row_version": 9},
            )
            assert stale_cancel.status_code == 409
            cancelled = await client.post(
                f"/api/v1/tasks/{task_id}/cancel",
                headers=mutation_headers(advisor, "cancel-task"),
                json={"schema_version": 1, "expected_row_version": 1},
            )
            assert cancelled.status_code == 200, cancelled.text
            assert cancelled.headers["cache-control"] == "no-store"
            assert cancelled.json()["status"] == "cancelled"
            cancel_replay = await client.post(
                f"/api/v1/tasks/{task_id}/cancel",
                headers=mutation_headers(advisor, "cancel-task"),
                json={"schema_version": 1, "expected_row_version": 1},
            )
            assert cancel_replay.status_code == 200
            assert cancel_replay.json()["replayed"] is True
            after_cancel = await client.get(f"/api/v1/tasks/{task_id}")
            assert after_cancel.json()["status"] == "cancelled"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_real_http_mixed_task_requires_approved_exact_pins_and_replays() -> None:
    case_id, promoted_version = await approved_pack(1220)
    url = os.environ["NIGHT_VOYAGER_API_DATABASE_URL"]
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings.model_validate(
        {
            "environment": "test",
            "database_url": url,
            "demo_mode": True,
            "demo_allow_insecure_cookie": True,
            "allowed_origins": [ORIGIN],
            "secret_key": "test-session-secret",
        }
    )
    try:
        advisor = await mint(sessions, DemoActorChoice.ADVISOR)
        app = create_app(settings=settings, session_factory=sessions)
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            client.cookies.set("night_voyager_session", advisor.raw_session_token)
            unapproved = await client.post(
                f"/api/v1/cases/{case_id}/agent-tasks",
                headers=mutation_headers(advisor, "mixed-unapproved"),
                json=create_payload(
                    operation="generate_governed_mixed_planning_run_v1",
                    source_pack_version=1,
                ),
            )
            assert unapproved.status_code == 409

            payload = create_payload(
                operation="generate_governed_mixed_planning_run_v1",
                source_pack_version=promoted_version,
            )
            created = await client.post(
                f"/api/v1/cases/{case_id}/agent-tasks",
                headers=mutation_headers(advisor, "mixed-create"),
                json=payload,
            )
            assert created.status_code == 202, created.text
            assert created.json()["status"] == "preparing"
            assert created.json()["replayed"] is False
            assert created.json()["leaf_binding"] == {
                "operation": "generate_governed_mixed_planning_run_v1",
                "adapter_id": "governed_mixed_planning",
                "adapter_version": "dra-mixed-v1",
            }

            replayed = await client.post(
                f"/api/v1/cases/{case_id}/agent-tasks",
                headers=mutation_headers(advisor, "mixed-create"),
                json=payload,
            )
            assert replayed.status_code == 202
            assert replayed.json()["task_id"] == created.json()["task_id"]
            assert replayed.json()["replayed"] is True

            conflict = await client.post(
                f"/api/v1/cases/{case_id}/agent-tasks",
                headers=mutation_headers(advisor, "mixed-create"),
                json={**payload, "source_pack_version": promoted_version + 1},
            )
            assert conflict.status_code == 409

            cancelled = await client.post(
                f"/api/v1/tasks/{created.json()['task_id']}/cancel",
                headers=mutation_headers(advisor, "mixed-cancel"),
                json={"schema_version": 1, "expected_row_version": 1},
            )
            assert cancelled.status_code == 200
    finally:
        await engine.dispose()
