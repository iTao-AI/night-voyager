from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
import urllib.request
from http.cookiejar import CookieJar
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ORIGIN = "http://127.0.0.1:3000"
API = "http://127.0.0.1:8000/api/v1"
ORGANIZATION = "10000000-0000-0000-0000-000000000001"
ADVISOR = "20000000-0000-0000-0000-000000000001"
CASE = "40000000-0000-0000-0000-000000000002"
PACK = "50000000-0000-0000-0000-000000000001"


def session() -> tuple[urllib.request.OpenerDirector, str]:
    cookies = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
    with opener.open(
        urllib.request.Request(f"{API}/demo/session-bootstrap", headers={"Origin": ORIGIN})
    ) as response:
        bootstrap = json.load(response)
    request = urllib.request.Request(
        f"{API}/demo/sessions",
        data=json.dumps({"demo_actor": "advisor"}).encode(),
        headers={
            "Content-Type": "application/json",
            "Origin": ORIGIN,
            "X-CSRF-Token": bootstrap["csrf_token"],
        },
        method="POST",
    )
    with opener.open(request) as response:
        minted = json.load(response)
    return opener, minted["csrf_token"]


def create_task(opener: urllib.request.OpenerDirector, csrf: str) -> str:
    request = urllib.request.Request(
        f"{API}/cases/{CASE}/agent-tasks",
        data=json.dumps(
            {
                "schema_version": 1,
                "operation": "generate_planning_run_v1",
                "expected_case_revision": 1,
                "source_pack_id": PACK,
                "source_pack_version": 1,
                "policy_version": "m3a-policy-v1",
            }
        ).encode(),
        headers={
            "Content-Type": "application/json",
            "Origin": ORIGIN,
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "compose-m4a-planning-task",
        },
        method="POST",
    )
    with opener.open(request) as response:
        result = json.load(response)
    if result["status"] not in {"preparing", "needs_advisor_review"}:
        raise SystemExit("compose M4A task did not enter a public in-progress state")
    return str(result["task_id"])


def get_task(opener: urllib.request.OpenerDirector, task_id: str) -> dict[str, Any]:
    with opener.open(f"{API}/tasks/{task_id}") as response:
        return json.load(response)


def wait_for_task(opener: urllib.request.OpenerDirector, task_id: str) -> dict[str, Any]:
    for _ in range(30):
        task = get_task(opener, task_id)
        if task["status"] == "needs_advisor_review":
            if not task["planning_run_id"]:
                raise SystemExit("compose M4A task omitted its PlanningRun")
            return task
        if task["status"] not in {"preparing"}:
            raise SystemExit(f"compose M4A task ended with unexpected status {task['status']}")
        time.sleep(1)
    raise SystemExit("compose M4A worker did not finish within 30 seconds")


def event_frames(body: str) -> list[tuple[int, str, dict[str, Any]]]:
    frames: list[tuple[int, str, dict[str, Any]]] = []
    for block in body.strip().split("\n\n"):
        if not block or block.startswith(":"):
            continue
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        frames.append((int(fields["id"]), fields["event"], json.loads(fields["data"])))
    return frames


def read_events(
    opener: urllib.request.OpenerDirector,
    task_id: str,
    *,
    after: int | None = None,
) -> list[tuple[int, str, dict[str, Any]]]:
    headers = {} if after is None else {"Last-Event-ID": str(after)}
    request = urllib.request.Request(f"{API}/tasks/{task_id}/events", headers=headers)
    with opener.open(request) as response:
        if not response.headers["Content-Type"].startswith("text/event-stream"):
            raise SystemExit("compose M4A events endpoint did not return SSE")
        return event_frames(response.read().decode())


