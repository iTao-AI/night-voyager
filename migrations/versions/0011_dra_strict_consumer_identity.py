# ruff: noqa: E501
"""Persist the closed DRA strict consumer identity."""

from collections.abc import Sequence
from importlib import import_module

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_migration_0010 = import_module(
    "migrations.versions.0010_dra_v0_1_6_live_consumer"
)

LEGACY_IMPORT_SIGNATURE = _migration_0010.IMPORT_SIGNATURE
OUTCOME_SIGNATURE = _migration_0010.OUTCOME_SIGNATURE
LEGACY_IMPORT_FUNCTION_SQL = _migration_0010.IMPORT_FUNCTION_SQL
LEGACY_OUTCOME_FUNCTION_SQL = _migration_0010.OUTCOME_FUNCTION_SQL

UPGRADED_LEGACY_IMPORT_FUNCTION_SQL = LEGACY_IMPORT_FUNCTION_SQL.replace(
    "CREATE FUNCTION app.import_dra_research_candidate(",
    "CREATE OR REPLACE FUNCTION app.import_dra_research_candidate(",
    1,
).replace(
    "INSERT INTO app.dra_research_candidates("
    "organization_id,id,case_id,case_revision,producer_release,producer_commit,",
    "INSERT INTO app.dra_research_candidates("
    "organization_id,id,case_id,case_revision,"
    "producer_repository,producer_ref_kind,producer_ref,"
    "producer_release,producer_commit,",
    1,
).replace(
    "VALUES(p_org,p_candidate,p_case,p_revision,"
    "p_producer_release,p_producer_commit,",
    "VALUES(p_org,p_candidate,p_case,p_revision,"
    "'https://github.com/iTao-AI/decision-research-agent',"
    "'release',p_producer_release,"
    "p_producer_release,p_producer_commit,",
    1,
)
RESTORED_LEGACY_IMPORT_FUNCTION_SQL = LEGACY_IMPORT_FUNCTION_SQL.replace(
    "CREATE FUNCTION app.import_dra_research_candidate(",
    "CREATE OR REPLACE FUNCTION app.import_dra_research_candidate(",
    1,
)

STRICT_IMPORT_SIGNATURE = (
    "app.import_dra_research_candidate("
    "uuid,uuid,uuid,uuid,integer,"
    "text,text,text,text,text,text,text,text,text,text,text,text,text,text,text,"
    "integer,text,jsonb,text,text)"
)

