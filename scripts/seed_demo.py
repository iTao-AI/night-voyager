# ruff: noqa: E501
from __future__ import annotations

import argparse
import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from night_voyager.identity.demo_seed import ensure_seed_allowed
from night_voyager.planning.fixtures import validate_planning_fixture

DEMO_ORG = "10000000-0000-0000-0000-000000000001"
ACTORS = (
    ("advisor", "20000000-0000-0000-0000-000000000001", "Demo Advisor"),
    ("student", "20000000-0000-0000-0000-000000000002", "Demo Student"),
    ("parent", "20000000-0000-0000-0000-000000000003", "Demo Parent"),
)


async def seed_demo(database_url: str, *, include_planning: bool = True) -> None:
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
            if include_planning:
                await _seed_planning_snapshot(connection)
    finally:
        await engine.dispose()
    print("demo seed: synthetic principals ready")


async def _seed_planning_snapshot(connection: AsyncConnection) -> None:
    statements = """
    INSERT INTO app.student_cases (organization_id, id, current_revision)
    VALUES (:org, '40000000-0000-0000-0000-000000000001', 1) ON CONFLICT DO NOTHING;
    INSERT INTO app.student_case_revisions
      (organization_id, case_id, revision, schema_version, student_preferences, family_preferences)
    VALUES (:org, '40000000-0000-0000-0000-000000000001', 1, 1,
      jsonb_build_object('intended_field', 'synthetic computing', 'preferred_countries',
        jsonb_build_array('Australia', 'Japan', 'Malaysia')),
      jsonb_build_object('budget_currency', 'CNY', 'budget_minor', NULL,
        'risk_tolerance', 'conditional'))
    ON CONFLICT DO NOTHING;
    INSERT INTO app.source_packs
      (organization_id, id, version, schema_version, manifest_sha256)
    VALUES (:org, '50000000-0000-0000-0000-000000000001', 1, 1,
      '054414d32ca8861afd41b06fbc06133edc10fbdb5992fa89c9faa0300ffed78c')
    ON CONFLICT DO NOTHING;
    INSERT INTO app.source_pack_entries
      (organization_id, source_pack_id, source_pack_version, id, declared_path, sha256)
    VALUES
      (:org, '50000000-0000-0000-0000-000000000001', 1, '51000000-0000-0000-0000-000000000001', 'sources/australia.txt', 'ec5c5ae9dd8b7575dac15f8e4fcfb1332be2832a0f773a5c4fcd690638038cce'),
      (:org, '50000000-0000-0000-0000-000000000001', 1, '51000000-0000-0000-0000-000000000002', 'sources/japan.txt', '02aaaf05433d55389d95ba22a18f5dd1c05b59d318ca10e83f7f2485115ba92a'),
      (:org, '50000000-0000-0000-0000-000000000001', 1, '51000000-0000-0000-0000-000000000003', 'sources/malaysia.txt', '6c9c0de61110663cba5af542c571bda26791e029f98267790f1065a9ed707179')
    ON CONFLICT DO NOTHING;
    INSERT INTO app.evidence_refs
      (organization_id, id, source_pack_id, source_pack_version, source_entry_id, claim, authority, source_sha256)
    VALUES
      (:org, '60000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000001', 1, '51000000-0000-0000-0000-000000000001', 'program_fit', 'accepted_synthetic_demo', 'ec5c5ae9dd8b7575dac15f8e4fcfb1332be2832a0f773a5c4fcd690638038cce'),
      (:org, '60000000-0000-0000-0000-000000000002', '50000000-0000-0000-0000-000000000001', 1, '51000000-0000-0000-0000-000000000001', 'cost', 'accepted_synthetic_demo', 'ec5c5ae9dd8b7575dac15f8e4fcfb1332be2832a0f773a5c4fcd690638038cce'),
      (:org, '60000000-0000-0000-0000-000000000003', '50000000-0000-0000-0000-000000000001', 1, '51000000-0000-0000-0000-000000000001', 'fx', 'accepted_synthetic_demo', 'ec5c5ae9dd8b7575dac15f8e4fcfb1332be2832a0f773a5c4fcd690638038cce'),
      (:org, '60000000-0000-0000-0000-000000000004', '50000000-0000-0000-0000-000000000001', 1, '51000000-0000-0000-0000-000000000002', 'program_fit', 'accepted_synthetic_demo', '02aaaf05433d55389d95ba22a18f5dd1c05b59d318ca10e83f7f2485115ba92a')
    ON CONFLICT DO NOTHING;
    INSERT INTO app.planning_runs
      (organization_id, id, case_id, case_revision, source_pack_id, source_pack_version, state, reason_code, output_sha256)
    VALUES (:org, '70000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000001', 1, '50000000-0000-0000-0000-000000000001', 1, 'review_required', 'single_fully_evidenced_recommendation', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')
    ON CONFLICT DO NOTHING;
    INSERT INTO app.planning_routes
      (organization_id, planning_run_id, id, country, outcome, reason_code)
    VALUES
      (:org, '70000000-0000-0000-0000-000000000001', '71000000-0000-0000-0000-000000000001', 'Australia', 'recommended_with_condition', 'complete_cost_and_fx_within_boundary'),
      (:org, '70000000-0000-0000-0000-000000000001', '71000000-0000-0000-0000-000000000002', 'Japan', 'conditional', 'synthetic_high_risk_alternative'),
      (:org, '70000000-0000-0000-0000-000000000001', '71000000-0000-0000-0000-000000000003', 'Malaysia', 'blocked', 'direct_program_fit_evidence_absent')
    ON CONFLICT DO NOTHING;
    INSERT INTO app.comparison_dimensions
      (organization_id, planning_run_id, route_id, id, dimension_key, outcome, reason_code)
    VALUES
      (:org, '70000000-0000-0000-0000-000000000001', '71000000-0000-0000-0000-000000000001', '72000000-0000-0000-0000-000000000001', 'program_fit', 'supported', 'accepted_synthetic_demo'),
      (:org, '70000000-0000-0000-0000-000000000001', '71000000-0000-0000-0000-000000000002', '72000000-0000-0000-0000-000000000002', 'risk', 'conditional', 'synthetic_high_risk_alternative'),
      (:org, '70000000-0000-0000-0000-000000000001', '71000000-0000-0000-0000-000000000003', '72000000-0000-0000-0000-000000000003', 'program_fit', 'blocked', 'direct_program_fit_evidence_absent')
    ON CONFLICT DO NOTHING;
    INSERT INTO app.comparison_dimension_evidence_refs
      (organization_id, planning_run_id, route_id, dimension_id, evidence_ref_id)
    VALUES
      (:org, '70000000-0000-0000-0000-000000000001', '71000000-0000-0000-0000-000000000001', '72000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000001'),
      (:org, '70000000-0000-0000-0000-000000000001', '71000000-0000-0000-0000-000000000002', '72000000-0000-0000-0000-000000000002', '60000000-0000-0000-0000-000000000004')
    ON CONFLICT DO NOTHING;
    INSERT INTO app.cost_evidence
      (organization_id, evidence_ref_id, currency, tuition_minor, living_minor, fx_rate, fx_boundary_bps)
    VALUES (:org, '60000000-0000-0000-0000-000000000002', 'AUD', 4000000, 2500000, 4.7, 500)
    ON CONFLICT DO NOTHING;
    INSERT INTO app.ranking_evidence
      (organization_id, evidence_ref_id, ranking_system, rank, publication_year)
    VALUES (:org, '60000000-0000-0000-0000-000000000001', 'synthetic_demo_scale', NULL, 2026)
    ON CONFLICT DO NOTHING;
    """
    for statement in statements.split(";"):
        if statement.strip():
            await connection.execute(text(statement), {"org": DEMO_ORG})


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--identity-only", action="store_true")
    arguments = parser.parse_args(argv)
    snapshot = validate_planning_fixture()
    if arguments.validate_only:
        print(f"planning fixture valid: {snapshot}")
        return
    environment = os.environ.get("NIGHT_VOYAGER_ENVIRONMENT", "development")
    demo_mode = os.environ.get("NIGHT_VOYAGER_DEMO_MODE", "false").lower() == "true"
    ensure_seed_allowed(environment, demo_mode)
    database_url = os.environ.get("NIGHT_VOYAGER_MIGRATION_DATABASE_URL")
    if not database_url:
        raise SystemExit("NIGHT_VOYAGER_MIGRATION_DATABASE_URL is required")
    asyncio.run(seed_demo(database_url, include_planning=not arguments.identity_only))


if __name__ == "__main__":
    main()
