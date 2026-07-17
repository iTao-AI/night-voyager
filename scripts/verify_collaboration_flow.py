from __future__ import annotations

import argparse
import asyncio
import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping
from http.cookiejar import CookieJar
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from night_voyager.identity.demo_seed import (
    COLLABORATION_ACTIVE_CASE_ID,
    COLLABORATION_CASE_ID,
    COLLABORATION_EXPIRED_CANDIDATE_ID,
    COLLABORATION_STALE_CANDIDATE_ID,
    COLLABORATION_THREAD_IDS,
)

ORIGIN = "http://127.0.0.1:3000"
API = "http://127.0.0.1:8000/api/v1"
ORGANIZATION_ID = "10000000-0000-0000-0000-000000000001"
ADVISOR_ID = "20000000-0000-0000-0000-000000000001"
PRIMARY_CASE = str(COLLABORATION_CASE_ID)
ACTIVE_CASE = str(COLLABORATION_ACTIVE_CASE_ID)
PRIMARY_THREAD = str(COLLABORATION_THREAD_IDS["primary"])
ACTIVE_THREAD = str(COLLABORATION_THREAD_IDS["active_task"])
CONFIRM_REASON = "The participant confirmed this bounded preference."

PARTICIPANT_CANDIDATE_FIELDS = {
    "schema_version",
    "fact_key",
    "value",
    "state",
    "created_at",
    "expires_at",
}
PARTICIPANT_FACT_FIELDS = {
    "schema_version",
    "fact_key",
    "value",
    "fact_version",
    "confirmed_at",
    "subject_role",
    "confirming_advisor_role",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def session(role: str) -> tuple[urllib.request.OpenerDirector, str]:
    cookies = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
    with opener.open(
        urllib.request.Request(f"{API}/demo/session-bootstrap", headers={"Origin": ORIGIN})
    ) as response:
        bootstrap = json.load(response)
    request = urllib.request.Request(
        f"{API}/demo/sessions",
        data=json.dumps({"demo_actor": role}).encode(),
        headers={
            "Content-Type": "application/json",
            "Origin": ORIGIN,
            "X-CSRF-Token": bootstrap["csrf_token"],
        },
        method="POST",
    )
    with opener.open(request) as response:
        minted = json.load(response)
    require(minted.get("role") == role, "collaboration proof session role mismatch")
    csrf = minted.get("csrf_token")
    require(
        isinstance(csrf, str) and bool(csrf),
        "collaboration proof session omitted CSRF",
    )
    assert isinstance(csrf, str)
    return opener, csrf


def request_json(
    opener: urllib.request.OpenerDirector,
    request: urllib.request.Request,
    expected_status: int,
) -> dict[str, Any] | list[Any]:
    try:
        with opener.open(request) as response:
            status = response.status
            headers = response.headers
            payload: object = json.load(response)
    except urllib.error.HTTPError as error:
        status = error.code
        headers = error.headers
        payload = cast(object, json.loads(error.read()))
    require(status == expected_status, "collaboration proof returned an unexpected status")
    require(
        headers.get("Cache-Control") == "no-store",
        "collaboration proof response omitted no-store",
    )
    content_type = headers.get("Content-Type", "")
    expected_type = "application/problem+json" if status >= 400 else "application/json"
    require(
        content_type.startswith(expected_type),
        "collaboration proof response content type mismatch",
    )
    if not isinstance(payload, (dict, list)):
        raise SystemExit("collaboration proof response was not JSON")
    return cast(dict[str, Any] | list[Any], payload)


def get_json(
    opener: urllib.request.OpenerDirector,
    path: str,
    *,
    expected_status: int = 200,
) -> dict[str, Any] | list[Any]:
    return request_json(
        opener,
        urllib.request.Request(f"{API}{path}"),
        expected_status,
    )


def post_json(
    opener: urllib.request.OpenerDirector,
    path: str,
    csrf: str,
    key: str,
    payload: Mapping[str, object],
    *,
    expected_status: int = 201,
) -> dict[str, Any]:
    result = request_json(
        opener,
        urllib.request.Request(
            f"{API}{path}",
            data=json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(),
            headers={
                "Content-Type": "application/json",
                "Origin": ORIGIN,
                "X-CSRF-Token": csrf,
                "Idempotency-Key": key,
            },
            method="POST",
        ),
        expected_status,
    )
    if not isinstance(result, dict):
        raise SystemExit("collaboration mutation response was not an object")
    return result


def one(items: dict[str, Any] | list[Any], label: str) -> dict[str, Any]:
    if not isinstance(items, list) or len(items) != 1:
        raise SystemExit(f"{label} cardinality mismatch")
    item = items[0]
    require(isinstance(item, dict), f"{label} projection was not an object")
    return item


def proposal_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "case_revision": 1,
        "proposal": {
            "schema_version": 1,
            "fact_key": "family.risk_tolerance",
            "value": "high",
        },
    }