STRICT_IMPORT_FUNCTION_SQL = r"""
CREATE FUNCTION app.import_dra_research_candidate(
  p_org uuid,p_actor uuid,p_case uuid,p_candidate uuid,p_revision integer,
  p_producer_repository text,p_producer_ref_kind text,p_producer_ref text,
  p_producer_release text,p_producer_commit text,
  p_contract_schema text,p_fixture_sha256 text,p_profile_id text,
  p_profile_version text,p_proof_schema text,p_request_identity_sha256 text,
  p_run_id text,p_artifact_id text,p_artifact_kind text,p_artifact_media_type text,
  p_artifact_byte_length integer,p_artifact_sha256 text,
  p_ordered_evidence jsonb,p_request_sha256 text,p_key_sha256 text
) RETURNS TABLE(candidate_id uuid,replayed boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
  prior app.idempotency_records%ROWTYPE;
  evidence_item jsonb;
  evidence_host text;
  seen_evidence_ids text[] := '{}';
  promotable_count integer := 0;
BEGIN
  PERFORM app.assert_m3b_context(p_org,p_actor,'advisor');
  PERFORM pg_advisory_xact_lock(hashtextextended(
    p_org::text||':'||p_actor::text||':'||'dra_candidate_import'||':'||p_key_sha256,0
  ));
  SELECT * INTO prior FROM app.idempotency_records
  WHERE organization_id=p_org AND actor_id=p_actor
    AND operation='dra_candidate_import' AND key_sha256=p_key_sha256;
  IF FOUND THEN
    IF prior.request_sha256<>p_request_sha256 THEN
      RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='idempotency request mismatch';
    END IF;
    RETURN QUERY SELECT prior.response_id,true;
    RETURN;
  END IF;
  IF p_producer_repository<>'https://github.com/iTao-AI/decision-research-agent'
    OR p_producer_ref_kind<>'commit'
    OR p_producer_ref<>'01ba21f2996769e68cbc88f4bb0596740df27f6b'
    OR p_producer_release IS NOT NULL
    OR p_producer_commit<>p_producer_ref
    OR p_contract_schema<>'dra.downstream-consumer.v1'
    OR p_fixture_sha256<>'cc602576115ff9b41b0f07fa5f6ee88db15424760a78ab4611675e62e19a8157'
    OR p_profile_id<>'generic-strict-citation'
    OR p_profile_version<>'1'
    OR p_proof_schema<>'dra.strict-citation-profile.v1'
    OR p_artifact_id<>'research-report.md'
    OR p_artifact_kind<>'research_report_markdown'
    OR p_artifact_media_type<>'text/markdown'
    OR p_artifact_byte_length NOT BETWEEN 1 AND 1048576
    OR p_request_identity_sha256 !~ '^[0-9a-f]{64}$'
    OR p_artifact_sha256 !~ '^[0-9a-f]{64}$'
    OR p_request_sha256 !~ '^[0-9a-f]{64}$'
    OR p_key_sha256 !~ '^[0-9a-f]{64}$'
    OR jsonb_typeof(p_ordered_evidence)<>'array'
    OR jsonb_array_length(p_ordered_evidence)=0
  THEN
    RAISE EXCEPTION USING ERRCODE='NV011', MESSAGE='candidate contract mismatch';
  END IF;
  FOR evidence_item IN
    SELECT value FROM jsonb_array_elements(p_ordered_evidence) item(value)
  LOOP
    IF jsonb_typeof(evidence_item)<>'object'
      OR NOT evidence_item ?& ARRAY[
        'evidence_id','source_url','source_identity','retrieved_at',
        'citation_status','verification_status'
      ]
      OR (SELECT count(*) FROM jsonb_object_keys(evidence_item))<>6
      OR jsonb_typeof(evidence_item->'evidence_id')<>'string'
      OR length(evidence_item->>'evidence_id') NOT BETWEEN 1 AND 200
      OR evidence_item->>'evidence_id'=ANY(seen_evidence_ids)
      OR jsonb_typeof(evidence_item->'source_url') NOT IN ('string','null')
      OR jsonb_typeof(evidence_item->'source_identity')<>'string'
      OR length(evidence_item->>'source_identity') NOT BETWEEN 1 AND 2048
      OR jsonb_typeof(evidence_item->'retrieved_at')<>'string'
      OR NOT pg_input_is_valid(
        evidence_item->>'retrieved_at','timestamp with time zone'
      )
      OR evidence_item->>'retrieved_at' !~ '(Z|[+-][0-9]{2}:[0-9]{2})$'
      OR evidence_item->>'citation_status'<>'cited'
      OR evidence_item->>'verification_status' NOT IN ('verified','unverified')
    THEN
      RAISE EXCEPTION USING ERRCODE='NV011',
        MESSAGE='candidate evidence contract mismatch';
    END IF;
    seen_evidence_ids := array_append(
      seen_evidence_ids,evidence_item->>'evidence_id'
    );
    IF jsonb_typeof(evidence_item->'source_url')='string' THEN
      promotable_count := promotable_count + 1;
      evidence_host := lower(substring(
        evidence_item->>'source_url' from '^https://([^/:?#]+)'
      ));
      IF evidence_host IS NULL
        OR position('@' in evidence_item->>'source_url')>0
        OR evidence_host='localhost'
        OR evidence_host LIKE '%.localhost'
        OR evidence_host LIKE '%.local'
        OR (
          evidence_host !~ '^[0-9]+(\.[0-9]+){3}$'
          AND evidence_host NOT LIKE '%.%'
        )
        OR evidence_host LIKE '[%'
        OR evidence_item->>'source_identity'
          IS DISTINCT FROM evidence_item->>'source_url'
        OR (
          evidence_host ~ '^[0-9]+(\.[0-9]+){3}$'
          AND (
            evidence_host::inet << '0.0.0.0/8'::inet
            OR evidence_host::inet << '10.0.0.0/8'::inet
            OR evidence_host::inet << '100.64.0.0/10'::inet
            OR evidence_host::inet << '127.0.0.0/8'::inet
            OR evidence_host::inet << '169.254.0.0/16'::inet
            OR evidence_host::inet << '172.16.0.0/12'::inet
            OR evidence_host::inet << '192.0.0.0/24'::inet
            OR evidence_host::inet << '192.0.2.0/24'::inet
            OR evidence_host::inet << '192.168.0.0/16'::inet
            OR evidence_host::inet << '198.18.0.0/15'::inet
            OR evidence_host::inet << '198.51.100.0/24'::inet
            OR evidence_host::inet << '203.0.113.0/24'::inet
            OR evidence_host::inet << '224.0.0.0/4'::inet
            OR evidence_host::inet << '240.0.0.0/4'::inet
          )
        )
      THEN
        RAISE EXCEPTION USING ERRCODE='NV011',
          MESSAGE='candidate evidence source mismatch';
      END IF;
    END IF;
  END LOOP;
  IF promotable_count<>1 THEN
    RAISE EXCEPTION USING ERRCODE='NV011',
      MESSAGE='candidate promotable evidence mismatch';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM app.student_case_participants
    WHERE organization_id=p_org AND case_id=p_case
      AND actor_id=p_actor AND role='advisor'
  ) THEN
    RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='candidate unavailable';
  END IF;
  PERFORM 1 FROM app.student_cases
  WHERE organization_id=p_org AND id=p_case
    AND current_revision=p_revision AND state='planning'
  FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='candidate case is stale';
  END IF;
  INSERT INTO app.dra_research_candidates(
    organization_id,id,case_id,case_revision,
    producer_repository,producer_ref_kind,producer_ref,
    producer_release,producer_commit,contract_schema,fixture_sha256,
    profile_id,profile_version,proof_schema,request_identity_sha256,
    run_id,artifact_id,artifact_kind,artifact_media_type,
    artifact_byte_length,artifact_sha256,ordered_evidence,
    import_request_sha256,created_by_actor_id
  ) VALUES(
    p_org,p_candidate,p_case,p_revision,
    p_producer_repository,p_producer_ref_kind,p_producer_ref,
    p_producer_release,p_producer_commit,p_contract_schema,p_fixture_sha256,
    p_profile_id,p_profile_version,p_proof_schema,p_request_identity_sha256,
    p_run_id,p_artifact_id,p_artifact_kind,p_artifact_media_type,
    p_artifact_byte_length,p_artifact_sha256,p_ordered_evidence,
    p_request_sha256,p_actor
  );
  INSERT INTO app.idempotency_records VALUES(
    p_org,p_actor,'dra_candidate_import',p_key_sha256,p_request_sha256,
    'dra_candidate',p_candidate,clock_timestamp()
  );
  RETURN QUERY SELECT p_candidate,false;
END; $$;
"""

