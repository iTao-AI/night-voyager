# ruff: noqa: E501
"""Create the M3A case, evidence, and deterministic planning foundation."""

from collections.abc import Sequence

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_DEFINITIONS = r"""
CREATE TABLE app.student_cases (organization_id uuid NOT NULL, id uuid NOT NULL, current_revision integer, created_at timestamptz NOT NULL DEFAULT clock_timestamp(), PRIMARY KEY (organization_id, id), FOREIGN KEY (organization_id) REFERENCES app.organizations(id));
CREATE TABLE app.student_case_revisions (organization_id uuid NOT NULL, case_id uuid NOT NULL, revision integer NOT NULL CHECK (revision > 0), schema_version integer NOT NULL CHECK (schema_version = 1), student_preferences jsonb NOT NULL, family_preferences jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(), PRIMARY KEY (organization_id, case_id, revision), FOREIGN KEY (organization_id, case_id) REFERENCES app.student_cases(organization_id, id));
CREATE TABLE app.source_packs (organization_id uuid NOT NULL, id uuid NOT NULL, version integer NOT NULL CHECK (version > 0), schema_version integer NOT NULL CHECK (schema_version = 1), manifest_sha256 text NOT NULL CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'), created_at timestamptz NOT NULL DEFAULT clock_timestamp(), PRIMARY KEY (organization_id, id, version), FOREIGN KEY (organization_id) REFERENCES app.organizations(id));
CREATE TABLE app.source_pack_entries (organization_id uuid NOT NULL, source_pack_id uuid NOT NULL, source_pack_version integer NOT NULL, id uuid NOT NULL, declared_path text NOT NULL CHECK (declared_path !~ '(^|/)\.\.(/|$)' AND declared_path !~ '^/'), sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'), PRIMARY KEY (organization_id, source_pack_id, source_pack_version, id), FOREIGN KEY (organization_id, source_pack_id, source_pack_version) REFERENCES app.source_packs(organization_id, id, version));
CREATE TABLE app.evidence_refs (organization_id uuid NOT NULL, id uuid NOT NULL, source_pack_id uuid NOT NULL, source_pack_version integer NOT NULL, source_entry_id uuid NOT NULL, claim text NOT NULL, authority text NOT NULL CHECK (authority IN ('untrusted_candidate','accepted_synthetic_demo','externally_verified')), source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[0-9a-f]{64}$'), PRIMARY KEY (organization_id, id), FOREIGN KEY (organization_id, source_pack_id, source_pack_version, source_entry_id) REFERENCES app.source_pack_entries(organization_id, source_pack_id, source_pack_version, id));
CREATE TABLE app.planning_runs (organization_id uuid NOT NULL, id uuid NOT NULL, case_id uuid NOT NULL, case_revision integer NOT NULL, source_pack_id uuid NOT NULL, source_pack_version integer NOT NULL, state text NOT NULL CHECK (state IN ('pending','running','failed','blocked','review_required')), reason_code text, output_sha256 text CHECK (output_sha256 ~ '^[0-9a-f]{64}$'), created_at timestamptz NOT NULL DEFAULT clock_timestamp(), PRIMARY KEY (organization_id, id), FOREIGN KEY (organization_id, case_id, case_revision) REFERENCES app.student_case_revisions(organization_id, case_id, revision), FOREIGN KEY (organization_id, source_pack_id, source_pack_version) REFERENCES app.source_packs(organization_id, id, version));
CREATE TABLE app.planning_routes (organization_id uuid NOT NULL, planning_run_id uuid NOT NULL, id uuid NOT NULL, country text NOT NULL, outcome text NOT NULL CHECK (outcome IN ('recommended_with_condition','conditional','blocked')), reason_code text NOT NULL, PRIMARY KEY (organization_id, planning_run_id, id), FOREIGN KEY (organization_id, planning_run_id) REFERENCES app.planning_runs(organization_id, id));
CREATE TABLE app.comparison_dimensions (organization_id uuid NOT NULL, planning_run_id uuid NOT NULL, route_id uuid NOT NULL, id uuid NOT NULL, dimension_key text NOT NULL, outcome text NOT NULL CHECK (outcome IN ('supported','conditional','blocked')), reason_code text NOT NULL, PRIMARY KEY (organization_id, planning_run_id, route_id, id), FOREIGN KEY (organization_id, planning_run_id, route_id) REFERENCES app.planning_routes(organization_id, planning_run_id, id));
CREATE TABLE app.comparison_dimension_evidence_refs (organization_id uuid NOT NULL, planning_run_id uuid NOT NULL, route_id uuid NOT NULL, dimension_id uuid NOT NULL, evidence_ref_id uuid NOT NULL, PRIMARY KEY (organization_id, planning_run_id, route_id, dimension_id, evidence_ref_id), FOREIGN KEY (organization_id, planning_run_id, route_id, dimension_id) REFERENCES app.comparison_dimensions(organization_id, planning_run_id, route_id, id), FOREIGN KEY (organization_id, evidence_ref_id) REFERENCES app.evidence_refs(organization_id, id));
CREATE TABLE app.cost_evidence (organization_id uuid NOT NULL, evidence_ref_id uuid NOT NULL, currency text NOT NULL, tuition_minor bigint CHECK (tuition_minor > 0), living_minor bigint CHECK (living_minor > 0), fx_rate numeric CHECK (fx_rate > 0), fx_boundary_bps integer CHECK (fx_boundary_bps > 0), CHECK (tuition_minor IS NOT NULL OR living_minor IS NOT NULL), PRIMARY KEY (organization_id, evidence_ref_id), FOREIGN KEY (organization_id, evidence_ref_id) REFERENCES app.evidence_refs(organization_id, id));
CREATE TABLE app.ranking_evidence (organization_id uuid NOT NULL, evidence_ref_id uuid NOT NULL, ranking_system text NOT NULL, rank integer CHECK (rank > 0), publication_year integer NOT NULL CHECK (publication_year >= 2000), PRIMARY KEY (organization_id, evidence_ref_id), FOREIGN KEY (organization_id, evidence_ref_id) REFERENCES app.evidence_refs(organization_id, id));
"""

TABLES = ("student_cases", "student_case_revisions", "source_packs", "source_pack_entries", "evidence_refs", "planning_runs", "planning_routes", "comparison_dimensions", "comparison_dimension_evidence_refs", "cost_evidence", "ranking_evidence")


def upgrade() -> None:
    for statement in TABLE_DEFINITIONS.split(";\n"):
        if statement.strip():
            op.execute(statement)
    for table in TABLES:
        op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE app.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY {table}_tenant_isolation ON app.{table} USING (organization_id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid) WITH CHECK (organization_id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid)")
    op.execute("GRANT SELECT ON " + ", ".join(f"app.{table}" for table in TABLES) + " TO night_voyager_api, night_voyager_worker")
    op.execute("GRANT INSERT ON " + ", ".join(f"app.{table}" for table in TABLES) + " TO night_voyager_api")
    op.execute("GRANT UPDATE (current_revision) ON app.student_cases TO night_voyager_api")
    op.execute("GRANT UPDATE (state, reason_code, output_sha256) ON app.planning_runs TO night_voyager_api")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE app.{table}")