def verification_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "expected_case_revision": 1,
        "decision": "confirm",
        "reason": CONFIRM_REASON,
    }


def expect_problem(payload: dict[str, Any], code: str) -> None:
    require(payload.get("code") == code, "collaboration proof problem code mismatch")
    require(payload.get("status") in {404, 409}, "collaboration proof problem status mismatch")


async def verify_primary_revision() -> None:
    database_url = os.environ.get("NIGHT_VOYAGER_DATABASE_URL")
    if not database_url:
        raise SystemExit("NIGHT_VOYAGER_DATABASE_URL is required")
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            for key, value in (
                ("organization_id", ORGANIZATION_ID),
                ("actor_id", ADVISOR_ID),
                ("role", "advisor"),
            ):
                await connection.execute(
                    text("SELECT set_config(:key,:value,true)"),
                    {"key": f"night_voyager.{key}", "value": value},
                )
            require(
                await connection.scalar(text("SELECT current_user")) == "night_voyager_api",
                "collaboration proof did not use the API database role",
            )
            current_revision = await connection.scalar(
                text(
                    "SELECT current_revision FROM app.student_cases "
                    "WHERE organization_id=:org AND id=:case"
                ),
                {"org": ORGANIZATION_ID, "case": PRIMARY_CASE},
            )
            revision_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM app.student_case_revisions "
                    "WHERE organization_id=:org AND case_id=:case AND revision=2"
                ),
                {"org": ORGANIZATION_ID, "case": PRIMARY_CASE},
            )
            require(
                current_revision == 2 and revision_count == 1,
                "collaboration confirmation revision did not persist",
            )
    finally:
        await engine.dispose()


def verify_role_safe_facts(
    advisor: urllib.request.OpenerDirector,
    parent: urllib.request.OpenerDirector,
) -> None:
    facts_path = f"/cases/{PRIMARY_CASE}/confirmed-facts"
    advisor_fact = one(get_json(advisor, facts_path), "advisor confirmed fact")
    require(
        set(advisor_fact) > PARTICIPANT_FACT_FIELDS,
        "advisor confirmed fact omitted authority metadata",
    )
    require(
        advisor_fact.get("fact_key") == "family.risk_tolerance"
        and advisor_fact.get("value") == "high"
        and advisor_fact.get("fact_version") == 1
        and advisor_fact.get("reason") == CONFIRM_REASON,
        "advisor confirmed fact projection mismatch",
    )
    parent_fact = one(get_json(parent, facts_path), "participant confirmed fact")
    require(
        set(parent_fact) == PARTICIPANT_FACT_FIELDS,
        "participant confirmed fact leaked authority metadata",
    )
    require(
        parent_fact.get("value") == "high" and parent_fact.get("fact_version") == 1,
        "participant confirmed fact projection mismatch",
    )


