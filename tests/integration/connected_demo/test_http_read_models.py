from __future__ import annotations

import json
import os
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from night_voyager.api import create_app
from night_voyager.config import Settings
from night_voyager.identity.demo_seed import CONNECTED_DEMO_CASE_ID
from night_voyager.identity.models import DemoActorChoice
from night_voyager.identity.repository import IdentityRepository
from night_voyager.identity.service import IdentityService
from night_voyager.planning.fixtures import validate_planning_fixture

pytestmark = pytest.mark.database
DEMO_ORG = UUID("10000000-0000-0000-0000-000000000001")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
STUDENT = UUID("20000000-0000-0000-0000-000000000002")
PARENT = UUID("20000000-0000-0000-0000-000000000003")
PLANNING_FIXTURE = validate_planning_fixture().planning_input


async def seed_pending_revision_case() -> UUID:
    case_id = uuid4()
    run_id = uuid4()
    review_id = uuid4()
    thread_id = uuid4()
    message_id = uuid4()
    candidate_id = uuid4()
    engine = create_async_engine(
        os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"]
    )
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "SELECT set_config("
                    "'night_voyager.organization_id',:org,true)"
                ),
                {"org": str(DEMO_ORG)},
            )
            source = (
                await connection.execute(
                    text(
                        "SELECT student_preferences,family_preferences "
                        "FROM app.student_case_revisions "
                        "WHERE organization_id=:org ORDER BY created_at LIMIT 1"
                    ),
                    {"org": DEMO_ORG},
                )
            ).mappings().one()
            await connection.execute(
                text(
                    "SELECT app.publish_case_revision("
                    ":org,:case,NULL,1,CAST(:student AS jsonb),"
                    "CAST(:family AS jsonb))"
                ),
                {
                    "org": DEMO_ORG,
                    "case": case_id,
                    "student": json.dumps(source["student_preferences"]),
                    "family": json.dumps(source["family_preferences"]),
                },
            )
            await connection.execute(
                text(
                    "SELECT app.seed_case_participants("
                    ":org,:case,:advisor,:student,:parent)"
                ),
                {
                    "org": DEMO_ORG,
                    "case": case_id,
                    "advisor": ADVISOR,
                    "student": STUDENT,
                    "parent": PARENT,
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO app.planning_runs("
                    "organization_id,id,case_id,case_revision,source_pack_id,"
                    "source_pack_version,policy_version,evidence_projection_sha256,"
                    "state,reason_code,output_sha256,is_current) VALUES("
                    ":org,:run,:case,1,"
                    "'50000000-0000-0000-0000-000000000001',1,"
                    "'m3a-policy-v1',repeat('a',64),'review_required',"
                    "'synthetic_pending_phase',repeat('b',64),true)"
                ),
                {"org": DEMO_ORG, "run": run_id, "case": case_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.advisor_reviews("
                    "organization_id,id,case_id,case_revision,planning_run_id,"
                    "review_version,advisor_actor_id,action,eligible_route_ids,"
                    "risk_acceptances,reviewer_notes) VALUES("
                    ":org,:review,:case,1,:run,1,:advisor,'request_revision',"
                    "'[]'::jsonb,'[]'::jsonb,'Synthetic bounded revision request.')"
                ),
                {
                    "org": DEMO_ORG,
                    "review": review_id,
                    "case": case_id,
                    "run": run_id,
                    "advisor": ADVISOR,
                },
            )
            await connection.execute(
                text(
                    "UPDATE app.student_cases SET state='planning' "
                    "WHERE organization_id=:org AND id=:case"
                ),
                {"org": DEMO_ORG, "case": case_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.collaboration_threads("
                    "organization_id,id,case_id,created_by_actor_id,created_by_role)"
                    " VALUES(:org,:thread,:case,:advisor,'advisor')"
                ),
                {
                    "org": DEMO_ORG,
                    "thread": thread_id,
                    "case": case_id,
                    "advisor": ADVISOR,
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO app.message_events("
                    "organization_id,id,thread_id,case_id,sequence_no,actor_id,"
                    "actor_role,body,content_sha256,request_sha256) VALUES("
                    ":org,:message,:thread,:case,1,:parent,'parent',"
                    "'Synthetic bounded budget proposal.',repeat('c',64),"
                    "repeat('d',64))"
                ),
                {
                    "org": DEMO_ORG,
                    "message": message_id,
                    "thread": thread_id,
                    "case": case_id,
                    "parent": PARENT,
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO app.memory_candidates("
                    "organization_id,id,case_id,case_revision,message_event_id,"
                    "subject_actor_id,subject_role,proposing_actor_id,"
                    "proposing_role,fact_key,proposed_value,value_sha256,"
                    "request_sha256,created_at,expires_at) VALUES("
                    ":org,:candidate,:case,1,:message,:parent,'parent',"
                    ":parent,'parent','family.budget','{}'::jsonb,"
                    "repeat('e',64),repeat('f',64),statement_timestamp(),"
                    "statement_timestamp()+interval '7 days')"
                ),
                {
                    "org": DEMO_ORG,
                    "candidate": candidate_id,
                    "case": case_id,
                    "message": message_id,
                    "parent": PARENT,
                },
            )
    finally:
        await engine.dispose()
    return case_id


async def seed_terminal_task_case() -> UUID:
    case_id = uuid4()
    task_id = uuid4()
    engine = create_async_engine(
        os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"]
    )
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "SELECT set_config("
                    "'night_voyager.organization_id',:org,true)"
                ),
                {"org": str(DEMO_ORG)},
            )
            await connection.execute(
                text(
                    "SELECT app.publish_case_revision("
                    ":org,:case,NULL,1,CAST(:student AS jsonb),CAST(:family AS jsonb))"
                ),
                {
                    "org": DEMO_ORG,
                    "case": case_id,
                    "student": PLANNING_FIXTURE.case.student.model_dump_json(),
                    "family": PLANNING_FIXTURE.case.family.model_dump_json(),
                },
            )
            await connection.execute(
                text(
                    "SELECT app.seed_case_participants("
                    ":org,:case,:advisor,:student,:parent)"
                ),
                {
                    "org": DEMO_ORG,
                    "case": case_id,
                    "advisor": ADVISOR,
                    "student": STUDENT,
                    "parent": PARENT,
                },
            )
            await connection.execute(
                text("SELECT app.transition_case(:org,:case,'intake','planning')"),
                {"org": DEMO_ORG, "case": case_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.agent_tasks("
                    "organization_id,id,case_id,operation,case_revision,"
                    "source_pack_id,source_pack_version,policy_version,"
                    "request_sha256,created_by_actor_id,state,terminal_code) VALUES("
                    ":org,:task,:case,'generate_planning_run_v1',1,"
                    "'50000000-0000-0000-0000-000000000001',1,'m3a-policy-v1',"
                    "repeat('a',64),:advisor,'timed_out','deadline_exceeded')"
                ),
                {
                    "org": DEMO_ORG,
                    "task": task_id,
                    "case": case_id,
                    "advisor": ADVISOR,
                },
            )
    finally:
        await engine.dispose()
    return case_id


def test_connected_demo_read_routes_are_registered() -> None:
    app = create_app()
    paths = app.openapi()["paths"]
    assert "get" in paths["/api/v1/cases/{case_id}/advisor-ledger"]
    assert "get" in paths["/api/v1/cases/{case_id}/current-decision-brief"]
    assert "get" in paths["/api/v1/cases/{case_id}/journey-status"]


@pytest.mark.parametrize(
    "path",
    (
        f"/api/v1/cases/{CONNECTED_DEMO_CASE_ID}/advisor-ledger?contract_version=",
        f"/api/v1/cases/{CONNECTED_DEMO_CASE_ID}/advisor-ledger?contract_version=3",
        f"/api/v1/cases/{CONNECTED_DEMO_CASE_ID}/advisor-ledger?"
        "contract_version=2&contract_version=2",
        f"/api/v1/cases/{CONNECTED_DEMO_CASE_ID}/current-decision-brief?"
        "contract_version=unknown",
    ),
)
def test_connected_demo_contract_negotiation_fails_closed(path: str) -> None:
    response = TestClient(create_app()).get(path)
    assert response.status_code == 422
    assert response.json()["code"] == "request_validation_failed"

def test_connected_demo_invalid_uuid_is_redacted_problem() -> None:
    response = TestClient(create_app()).get("/api/v1/cases/not-a-uuid/advisor-ledger")
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["code"] == "request_validation_failed"


@pytest.mark.asyncio
async def test_invalid_read_session_expires_both_identity_cookies() -> None:
    url = os.environ["NIGHT_VOYAGER_API_DATABASE_URL"]
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings.model_validate(
        {
            "environment": "test",
            "database_url": url,
            "demo_mode": True,
            "demo_allow_insecure_cookie": True,
            "allowed_origins": ["http://127.0.0.1:3000"],
            "secret_key": "test-session-secret",
        }
    )
    try:
        app = create_app(settings=settings, session_factory=sessions)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://127.0.0.1:3000"
        ) as client:
            client.cookies.set("night_voyager_session", "invalid")
            client.cookies.set("night_voyager_csrf_bootstrap", "stale")
            response = await client.get(
                f"/api/v1/cases/{CONNECTED_DEMO_CASE_ID}/advisor-ledger"
            )
        assert response.status_code == 401
        cookies = response.headers.get_list("set-cookie")
        assert len(cookies) == 2
        assert any("night_voyager_session=" in value and "Max-Age=0" in value for value in cookies)
        assert any(
            "night_voyager_csrf_bootstrap=" in value and "Max-Age=0" in value
            for value in cookies
        )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_task_ready_http_projection_is_real_and_no_store() -> None:
    url = os.environ["NIGHT_VOYAGER_API_DATABASE_URL"]
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings.model_validate(
        {
            "environment": "test",
            "database_url": url,
            "demo_mode": True,
            "demo_allow_insecure_cookie": True,
            "allowed_origins": ["http://127.0.0.1:3000"],
            "secret_key": "test-session-secret",
        }
    )
    try:
        async with sessions() as session, session.begin():
            issued = await IdentityService(
                IdentityRepository(session), settings.secret_key
            ).mint(DemoActorChoice.ADVISOR)
        app = create_app(settings=settings, session_factory=sessions)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://127.0.0.1:3000"
        ) as client:
            client.cookies.set("night_voyager_session", issued.raw_session_token)
            response = await client.get(
                f"/api/v1/cases/{CONNECTED_DEMO_CASE_ID}/advisor-ledger"
            )
            response_v2 = await client.get(
                f"/api/v1/cases/{CONNECTED_DEMO_CASE_ID}/advisor-ledger"
                "?contract_version=2"
            )
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["phase"] == "task-ready"
        assert response.json()["task"] is None
        assert response_v2.status_code == 200, response_v2.text
        assert response_v2.json()["schema_version"] == 2
        assert response_v2.json()["phase"] == "task_ready"
        assert "comparison" in response_v2.json()
    finally:
        await engine.dispose()


@pytest.mark.parametrize(
    "choice",
    (
        DemoActorChoice.ADVISOR,
        DemoActorChoice.STUDENT,
        DemoActorChoice.PARENT,
    ),
)
@pytest.mark.asyncio
async def test_journey_status_is_exact_and_participant_safe(
    choice: DemoActorChoice,
) -> None:
    url = os.environ["NIGHT_VOYAGER_API_DATABASE_URL"]
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings.model_validate(
        {
            "environment": "test",
            "database_url": url,
            "demo_mode": True,
            "demo_allow_insecure_cookie": True,
            "allowed_origins": ["http://127.0.0.1:3000"],
            "secret_key": "test-session-secret",
        }
    )
    try:
        async with sessions() as session, session.begin():
            issued = await IdentityService(
                IdentityRepository(session), settings.secret_key
            ).mint(choice)
        app = create_app(settings=settings, session_factory=sessions)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://127.0.0.1:3000"
        ) as client:
            client.cookies.set("night_voyager_session", issued.raw_session_token)
            response = await client.get(
                f"/api/v1/cases/{CONNECTED_DEMO_CASE_ID}/journey-status"
            )
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == {
            "schema": "night-voyager.connected-journey-status.v1",
            "case_id": str(CONNECTED_DEMO_CASE_ID),
            "current_revision": 1,
            "phase": "task_ready",
            "active_role": "advisor",
        }
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_pending_revision_http_phase_is_role_equal_and_identifier_free() -> None:
    case_id = await seed_pending_revision_case()
    url = os.environ["NIGHT_VOYAGER_API_DATABASE_URL"]
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings.model_validate(
        {
            "environment": "test",
            "database_url": url,
            "demo_mode": True,
            "demo_allow_insecure_cookie": True,
            "allowed_origins": ["http://127.0.0.1:3000"],
            "secret_key": "test-session-secret",
        }
    )
    expected_keys = {
        "schema",
        "case_id",
        "current_revision",
        "phase",
        "active_role",
    }
    try:
        app = create_app(settings=settings, session_factory=sessions)
        for choice in (
            DemoActorChoice.ADVISOR,
            DemoActorChoice.STUDENT,
            DemoActorChoice.PARENT,
        ):
            async with sessions() as session, session.begin():
                issued = await IdentityService(
                    IdentityRepository(session), settings.secret_key
                ).mint(choice)
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://127.0.0.1:3000",
            ) as client:
                client.cookies.set(
                    "night_voyager_session", issued.raw_session_token
                )
                response = await client.get(
                    f"/api/v1/cases/{case_id}/journey-status"
                )
                hidden = await client.get(
                    f"/api/v1/cases/{uuid4()}/journey-status"
                )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.keys() == expected_keys
            assert payload == {
                "schema": "night-voyager.connected-journey-status.v1",
                "case_id": str(case_id),
                "current_revision": 1,
                "phase": "revision_fact_pending",
                "active_role": "advisor",
            }
            assert hidden.status_code == 404
            assert hidden.json()["code"] == "resource_unavailable"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_terminal_task_http_phase_is_role_equal_after_reload() -> None:
    case_id = await seed_terminal_task_case()
    url = os.environ["NIGHT_VOYAGER_API_DATABASE_URL"]
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings.model_validate(
        {
            "environment": "test",
            "database_url": url,
            "demo_mode": True,
            "demo_allow_insecure_cookie": True,
            "allowed_origins": ["http://127.0.0.1:3000"],
            "secret_key": "test-session-secret",
        }
    )
    try:
        app = create_app(settings=settings, session_factory=sessions)
        for choice in (
            DemoActorChoice.ADVISOR,
            DemoActorChoice.STUDENT,
            DemoActorChoice.PARENT,
        ):
            async with sessions() as session, session.begin():
                issued = await IdentityService(
                    IdentityRepository(session), settings.secret_key
                ).mint(choice)
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://127.0.0.1:3000",
            ) as client:
                client.cookies.set(
                    "night_voyager_session", issued.raw_session_token
                )
                response = await client.get(
                    f"/api/v1/cases/{case_id}/journey-status"
                )
            assert response.status_code == 200
            assert response.json()["phase"] == "terminal_task_failure"
            assert response.json()["active_role"] == "advisor"
    finally:
        await engine.dispose()
