#!/usr/bin/env python3
"""Seed only the dedicated synthetic DRA authority proof Case."""

from __future__ import annotations

import asyncio
import os
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from night_voyager.identity.demo_seed import DRA_PROOF_CASE_ID, ensure_seed_allowed
from night_voyager.planning.fixtures import validate_planning_fixture

ORG = UUID("10000000-0000-0000-0000-000000000001")
ADVISOR = UUID("20000000-0000-0000-0000-000000000001")
STUDENT = UUID("20000000-0000-0000-0000-000000000002")
PARENT = UUID("20000000-0000-0000-0000-000000000003")


async def seed(
    database_url: str, case_id: UUID = DRA_PROOF_CASE_ID
) -> None:
    fixture_case = validate_planning_fixture().planning_input.case
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id',:org,true)"),
                {"org": str(ORG)},
            )
            exists = await connection.scalar(
                text("SELECT EXISTS(SELECT 1 FROM app.student_cases WHERE id=:case)"),
                {"case": case_id},
            )
            if not exists:
                await connection.execute(
                    text(
                        "SELECT app.publish_case_revision(:org,:case,NULL,1,"
                        "CAST(:student AS jsonb),CAST(:family AS jsonb))"
                    ),
                    {
                        "org": ORG,
                        "case": case_id,
                        "student": fixture_case.student.model_dump_json(),
                        "family": fixture_case.family.model_dump_json(),
                    },
                )
                await connection.execute(
                    text("SELECT app.transition_case(:org,:case,'intake','planning')"),
                    {"org": ORG, "case": case_id},
                )
            await connection.execute(
                text("SELECT app.seed_case_participants(:org,:case,:advisor,:student,:parent)"),
                {
                    "org": ORG,
                    "case": case_id,
                    "advisor": ADVISOR,
                    "student": STUDENT,
                    "parent": PARENT,
                },
            )
    finally:
        await engine.dispose()


def main() -> None:
    ensure_seed_allowed(
        os.environ.get("NIGHT_VOYAGER_ENVIRONMENT", "development"),
        os.environ.get("NIGHT_VOYAGER_DEMO_MODE", "false").lower() == "true",
    )
    database_url = os.environ.get("NIGHT_VOYAGER_MIGRATION_DATABASE_URL")
    if not database_url:
        raise SystemExit("NIGHT_VOYAGER_MIGRATION_DATABASE_URL is required")
    asyncio.run(seed(database_url))
    print("DRA proof seed: dedicated synthetic Case ready")


if __name__ == "__main__":
    main()
