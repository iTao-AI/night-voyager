"""Read-only acceptance of the fixed, synthetic intake revision from PostgreSQL."""

from __future__ import annotations

import asyncio
import json
import os
import re
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from night_voyager.identity.demo_seed import INTAKE_REVISION_CASE_ID
from night_voyager.planning.fixtures import validate_planning_fixture
from night_voyager.planning.intake_fixture import (
    INTAKE_DELAY_MANIFEST_SHA256,
    INTAKE_DELAY_SOURCE_PACK_ID,
    load_exact_intake_delay_fixture,
)
from night_voyager.planning.models import EvidenceAuthority

ORG = UUID("10000000-0000-0000-0000-000000000001")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
PARENT = UUID("20000000-0000-0000-0000-000000000003")
STUDENT = UUID("20000000-0000-0000-0000-000000000002")
PACK = UUID("50000000-0000-0000-0000-000000000001")
DATES = ["2027-09-01", "2027-10-15", "2027-12-15", "2028-01-20"]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def one(rows: list[dict[str, Any]], message: str) -> dict[str, Any]:
    require(len(rows) == 1, message)
    return rows[0]


async def read_persisted_intake_snapshot(
    connection: AsyncConnection, *, case_id: UUID = INTAKE_REVISION_CASE_ID
) -> dict[str, Any]:
    """Bounded table readback; the CLI exposes only the canonical fixed Case."""
    parameters = {"org": ORG, "case": case_id}

    async def rows(table: str, predicate: str) -> list[dict[str, Any]]:
        # Both identifiers come exclusively from the static declarations below.
        result = await connection.execute(
            text(
                f"SELECT to_jsonb(selected) FROM (SELECT * FROM app.{table} item "
                f"WHERE item.organization_id=:org AND {predicate}) selected "
                "ORDER BY to_jsonb(selected)::text"
            ),
            parameters,
        )
        return list(result.scalars())

    snapshot: dict[str, Any] = {
        "case": one(await rows("student_cases", "item.id=:case"), "controlled Case unavailable")
    }
    for key, table in (
        ("revisions", "student_case_revisions"),
        ("runs", "planning_runs"),
        ("tasks", "agent_tasks"),
        ("reviews", "advisor_reviews"),
        ("briefs", "decision_briefs"),
        ("decisions", "family_decisions"),
    ):
        snapshot[key] = await rows(table, "item.case_id=:case")
    run_predicate = (
        "item.planning_run_id IN (SELECT id FROM app.planning_runs "
        "WHERE organization_id=:org AND case_id=:case)"
    )
    for key, table in (
        ("routes", "planning_routes"),
        ("costs", "cost_evidence"),
        ("dimensions", "comparison_dimensions"),
        ("dimension_evidence", "comparison_dimension_evidence_refs"),
        ("rankings", "ranking_evidence"),
    ):
        snapshot[key] = await rows(table, run_predicate)
    snapshot["timelines"] = await rows(
        "timeline_plans",
        "item.family_decision_id IN (SELECT id FROM app.family_decisions "
        "WHERE organization_id=:org AND case_id=:case)",
    )
    context = {**parameters, "actor": ADVISOR}
    candidates = await connection.execute(
        text("SELECT projection FROM app.read_memory_candidates(:org,:actor,'advisor',:case,100)"),
        context,
    )
    snapshot["candidates"] = list(candidates.scalars())
    facts = await connection.execute(
        text(
            "SELECT projection FROM app.read_confirmed_facts("
            ":org,:actor,'advisor',:case,NULL,NULL,NULL,100)"
        ),
        context,
    )
    unique = {json.dumps(row, sort_keys=True): row for row in facts.scalars()}
    snapshot["facts"] = [unique[key] for key in sorted(unique)]
    for key, table, field in (
        ("packs", "source_packs", "id"),
        ("entries", "source_pack_entries", "source_pack_id"),
        ("evidence", "evidence_refs", "source_pack_id"),
    ):
        version_field = "version" if table == "source_packs" else "source_pack_version"
        snapshot[key] = await rows(
            table,
            f"(item.{field},item.{version_field}) "
            "IN (SELECT source_pack_id,source_pack_version FROM app.planning_runs "
            "WHERE organization_id=:org AND case_id=:case)",
        )
    return snapshot