OUTCOME_FUNCTION_SQL = LEGACY_OUTCOME_FUNCTION_SQL.replace(
    "candidate_id uuid,case_id uuid,case_revision integer,"
    "\n  producer_release text,producer_commit text,run_id text,",
    "candidate_id uuid,producer_repository text,producer_ref_kind text,"
    "producer_ref text,producer_release text,producer_commit text,"
    "contract_schema text,fixture_sha256 text,profile_id text,"
    "profile_version text,proof_schema text,request_identity_sha256 text,"
    "case_id uuid,case_revision integer,run_id text,",
    1,
).replace(
    "c.id,c.case_id,c.case_revision,c.producer_release,c.producer_commit,",
    "c.id,c.producer_repository,c.producer_ref_kind,c.producer_ref,"
    "c.producer_release,c.producer_commit,c.contract_schema,c.fixture_sha256,"
    "c.profile_id,c.profile_version,c.proof_schema,c.request_identity_sha256,"
    "c.case_id,c.case_revision,",
    1,
)

CLOSED_IDENTITY_CONSTRAINT_SQL = (
    "ALTER TABLE app.dra_research_candidates "
    "ADD CONSTRAINT dra_research_candidates_producer_identity_check CHECK ("
    "("
    "producer_repository="
    "'https://github.com/iTao-AI/decision-research-agent' "
    "AND producer_ref_kind='release' "
    "AND producer_ref=producer_release "
    "AND profile_id='generic' "
    "AND profile_version IS NULL "
    "AND proof_schema IS NULL "
    "AND ("
    "(producer_release='v0.1.3' AND "
    "producer_commit='87b2a8e335385eb865086f7a69fe2b190567cfa2') OR "
    "(producer_release='v0.1.6' AND "
    "producer_commit='7d43324b469cb5e445c2e8be83af3be4d841cf1c')"
    ")"
    ") OR ("
    "producer_repository="
    "'https://github.com/iTao-AI/decision-research-agent' "
    "AND producer_ref_kind='commit' "
    "AND producer_ref='01ba21f2996769e68cbc88f4bb0596740df27f6b' "
    "AND producer_release IS NULL "
    "AND producer_commit=producer_ref "
    "AND contract_schema='dra.downstream-consumer.v1' "
    "AND fixture_sha256="
    "'cc602576115ff9b41b0f07fa5f6ee88db15424760a78ab4611675e62e19a8157' "
    "AND profile_id='generic-strict-citation' "
    "AND profile_version='1' "
    "AND proof_schema='dra.strict-citation-profile.v1'"
    "))"
)


