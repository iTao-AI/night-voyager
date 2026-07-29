from __future__ import annotations

import os
from typing import Any
from uuid import UUID

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from night_voyager.api import create_app
from night_voyager.config import Settings
from night_voyager.database import create_engine, create_session_factory
from night_voyager.identity.demo_seed import (
    BLOCKED_PLAN_EXECUTION_CASE_ID,
    PLAN_EXECUTION_CASE_ID,
    PLAN_EXECUTION_TIMELINE_ID,
)
from night_voyager.identity.models import DemoActorChoice
from night_voyager.identity.repository import IdentityRepository
from night_voyager.identity.service import IdentityService, IssuedSession
from night_voyager.interfaces.http.identity import SESSION_COOKIE

pytestmark = pytest.mark.database
ORIGIN = "http://127.0.0.1:3000"


async def mint(
    sessions: async_sessionmaker[AsyncSession], choice: DemoActorChoice
) -> IssuedSession:
    async with sessions() as session, session.begin():
        return await IdentityService(
            IdentityRepository(session), "test-session-secret"
        ).mint(choice)


@pytest.mark.asyncio
async def test_http_contract_closes_scenario_authentication_and_body_shape() -> None:
    engine = create_engine(os.environ["NIGHT_VOYAGER_API_DATABASE_URL"])
    app = create_app(
        settings=Settings(database_url=os.environ["NIGHT_VOYAGER_API_DATABASE_URL"]),
        session_factory=create_session_factory(engine),
    )
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            invalid_scenario = await client.get(
                "/api/v1/plan-execution-context?scenario=arbitrary"
            )
            assert invalid_scenario.status_code == 422
            assert invalid_scenario.headers["content-type"].startswith(
                "application/problem+json"
            )
            assert invalid_scenario.json()["code"] == "request_validation_failed"

            unauthenticated = await client.get(
                "/api/v1/plan-execution-context"
                "?scenario=governed-plan-execution-v1"
            )
            assert unauthenticated.status_code == 401
            assert unauthenticated.json()["code"] == "authentication_failed"

            strict = await client.post(
                "/api/v1/timeline-plans/"
                "94000000-0000-0000-0000-000000000001/executions",
                headers={
                    "Origin": "http://127.0.0.1:3000",
                    "Content-Type": "application/json",
                },
                json={
                    "schema_version": 1,
                    "case_id": "40000000-0000-0000-0000-000000000001",
                    "expected_case_revision": 1,
                    "actor_id": "20000000-0000-0000-0000-000000000002",
                },
            )
            assert strict.status_code == 422
            assert strict.json()["code"] == "request_validation_failed"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_closed_demo_principals_resolve_exactly_one_assigned_scenario() -> None:
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
    app = create_app(settings=settings, session_factory=sessions)
    try:
        for choice, expected_case in (
            (DemoActorChoice.PLAN_EXECUTION_HAPPY_ADVISOR, PLAN_EXECUTION_CASE_ID),
            (DemoActorChoice.PLAN_EXECUTION_HAPPY_STUDENT, PLAN_EXECUTION_CASE_ID),
            (DemoActorChoice.PLAN_EXECUTION_HAPPY_PARENT, PLAN_EXECUTION_CASE_ID),
            (
                DemoActorChoice.PLAN_EXECUTION_BLOCKED_ADVISOR,
                BLOCKED_PLAN_EXECUTION_CASE_ID,
            ),
            (
                DemoActorChoice.PLAN_EXECUTION_BLOCKED_STUDENT,
                BLOCKED_PLAN_EXECUTION_CASE_ID,
            ),
            (
                DemoActorChoice.PLAN_EXECUTION_BLOCKED_PARENT,
                BLOCKED_PLAN_EXECUTION_CASE_ID,
            ),
        ):
            issued = await mint(sessions, choice)
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=ORIGIN
            ) as client:
                client.cookies.set(SESSION_COOKIE, issued.raw_session_token)
                response = await client.get(
                    "/api/v1/plan-execution-context"
                    "?scenario=governed-plan-execution-v1"
                )
            assert response.status_code == 200, response.text
            assert response.json()["case_id"] == str(expected_case)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_demo_session_rotation_stays_within_one_closed_scenario() -> None:
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
    app = create_app(settings=settings, session_factory=sessions)
    try:
        for advisor_choice, student_key, cross_key, expected_case in (
            (
                DemoActorChoice.PLAN_EXECUTION_HAPPY_ADVISOR,
                "plan_execution_happy_student",
                "plan_execution_blocked_parent",
                PLAN_EXECUTION_CASE_ID,
            ),
            (
                DemoActorChoice.PLAN_EXECUTION_BLOCKED_ADVISOR,
                "plan_execution_blocked_student",
                "plan_execution_happy_parent",
                BLOCKED_PLAN_EXECUTION_CASE_ID,
            ),
        ):
            advisor = await mint(sessions, advisor_choice)
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=ORIGIN
            ) as client:
                client.cookies.set(SESSION_COOKIE, advisor.raw_session_token)
                rotated = await client.post(
                    "/api/v1/demo/sessions",
                    headers={
                        "Origin": ORIGIN,
                        "X-CSRF-Token": advisor.raw_csrf_token,
                    },
                    json={"demo_actor": student_key},
                )
                assert rotated.status_code == 201, rotated.text
                assert rotated.json()["role"] == "student"
                context = await client.get(
                    "/api/v1/plan-execution-context"
                    "?scenario=governed-plan-execution-v1"
                )
                assert context.status_code == 200, context.text
                assert context.json()["case_id"] == str(expected_case)
                assert context.json()["active_role"] == "student"

                refused = await client.post(
                    "/api/v1/demo/sessions",
                    headers={
                        "Origin": ORIGIN,
                        "X-CSRF-Token": rotated.json()["csrf_token"],
                    },
                    json={"demo_actor": cross_key},
                )
                assert refused.status_code == 401
                assert refused.json() == {"detail": "authentication failed"}
                assert "night_voyager_session=" not in refused.headers.get(
                    "set-cookie", ""
                )
                unchanged = await client.get(
                    "/api/v1/plan-execution-context"
                    "?scenario=governed-plan-execution-v1"
                )
                assert unchanged.status_code == 200, unchanged.text
                assert unchanged.json()["case_id"] == str(expected_case)
                assert unchanged.json()["active_role"] == "student"

        generic = await mint(sessions, DemoActorChoice.ADVISOR)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url=ORIGIN
        ) as client:
            client.cookies.set(SESSION_COOKIE, generic.raw_session_token)
            refused = await client.post(
                "/api/v1/demo/sessions",
                headers={
                    "Origin": ORIGIN,
                    "X-CSRF-Token": generic.raw_csrf_token,
                },
                json={"demo_actor": "plan_execution_happy_advisor"},
            )
            assert refused.status_code == 401
            assert refused.json() == {"detail": "authentication failed"}
        async with sessions() as session, session.begin():
            resolved = await IdentityService(
                IdentityRepository(session), "test-session-secret"
            ).resolve(generic.raw_session_token)
            assert resolved is not None
            assert resolved.role.value == "advisor"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_authenticated_http_races_replays_and_terminal_refusal() -> None:
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
        student = await mint(
            sessions, DemoActorChoice.PLAN_EXECUTION_HAPPY_STUDENT
        )
        parent = await mint(
            sessions, DemoActorChoice.PLAN_EXECUTION_HAPPY_PARENT
        )
        advisor = await mint(
            sessions, DemoActorChoice.PLAN_EXECUTION_HAPPY_ADVISOR
        )
        app = create_app(settings=settings, session_factory=sessions)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url=ORIGIN
        ) as client:
            start_url = (
                f"/api/v1/timeline-plans/{PLAN_EXECUTION_TIMELINE_ID}/executions"
            )
            start_body = {
                "schema_version": 1,
                "case_id": str(PLAN_EXECUTION_CASE_ID),
                "expected_case_revision": 1,
            }
            client.cookies.set(SESSION_COOKIE, student.raw_session_token)
            rejected_origin = await client.post(
                start_url,
                headers={
                    "Origin": "https://evil.invalid",
                    "X-CSRF-Token": student.raw_csrf_token,
                    "Idempotency-Key": "bad-origin",
                },
                json=start_body,
            )
            assert rejected_origin.status_code == 403
            wrong_csrf = await client.post(
                start_url,
                headers={
                    "Origin": ORIGIN,
                    "X-CSRF-Token": "wrong",
                    "Idempotency-Key": "bad-csrf",
                },
                json=start_body,
            )
            assert wrong_csrf.status_code == 401
            missing_key = await client.post(
                start_url,
                headers={
                    "Origin": ORIGIN,
                    "X-CSRF-Token": student.raw_csrf_token,
                },
                json=start_body,
            )
            assert missing_key.status_code == 400
            assert missing_key.json()["code"] == "invalid_idempotency_key"
            client.cookies.set(SESSION_COOKIE, advisor.raw_session_token)
            wrong_role = await client.post(
                start_url,
                headers={
                    "Origin": ORIGIN,
                    "X-CSRF-Token": advisor.raw_csrf_token,
                    "Idempotency-Key": "advisor-cannot-start",
                },
                json=start_body,
            )
            assert wrong_role.status_code == 404
            assert wrong_role.json()["code"] == "resource_unavailable"

            client.cookies.set(SESSION_COOKIE, student.raw_session_token)
            for body, expected_code in (
                (
                    {**start_body, "expected_case_revision": 2},
                    "stale_execution_version",
                ),
                (
                    {
                        **start_body,
                        "case_id": "40000000-0000-0000-0000-000000000001",
                    },
                    "resource_unavailable",
                ),
            ):
                rejected = await client.post(
                    start_url,
                    headers={
                        "Origin": ORIGIN,
                        "X-CSRF-Token": student.raw_csrf_token,
                        "Idempotency-Key": f"rejected-{expected_code}",
                    },
                    json=body,
                )
                assert rejected.status_code in {404, 409}
                assert rejected.json()["code"] == expected_code

            start_headers = {
                "Origin": ORIGIN,
                "X-CSRF-Token": student.raw_csrf_token,
                "Idempotency-Key": "http-start",
            }
            started = await client.post(start_url, headers=start_headers, json=start_body)
            assert started.status_code == 200, started.text
            start_receipt = started.json()
            execution_id = start_receipt["execution_id"]
            replay = await client.post(start_url, headers=start_headers, json=start_body)
            assert replay.json() == start_receipt
            conflict = await client.post(
                start_url,
                headers=start_headers,
                json={**start_body, "expected_case_revision": 2},
            )
            assert conflict.status_code == 409
            assert conflict.json()["code"] == "idempotency_conflict"

            read_url = (
                f"/api/v1/cases/{PLAN_EXECUTION_CASE_ID}/timeline-execution"
            )
            attest_url = ""
            attest_body: dict[str, Any] = {}
            last_verification: dict[str, Any] = {}
            for ordinal in range(1, 5):
                client.cookies.set(SESSION_COOKIE, student.raw_session_token)
                read = await client.get(read_url)
                assert read.status_code == 200
                view = read.json()
                checkpoint = view["current_checkpoint"]
                assert checkpoint["ordinal"] == ordinal
                actor = (
                    parent
                    if checkpoint["accountable_role"] == "parent"
                    else student
                )
                client.cookies.set(SESSION_COOKIE, actor.raw_session_token)
                attest_url = (
                    f"/api/v1/timeline-executions/{execution_id}/"
                    "checkpoint-attestations"
                )
                attest_body = {
                    "schema_version": 1,
                    "case_id": str(PLAN_EXECUTION_CASE_ID),
                    "checkpoint_id": checkpoint["checkpoint_id"],
                    "expected_execution_version": view["execution"]["row_version"],
                    "expected_checkpoint_version": checkpoint["row_version"],
                    "attestation_kind": "completion",
                    "status_code": "ready_for_advisor",
                    "attestation_code": (
                        f"{checkpoint['milestone_key']}_status_confirmed"
                    ),
                    "reason_code": "not_applicable",
                }
                if ordinal == 1:
                    cross_case_attestation = await client.post(
                        attest_url,
                        headers={
                            "Origin": ORIGIN,
                            "X-CSRF-Token": actor.raw_csrf_token,
                            "Idempotency-Key": "cross-case-attestation",
                        },
                        json={
                            **attest_body,
                            "case_id": "40000000-0000-0000-0000-000000000001",
                        },
                    )
                    assert cross_case_attestation.status_code == 404
                    assert (
                        cross_case_attestation.json()["code"]
                        == "resource_unavailable"
                    )
                    stale = await client.post(
                        attest_url,
                        headers={
                            "Origin": ORIGIN,
                            "X-CSRF-Token": actor.raw_csrf_token,
                            "Idempotency-Key": "stale-execution",
                        },
                        json={**attest_body, "expected_execution_version": 2},
                    )
                    assert stale.json()["code"] == "stale_execution_version"
                    future = view["checkpoints"][1]
                    not_current = await client.post(
                        attest_url,
                        headers={
                            "Origin": ORIGIN,
                            "X-CSRF-Token": actor.raw_csrf_token,
                            "Idempotency-Key": "future-checkpoint",
                        },
                        json={
                            **attest_body,
                            "checkpoint_id": future["checkpoint_id"],
                        },
                    )
                    assert not_current.json()["code"] == "checkpoint_not_current"
                    client.cookies.set(SESSION_COOKIE, advisor.raw_session_token)
                    advisor_attest = await client.post(
                        attest_url,
                        headers={
                            "Origin": ORIGIN,
                            "X-CSRF-Token": advisor.raw_csrf_token,
                            "Idempotency-Key": "advisor-cannot-attest",
                        },
                        json=attest_body,
                    )
                    assert advisor_attest.status_code == 404
                    assert advisor_attest.json()["code"] == "resource_unavailable"
                    client.cookies.set(SESSION_COOKIE, actor.raw_session_token)
                attest_headers = {
                    "Origin": ORIGIN,
                    "X-CSRF-Token": actor.raw_csrf_token,
                    "Idempotency-Key": f"attest-{ordinal}",
                }
                attested = await client.post(
                    attest_url, headers=attest_headers, json=attest_body
                )
                assert attested.status_code == 200, attested.text
                attestation_receipt = attested.json()
                attestation_replay = await client.post(
                    attest_url, headers=attest_headers, json=attest_body
                )
                assert attestation_replay.json() == attestation_receipt
                case_drift = await client.post(
                    attest_url,
                    headers=attest_headers,
                    json={
                        **attest_body,
                        "case_id": "40000000-0000-0000-0000-000000000001",
                    },
                )
                assert case_drift.status_code == 409
                assert case_drift.json()["code"] == "idempotency_conflict"

                client.cookies.set(SESSION_COOKIE, advisor.raw_session_token)
                verify_url = (
                    f"/api/v1/timeline-executions/{execution_id}/"
                    "checkpoint-verifications"
                )
                verify_body = {
                    "schema_version": 1,
                    "case_id": str(PLAN_EXECUTION_CASE_ID),
                    "checkpoint_id": checkpoint["checkpoint_id"],
                    "attestation_id": attestation_receipt["result_id"],
                    "expected_execution_version": attestation_receipt[
                        "after_execution_version"
                    ],
                    "expected_checkpoint_version": attestation_receipt[
                        "after_checkpoint_version"
                    ],
                    "action": "verify",
                    "reason_code": "attestation_verified",
                }
                if ordinal == 1:
                    stale_checkpoint = await client.post(
                        verify_url,
                        headers={
                            "Origin": ORIGIN,
                            "X-CSRF-Token": advisor.raw_csrf_token,
                            "Idempotency-Key": "stale-checkpoint",
                        },
                        json={**verify_body, "expected_checkpoint_version": 1},
                    )
                    assert (
                        stale_checkpoint.json()["code"]
                        == "stale_checkpoint_version"
                    )
                    cross_case = await client.post(
                        verify_url,
                        headers={
                            "Origin": ORIGIN,
                            "X-CSRF-Token": advisor.raw_csrf_token,
                            "Idempotency-Key": "cross-case",
                        },
                        json={
                            **verify_body,
                            "case_id": "40000000-0000-0000-0000-000000000001",
                        },
                    )
                    assert cross_case.status_code == 404
                    assert cross_case.json()["code"] == "resource_unavailable"
                verified = await client.post(
                    verify_url,
                    headers={
                        "Origin": ORIGIN,
                        "X-CSRF-Token": advisor.raw_csrf_token,
                        "Idempotency-Key": f"verify-{ordinal}",
                    },
                    json=verify_body,
                )
                assert verified.status_code == 200, verified.text
                last_verification = verified.json()
                verify_case_drift = await client.post(
                    verify_url,
                    headers={
                        "Origin": ORIGIN,
                        "X-CSRF-Token": advisor.raw_csrf_token,
                        "Idempotency-Key": f"verify-{ordinal}",
                    },
                    json={
                        **verify_body,
                        "case_id": "40000000-0000-0000-0000-000000000001",
                    },
                )
                assert verify_case_drift.status_code == 409
                assert verify_case_drift.json()["code"] == "idempotency_conflict"

            completed = await client.get(read_url)
            assert completed.status_code == 200
            completed_view = completed.json()
            assert completed_view["execution"]["state"] == "completed"
            assert completed_view["current_action"]["code"] == "execution_completed"
            client.cookies.set(SESSION_COOKIE, parent.raw_session_token)
            terminal = await client.post(
                attest_url,
                headers={
                    "Origin": ORIGIN,
                    "X-CSRF-Token": parent.raw_csrf_token,
                    "Idempotency-Key": "post-terminal",
                },
                json={
                    **attest_body,
                    "expected_execution_version": last_verification[
                        "after_execution_version"
                    ],
                    "expected_checkpoint_version": last_verification[
                        "after_checkpoint_version"
                    ],
                },
            )
            assert terminal.status_code == 409
            assert terminal.json()["code"] == "execution_completed"

        async with sessions() as session:
            assert (
                await session.scalar(
                    text(
                        "SELECT count(*) FROM app.timeline_reassessment_requests "
                        "WHERE organization_id=:org AND execution_id=:execution"
                    ),
                    {
                        "org": UUID("10000000-0000-0000-0000-000000000001"),
                        "execution": execution_id,
                    },
                )
                == 0
            )
    finally:
        await engine.dispose()