def run_initial_flow() -> None:
    advisor, advisor_csrf = session("advisor")
    student, _student_csrf = session("student")
    parent, parent_csrf = session("parent")

    thread_path = f"/cases/{PRIMARY_CASE}/collaboration-thread"
    created = post_json(
        advisor,
        thread_path,
        advisor_csrf,
        "compose-collaboration-thread",
        {"schema_version": 1},
    )
    replayed_thread = post_json(
        advisor,
        thread_path,
        advisor_csrf,
        "compose-collaboration-thread",
        {"schema_version": 1},
    )
    require(created == replayed_thread, "collaboration thread replay mismatch")
    require(created.get("thread_id") == PRIMARY_THREAD, "seeded collaboration thread drift")
    student_thread = get_json(student, thread_path)
    require(
        isinstance(student_thread, dict) and student_thread.get("thread_id") == PRIMARY_THREAD,
        "assigned student could not read the shared thread",
    )

    messages_path = f"/collaboration-threads/{PRIMARY_THREAD}/messages"
    message_payload = {
        "schema_version": 1,
        "body": "Our family can accept a bounded high-risk option.",
    }
    appended = post_json(
        parent,
        messages_path,
        parent_csrf,
        "compose-collaboration-message",
        message_payload,
    )
    appended_replay = post_json(
        parent,
        messages_path,
        parent_csrf,
        "compose-collaboration-message",
        message_payload,
    )
    require(appended == appended_replay, "collaboration message replay mismatch")
    message_id = appended.get("message_event_id")
    require(isinstance(message_id, str), "collaboration message omitted its identity")
    message_page = get_json(student, f"{messages_path}?after_sequence=0&limit=50")
    require(
        isinstance(message_page, dict)
        and len(message_page.get("items", [])) == 1
        and message_page["items"][0].get("body") == message_payload["body"],
        "shared collaboration message projection mismatch",
    )

    proposal_path = f"/messages/{message_id}/memory-candidates"
    proposed = post_json(
        parent,
        proposal_path,
        parent_csrf,
        "compose-collaboration-proposal",
        proposal_payload(),
    )
    proposed_replay = post_json(
        parent,
        proposal_path,
        parent_csrf,
        "compose-collaboration-proposal",
        proposal_payload(),
    )
    require(proposed == proposed_replay, "memory candidate replay mismatch")
    require(
        set(proposed) == PARTICIPANT_CANDIDATE_FIELDS,
        "proposal response leaked candidate authority metadata",
    )
    candidates_path = f"/cases/{PRIMARY_CASE}/memory-candidates"
    parent_candidate = one(get_json(parent, candidates_path), "parent candidate")
    require(
        set(parent_candidate) == PARTICIPANT_CANDIDATE_FIELDS,
        "participant candidate projection leaked authority metadata",
    )
    require(get_json(student, candidates_path) == [], "student saw another actor's proposal")
    advisor_candidate = one(get_json(advisor, candidates_path), "advisor candidate")
    require(
        set(advisor_candidate) > PARTICIPANT_CANDIDATE_FIELDS,
        "advisor candidate omitted authority metadata",
    )
    candidate_id = advisor_candidate.get("candidate_id")
    require(isinstance(candidate_id, str), "advisor candidate omitted its identity")

    verification_path = f"/memory-candidates/{candidate_id}/verification-decisions"
    wrong_role = post_json(
        parent,
        verification_path,
        parent_csrf,
        "compose-collaboration-wrong-role",
        verification_payload(),
        expected_status=404,
    )
    expect_problem(wrong_role, "resource_unavailable")
    verified = post_json(
        advisor,
        verification_path,
        advisor_csrf,
        "compose-collaboration-confirm",
        verification_payload(),
    )
    verified_replay = post_json(
        advisor,
        verification_path,
        advisor_csrf,
        "compose-collaboration-confirm",
        verification_payload(),
    )
    require(verified.get("replayed") is False, "first confirmation was not fresh")
    require(verified_replay.get("replayed") is True, "confirmation replay was not marked")
    require(
        verified.get("verification_id") == verified_replay.get("verification_id")
        and verified.get("result_fact_id") == verified_replay.get("result_fact_id")
        and verified.get("result_revision") == verified_replay.get("result_revision") == 2,
        "confirmation replay authority mismatch",
    )
    verify_role_safe_facts(advisor, parent)

    active_message = post_json(
        parent,
        f"/collaboration-threads/{ACTIVE_THREAD}/messages",
        parent_csrf,
        "compose-collaboration-active-message",
        {"schema_version": 1, "body": "Keep this preference pending during review."},
    )
    active_message_id = active_message.get("message_event_id")
    require(isinstance(active_message_id, str), "active-task message omitted its identity")
    post_json(
        parent,
        f"/messages/{active_message_id}/memory-candidates",
        parent_csrf,
        "compose-collaboration-active-proposal",
        proposal_payload(),
    )
    active_candidate = one(
        get_json(advisor, f"/cases/{ACTIVE_CASE}/memory-candidates"),
        "active-task candidate",
    )
    active_candidate_id = active_candidate.get("candidate_id")
    require(isinstance(active_candidate_id, str), "active-task candidate omitted its identity")
    active_problem = post_json(
        advisor,
        f"/memory-candidates/{active_candidate_id}/verification-decisions",
        advisor_csrf,
        "compose-collaboration-active-confirm",
        verification_payload(),
        expected_status=409,
    )
    expect_problem(active_problem, "active_task_blocks_revision")

    stale_problem = post_json(
        advisor,
        f"/memory-candidates/{COLLABORATION_STALE_CANDIDATE_ID}/verification-decisions",
        advisor_csrf,
        "compose-collaboration-stale-confirm",
        verification_payload(),
        expected_status=409,
    )
    expect_problem(stale_problem, "memory_candidate_stale")
    expired_problem = post_json(
        advisor,
        f"/memory-candidates/{COLLABORATION_EXPIRED_CANDIDATE_ID}/verification-decisions",
        advisor_csrf,
        "compose-collaboration-expired-confirm",
        verification_payload(),
        expected_status=409,
    )
    expect_problem(expired_problem, "memory_candidate_expired")

    asyncio.run(verify_primary_revision())
    print("compose-proof: governed collaboration authority flow passed")


def verify_existing_flow() -> None:
    advisor, _advisor_csrf = session("advisor")
    parent, _parent_csrf = session("parent")
    verify_role_safe_facts(advisor, parent)
    asyncio.run(verify_primary_revision())
    print("compose-proof: collaboration fact and revision restart durability passed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-existing", action="store_true")
    arguments = parser.parse_args()
    if arguments.verify_existing:
        verify_existing_flow()
    else:
        run_initial_flow()


if __name__ == "__main__":
    main()