def _freeze_function(signature: str, *, api_execute: bool = True) -> None:
    op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
    if api_execute:
        op.execute(
            f"GRANT EXECUTE ON FUNCTION {signature} TO night_voyager_api"
        )


def upgrade() -> None:
    op.execute(
        "LOCK TABLE app.dra_research_candidates IN ACCESS EXCLUSIVE MODE"
    )
    op.execute(
        "ALTER TABLE app.dra_research_candidates NO FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE app.dra_research_candidates DISABLE TRIGGER dra_research_candidates_immutable"
    )
    op.execute(
        "ALTER TABLE app.dra_research_candidates "
        "ADD COLUMN producer_repository text,"
        "ADD COLUMN producer_ref_kind text,"
        "ADD COLUMN producer_ref text,"
        "ADD COLUMN profile_version text,"
        "ADD COLUMN proof_schema text"
    )
    op.execute(
        "UPDATE app.dra_research_candidates SET "
        "producer_repository="
        "'https://github.com/iTao-AI/decision-research-agent',"
        "producer_ref_kind='release',producer_ref=producer_release"
    )
    op.execute(
        "ALTER TABLE app.dra_research_candidates "
        "ALTER COLUMN producer_repository SET NOT NULL,"
        "ALTER COLUMN producer_ref_kind SET NOT NULL,"
        "ALTER COLUMN producer_ref SET NOT NULL,"
        "ALTER COLUMN producer_release DROP NOT NULL"
    )
    op.execute(
        "ALTER TABLE app.dra_research_candidates "
        "DROP CONSTRAINT dra_research_candidates_producer_identity_check"
    )
    op.execute(
        "ALTER TABLE app.dra_research_candidates "
        "DROP CONSTRAINT dra_research_candidates_profile_id_check"
    )
    op.execute(CLOSED_IDENTITY_CONSTRAINT_SQL)
    op.execute(
        "ALTER TABLE app.dra_research_candidates "
        "ADD CONSTRAINT dra_research_candidates_profile_id_check CHECK ("
        "profile_id IN ('generic','generic-strict-citation'))"
    )
    op.execute(UPGRADED_LEGACY_IMPORT_FUNCTION_SQL.strip())
    op.execute(STRICT_IMPORT_FUNCTION_SQL.strip())
    _freeze_function(LEGACY_IMPORT_SIGNATURE)
    _freeze_function(STRICT_IMPORT_SIGNATURE)
    op.execute(f"DROP FUNCTION {OUTCOME_SIGNATURE}")
    op.execute(OUTCOME_FUNCTION_SQL.strip())
    _freeze_function(OUTCOME_SIGNATURE)
    op.execute(
        "ALTER TABLE app.dra_research_candidates ENABLE TRIGGER dra_research_candidates_immutable"
    )
    op.execute(
        "ALTER TABLE app.dra_research_candidates FORCE ROW LEVEL SECURITY"
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.execute(
        "LOCK TABLE app.dra_research_candidates IN ACCESS EXCLUSIVE MODE"
    )
    op.execute(
        "ALTER TABLE app.dra_research_candidates NO FORCE ROW LEVEL SECURITY"
    )
    try:
        has_strict_history = bind.execute(
            sa.text(
                "SELECT EXISTS(SELECT 1 FROM app.dra_research_candidates "
                "WHERE producer_ref_kind='commit')"
            )
        ).scalar_one()
    finally:
        op.execute(
            "ALTER TABLE app.dra_research_candidates FORCE ROW LEVEL SECURITY"
        )
    if has_strict_history:
        raise RuntimeError(
            "refusing downgrade: DRA strict candidate history exists"
        )

    op.execute(
        "ALTER TABLE app.dra_research_candidates NO FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE app.dra_research_candidates DISABLE TRIGGER dra_research_candidates_immutable"
    )
    op.execute(f"DROP FUNCTION {OUTCOME_SIGNATURE}")
    op.execute(LEGACY_OUTCOME_FUNCTION_SQL.strip())
    _freeze_function(OUTCOME_SIGNATURE)
    op.execute(f"DROP FUNCTION {STRICT_IMPORT_SIGNATURE}")
    op.execute(RESTORED_LEGACY_IMPORT_FUNCTION_SQL.strip())
    op.execute(
        "ALTER TABLE app.dra_research_candidates "
        "DROP CONSTRAINT dra_research_candidates_producer_identity_check"
    )
    op.execute(
        "ALTER TABLE app.dra_research_candidates "
        "DROP CONSTRAINT dra_research_candidates_profile_id_check"
    )
    op.execute(
        "ALTER TABLE app.dra_research_candidates "
        "ALTER COLUMN producer_release SET NOT NULL"
    )
    op.execute(
        "ALTER TABLE app.dra_research_candidates "
        "DROP COLUMN producer_repository,"
        "DROP COLUMN producer_ref_kind,"
        "DROP COLUMN producer_ref,"
        "DROP COLUMN profile_version,"
        "DROP COLUMN proof_schema"
    )
    op.execute(
        "ALTER TABLE app.dra_research_candidates "
        "ADD CONSTRAINT dra_research_candidates_producer_identity_check CHECK ("
        "(producer_release='v0.1.3' AND "
        "producer_commit='87b2a8e335385eb865086f7a69fe2b190567cfa2') OR "
        "(producer_release='v0.1.6' AND "
        "producer_commit='7d43324b469cb5e445c2e8be83af3be4d841cf1c'))"
    )
    op.execute(
        "ALTER TABLE app.dra_research_candidates "
        "ADD CONSTRAINT dra_research_candidates_profile_id_check "
        "CHECK (profile_id = 'generic')"
    )
    _freeze_function(LEGACY_IMPORT_SIGNATURE)
    op.execute(
        "ALTER TABLE app.dra_research_candidates ENABLE TRIGGER dra_research_candidates_immutable"
    )
    op.execute(
        "ALTER TABLE app.dra_research_candidates FORCE ROW LEVEL SECURITY"
    )
