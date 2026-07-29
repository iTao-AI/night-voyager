from __future__ import annotations

import json
import os
from typing import Any, cast

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.database

ACTIVITY_TABLES = (
    ("timeline_checkpoint_attestations", "attestation_id"),
    ("timeline_checkpoint_verifications", "verification_id"),
    ("timeline_reassessment_requests", "reassessment_id"),
    ("timeline_mutation_receipts", "receipt_id"),
)


@pytest.mark.asyncio
async def test_activity_indexes_have_exact_bounded_order_prefix() -> None:
    engine = create_async_engine(os.environ["NIGHT_VOYAGER_MIGRATION_DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            for table_name, durable_id in ACTIVITY_TABLES:
                definition = await connection.scalar(
                    text(
                        "SELECT pg_get_indexdef(i.indexrelid) "
                        "FROM pg_index i "
                        "JOIN pg_class t ON t.oid=i.indrelid "
                        "JOIN pg_namespace n ON n.oid=t.relnamespace "
                        "WHERE n.nspname='app' AND t.relname=:table "
                        "AND pg_get_indexdef(i.indexrelid) LIKE :prefix"
                    ),
                    {
                        "table": table_name,
                        "prefix": (
                            "%(organization_id, execution_id, created_at DESC, "
                            f"{durable_id} DESC)%"
                        ),
                    },
                )
                assert definition is not None

            await connection.execute(text("SET LOCAL enable_seqscan=off"))
            explained = await connection.scalar(
                text(
                    "EXPLAIN (FORMAT JSON) SELECT attestation_id "
                    "FROM app.timeline_checkpoint_attestations "
                    "WHERE organization_id='10000000-0000-0000-0000-000000000001' "
                    "AND execution_id='70000000-0000-0000-0000-000000000001' "
                    "ORDER BY created_at DESC,attestation_id DESC LIMIT 64"
                )
            )
            plan = (
                cast(list[dict[str, Any]], explained)
                if isinstance(explained, list)
                else cast(list[dict[str, Any]], json.loads(explained))
            )
            assert "Index" in json.dumps(plan)
    finally:
        await engine.dispose()