async def inspect_database(task_id: str) -> dict[str, Any]:
    database_url = os.environ.get("NIGHT_VOYAGER_DATABASE_URL")
    if not database_url:
        raise SystemExit("NIGHT_VOYAGER_DATABASE_URL is required")
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            for name, value in (
                ("night_voyager.organization_id", ORGANIZATION),
                ("night_voyager.actor_id", ADVISOR),
                ("night_voyager.role", "advisor"),
            ):
                await connection.execute(
                    text("SELECT set_config(:name,:value,true)"),
                    {"name": name, "value": value},
                )
            row = (
                await connection.execute(
                    text(
                        "SELECT t.id,t.state,t.result_planning_run_id,r.state AS run_state,"
                        "count(e.event_sequence) AS event_count,"
                        "count(*) FILTER (WHERE e.event_code='heartbeat_recorded') "
                        "AS heartbeat_rows "
                        "FROM app.agent_tasks t JOIN app.planning_runs r "
                        "ON r.organization_id=t.organization_id AND r.id=t.result_planning_run_id "
                        "JOIN app.agent_task_events e ON e.organization_id=t.organization_id "
                        "AND e.task_id=t.id WHERE t.organization_id=:org AND t.id=:task "
                        "GROUP BY t.id,t.state,t.result_planning_run_id,r.state"
                    ),
                    {"org": ORGANIZATION, "task": task_id},
                )
            ).mappings().one()
            return dict(row)
    finally:
        await engine.dispose()


async def latest_task_id() -> str:
    database_url = os.environ.get("NIGHT_VOYAGER_DATABASE_URL")
    if not database_url:
        raise SystemExit("NIGHT_VOYAGER_DATABASE_URL is required")
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            for name, value in (
                ("night_voyager.organization_id", ORGANIZATION),
                ("night_voyager.actor_id", ADVISOR),
                ("night_voyager.role", "advisor"),
            ):
                await connection.execute(
                    text("SELECT set_config(:name,:value,true)"),
                    {"name": name, "value": value},
                )
            task_id = await connection.scalar(
                text(
                    "SELECT id FROM app.agent_tasks WHERE organization_id=:org "
                    "AND case_id=:case ORDER BY created_at DESC LIMIT 1"
                ),
                {"org": ORGANIZATION, "case": CASE},
            )
            if task_id is None:
                raise SystemExit("compose M4A restart proof found no durable task")
            return str(task_id)
    finally:
        await engine.dispose()


def verify(task_id: str, opener: urllib.request.OpenerDirector) -> None:
    task = wait_for_task(opener, task_id)
    frames = read_events(opener, task_id)
    sequences = [frame[0] for frame in frames]
    if sequences != list(range(1, len(frames) + 1)):
        raise SystemExit("compose M4A SSE sequence is not contiguous")
    if frames[-1][1] != "waiting_review":
        raise SystemExit("compose M4A SSE did not close at waiting_review")
    if frames[-1][2]["planning_run_id"] != task["planning_run_id"]:
        raise SystemExit("compose M4A HTTP and SSE PlanningRun identifiers differ")
    reconnect = read_events(opener, task_id, after=sequences[-1] - 1)
    if [frame[0] for frame in reconnect] != [sequences[-1]]:
        raise SystemExit("compose M4A Last-Event-ID replay mismatch")
    evidence = asyncio.run(inspect_database(task_id))
    if evidence["state"] != "waiting_review" or evidence["run_state"] != "review_required":
        raise SystemExit("compose M4A durable task or PlanningRun state mismatch")
    if str(evidence["result_planning_run_id"]) != task["planning_run_id"]:
        raise SystemExit("compose M4A database and HTTP PlanningRun identifiers differ")
    if evidence["event_count"] != len(frames) or evidence["heartbeat_rows"] != 0:
        raise SystemExit("compose M4A durable event projection mismatch")
    print(
        "compose-proof: M4A HTTP-to-worker-to-PlanningRun-to-SSE flow passed "
        f"task={task_id} events={len(frames)}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-existing", action="store_true")
    arguments = parser.parse_args()
    opener, csrf = session()
    task_id = (
        asyncio.run(latest_task_id())
        if arguments.verify_existing
        else create_task(opener, csrf)
    )
    verify(task_id, opener)


if __name__ == "__main__":
    main()
