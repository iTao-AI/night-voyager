from __future__ import annotations

import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from night_voyager.identity.demo_seed import ensure_seed_allowed

DEMO_ORG = "10000000-0000-0000-0000-000000000001"
ACTORS = (
    ("advisor", "20000000-0000-0000-0000-000000000001", "Demo Advisor"),
    ("student", "20000000-0000-0000-0000-000000000002", "Demo Student"),
    ("parent", "20000000-0000-0000-0000-000000000003", "Demo Parent"),
)


async def seed_demo(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('night_voyager.organization_id', :value, true)"),
                {"value": DEMO_ORG},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.organizations (id, name, is_synthetic) "
                    "VALUES (:id, 'Night Voyager synthetic demo', true) "
                    "ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name"
                ),
                {"id": DEMO_ORG},
            )
            for index, (role, actor_id, display_name) in enumerate(ACTORS, start=1):
                await connection.execute(
                    text(
                        "INSERT INTO app.actors "
                        "(id, organization_id, display_name, is_synthetic) "
                        "VALUES (:id, :organization_id, :display_name, true) "
                        "ON CONFLICT (id) DO UPDATE SET display_name = EXCLUDED.display_name"
                    ),
                    {"id": actor_id, "organization_id": DEMO_ORG, "display_name": display_name},
                )
                await connection.execute(
                    text(
                        "INSERT INTO app.memberships (id, organization_id, actor_id, role) "
                        "VALUES (:id, :organization_id, :actor_id, :role) "
                        "ON CONFLICT (organization_id, actor_id, role) DO NOTHING"
                    ),
                    {
                        "id": f"30000000-0000-0000-0000-{index:012d}",
                        "organization_id": DEMO_ORG,
                        "actor_id": actor_id,
                        "role": role,
                    },
                )
                await connection.execute(
                    text(
                        "INSERT INTO auth.demo_principals "
                        "(demo_key, organization_id, actor_id, role) "
                        "VALUES (:role, :organization_id, :actor_id, :role) "
                        "ON CONFLICT (demo_key) DO UPDATE SET "
                        "organization_id = EXCLUDED.organization_id, "
                        "actor_id = EXCLUDED.actor_id, role = EXCLUDED.role"
                    ),
                    {"organization_id": DEMO_ORG, "actor_id": actor_id, "role": role},
                )
    finally:
        await engine.dispose()
    print("demo seed: synthetic principals ready")


def main() -> None:
    environment = os.environ.get("NIGHT_VOYAGER_ENVIRONMENT", "development")
    demo_mode = os.environ.get("NIGHT_VOYAGER_DEMO_MODE", "false").lower() == "true"
    ensure_seed_allowed(environment, demo_mode)
    database_url = os.environ.get("NIGHT_VOYAGER_MIGRATION_DATABASE_URL")
    if not database_url:
        raise SystemExit("NIGHT_VOYAGER_MIGRATION_DATABASE_URL is required")
    asyncio.run(seed_demo(database_url))


if __name__ == "__main__":
    main()