def verify_persisted_intake_revision(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Reject incomplete, ambiguous or incorrectly joined business acceptance."""
    case = snapshot["case"]
    require(
        case["id"] == str(INTAKE_REVISION_CASE_ID)
        and case["organization_id"] == str(ORG)
        and case["current_revision"] == 2
        and case["state"] == "plan_ready",
        "controlled Case is not finalized at revision 2",
    )
    for key, count in (
        ("revisions", 2),
        ("runs", 2),
        ("tasks", 2),
        ("reviews", 2),
        ("briefs", 1),
        ("decisions", 1),
        ("timelines", 1),
    ):
        require(len(snapshot[key]) == count, f"unexpected {key} cardinality")
    old_revision, new_revision = sorted(snapshot["revisions"], key=lambda row: row["revision"])
    require(
        [old_revision["revision"], new_revision["revision"]] == [1, 2], "revision lineage invalid"
    )
    old_student = old_revision["student_preferences"]
    new_student = new_revision["student_preferences"]
    require(
        old_student["intake"] == "2027-02"
        and new_student["intake"] == "2028-02"
        and {key: value for key, value in old_student.items() if key != "intake"}
        == {key: value for key, value in new_student.items() if key != "intake"}
        and old_revision["family_preferences"] == new_revision["family_preferences"],
        "intake-only revision changed another preference",
    )
    budget = new_revision["family_preferences"]["budget"]
    require(
        (budget["preferred_minor"], budget["hard_ceiling_minor"], budget["elasticity_bps"])
        == (34000000, 40000000, 1000),
        "controlled budget changed",
    )
    old_run, new_run = sorted(snapshot["runs"], key=lambda row: row["case_revision"])
    require(
        [old_run["case_revision"], new_run["case_revision"]] == [1, 2]
        and old_run["is_current"] is False
        and new_run["is_current"] is True
        and all(
            row["state"] == "review_required"
            and row["policy_version"] == "m3a-policy-v1"
            and re.fullmatch(r"[0-9a-f]{64}", row["output_sha256"] or "")
            for row in (old_run, new_run)
        )
        and new_run["supersedes_run_id"] == old_run["id"]
        and new_revision["superseded_planning_run_id"] == old_run["id"],
        "run lineage invalid",
    )
    require(
        (old_run["source_pack_id"], new_run["source_pack_id"])
        == (str(PACK), str(INTAKE_DELAY_SOURCE_PACK_ID))
        and old_run["source_pack_version"] == new_run["source_pack_version"] == 1,
        "frozen source selection invalid",
    )
    packs = {row["id"]: row for row in snapshot["packs"]}
    require(
        len(packs) == 2
        and packs[str(PACK)]["manifest_sha256"] == validate_planning_fixture().manifest_sha256
        and packs[str(INTAKE_DELAY_SOURCE_PACK_ID)]["manifest_sha256"]
        == INTAKE_DELAY_MANIFEST_SHA256,
        "source manifest pins invalid",
    )
    request = one(
        [row for row in snapshot["reviews"] if row["action"] == "request_revision"],
        "request-review cardinality invalid",
    )
    approval = one(
        [row for row in snapshot["reviews"] if row["action"] == "approve_for_consultation"],
        "fresh approval unavailable",
    )
    require(
        request["planning_run_id"] == old_run["id"]
        and request["case_revision"] == 1
        and request["advisor_actor_id"] == str(ADVISOR)
        and new_revision["revision_requested_by_review_id"] == request["id"]
        and approval["planning_run_id"] == new_run["id"]
        and approval["case_revision"] == 2
        and approval["advisor_actor_id"] == str(ADVISOR),
        "review lineage invalid",
    )
    for run in (old_run, new_run):
        task = one(
            [row for row in snapshot["tasks"] if row["result_planning_run_id"] == run["id"]],
            "durable task/run link invalid",
        )
        require(
            task["case_revision"] == run["case_revision"]
            and task["source_pack_id"] == run["source_pack_id"]
            and task["source_pack_version"] == run["source_pack_version"]
            and task["policy_version"] == run["policy_version"]
            and task["state"] == "waiting_review"
            and task["operation"] == "generate_planning_run_v1"
            and task["created_by_actor_id"] == str(ADVISOR)
            and all(
                (task[field] is not None) == (run is new_run)
                for field in (
                    "skill_definition_id",
                    "skill_version_id",
                    "skill_activation_event_id",
                    "skill_activation_sequence",
                    "runtime_binding_sha256",
                )
            ),
            "task runtime/source pin invalid",
        )
        if run is new_run:
            require(
                task["predecessor_planning_run_id"] == old_run["id"], "task predecessor invalid"
            )
    evidence = {row["id"]: row for row in snapshot["evidence"]}
    entries = {row["id"]: row for row in snapshot["entries"]}
    alternate = load_exact_intake_delay_fixture()
    require(
        {
            row["id"]
            for row in snapshot["entries"]
            if row["source_pack_id"] == str(INTAKE_DELAY_SOURCE_PACK_ID)
        }
        == {str(row.entry_id) for row in alternate.source_pack.entries},
        "alternate source entry cardinality invalid",
    )
    for entry in alternate.source_pack.entries:
        expected = entry.model_dump(mode="json", exclude={"schema_version", "entry_id", "path"})
        actual = entries[str(entry.entry_id)]
        require(
            actual["declared_path"] == entry.path
            and actual["source_pack_version"] == 1
            and {key: actual[key] for key in expected} == expected,
            "alternate source metadata drifted",
        )
    for reference in alternate.evidence:
        expected = reference.model_dump(mode="json", exclude={"schema_version", "evidence_id"})
        require(
            {key: evidence[str(reference.evidence_id)][key] for key in expected} == expected,
            "alternate accepted evidence drifted",
        )
    totals: list[int] = []
    for run, expected in (
        (old_run, validate_planning_fixture().planning_input.costs[0]),
        (new_run, load_exact_intake_delay_fixture().costs[0]),
    ):
        cost = one(
            [row for row in snapshot["costs"] if row["planning_run_id"] == run["id"]],
            "one Australia cost per run required",
        )
        for field, value in expected.model_dump(mode="json").items():
            if field in ("schema_version", "organization_id"):
                continue
            actual = Decimal(str(cost[field])) if field == "fx_rate" else cost[field]
            wanted = Decimal(str(value)) if field == "fx_rate" else value
            require(actual == wanted, "stored cost does not match its exact intake fixture")
        total = int((cost["tuition_minor"] + cost["living_minor"]) * Decimal(str(cost["fx_rate"])))
        totals.append(total)
        for field in ("tuition_evidence_id", "living_evidence_id", "fx_evidence_id"):
            ref = evidence[cost[field]]
            entry = entries[ref["source_entry_id"]]
            require(
                ref["source_pack_id"] == run["source_pack_id"]
                and ref["source_pack_version"] == run["source_pack_version"]
                and ref["authority"] == EvidenceAuthority.ACCEPTED_SYNTHETIC_DEMO.value
                and ref["source_sha256"] == entry["sha256"]
                and entry["source_pack_id"] == run["source_pack_id"]
                and entry["snapshot_date"] == "2026-07-01",
                "cost evidence provenance invalid",
            )
    require(totals == [30550000, 32640000], "cost totals invalid")
    routes = {
        run["id"]: {
            row["country"]: row for row in snapshot["routes"] if row["planning_run_id"] == run["id"]
        }
        for run in (old_run, new_run)
    }
    require(
        set(routes[old_run["id"]])
        == set(routes[new_run["id"]])
        == {"australia", "japan", "malaysia"}
        and all(
            (row["outcome"], row["reason_code"])
            == (
                routes[new_run["id"]][country]["outcome"],
                routes[new_run["id"]][country]["reason_code"],
            )
            for country, row in routes[old_run["id"]].items()
        ),
        "country outcome changed unexpectedly",
    )
    brief = snapshot["briefs"][0]
    route = routes[new_run["id"]]["australia"]
    require(
        brief["planning_run_id"] == new_run["id"]
        and brief["case_revision"] == 2
        and brief["advisor_review_id"] == approval["id"]
        and brief["source_pack_id"] == new_run["source_pack_id"]
        and brief["source_pack_version"] == new_run["source_pack_version"]
        and brief["output_sha256"] == new_run["output_sha256"]
        and brief["evidence_projection_sha256"] == new_run["evidence_projection_sha256"]
        and brief["source_snapshot_date"] == "2026-07-01"
        and brief["is_current"] is False
        and brief["family_safe_projection"]["intake"] == "2028-02"
        and brief["family_safe_projection"]["eligible_route_ids"]
        == approval["eligible_route_ids"]
        == [route["id"]],
        "current Brief/approval source join invalid",
    )
    decision = snapshot["decisions"][0]
    require(
        decision["decision_brief_id"] == brief["id"]
        and decision["brief_version"] == brief["brief_version"]
        and decision["selected_route_id"] == route["id"]
        and decision["currency"] == "CNY"
        and decision["accepted_budget_min_minor"] == 32000000
        and decision["accepted_budget_max_minor"] == 36000000
        and decision["accepted_trade_offs"] == ["budget_elasticity"]
        and decision["decision_made_by_actor_id"] == decision["recorded_by_actor_id"] == str(PARENT)
        and decision["source"] == "direct"
        and bool(UUID(decision["receipt_id"])),
        "direct parent receipt invalid",
    )
    timeline = snapshot["timelines"][0]
    require(
        timeline["family_decision_id"] == decision["id"]
        and timeline["country"] == "australia"
        and timeline["intake"] == "2028-02"
        and timeline["milestones"]
        == [
            dict(key=key, due_date=value)
            for key, value in zip(
                ("documents", "application", "visa", "arrival"), DATES, strict=True
            )
        ],
        "persisted February timeline invalid",
    )
    confirmed = [row for row in snapshot["facts"] if row["fact_key"] == "student.intake"]
    require(
        len(confirmed) == 2
        and {row["value"] for row in confirmed} == {"2027-02", "2028-02"}
        and all(row["subject_role"] == "student" for row in confirmed),
        "confirmed intake lineage invalid",
    )
    return {
        "proof_mode": "local-synthetic-runtime-role-database",
        "case_id": case["id"],
        "old_intake": "2027-02",
        "new_intake": "2028-02",
        "as_of": "2026-07-01",
        "old_run_id": old_run["id"],
        "new_run_id": new_run["id"],
        "old_output_sha256": old_run["output_sha256"],
        "new_output_sha256": new_run["output_sha256"],
        "new_source_pack_id": new_run["source_pack_id"],
        "old_cost_minor": totals[0],
        "new_cost_minor": totals[1],
        "receipt_id": decision["receipt_id"],
        "accepted_budget_minor": [32000000, 36000000],
        "timeline_dates": DATES,
        "browser_image_acceptance": "pending",
        "hosted_delivery": "pending",
    }


async def verify_database(database_url: str) -> dict[str, Any]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection, connection.begin():
            await connection.execute(text("SET TRANSACTION READ ONLY"))
            require(
                await connection.scalar(text("SELECT current_user")) == "night_voyager_api",
                "verification requires the runtime API role",
            )
            for key, value in (
                ("organization_id", ORG),
                ("actor_id", ADVISOR),
                ("role", "advisor"),
            ):
                await connection.execute(
                    text("SELECT set_config(:key,:value,true)"),
                    {"key": f"night_voyager.{key}", "value": str(value)},
                )
            return verify_persisted_intake_revision(
                await read_persisted_intake_snapshot(connection)
            )
    finally:
        await engine.dispose()


def main() -> None:
    url = os.environ.get("NIGHT_VOYAGER_API_DATABASE_URL")
    if not url:
        raise SystemExit("NIGHT_VOYAGER_API_DATABASE_URL is required")
    try:
        summary = asyncio.run(verify_database(url))
    except (SQLAlchemyError, ValueError, KeyError, TypeError) as error:
        raise SystemExit("controlled intake database acceptance unavailable") from error
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
