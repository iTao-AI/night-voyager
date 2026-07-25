# ruff: noqa: E501
"""Pin new DRA imports and add the closed live-outcome read boundary."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

IMPORT_SIGNATURE = (
    "app.import_dra_research_candidate("
    "uuid,uuid,uuid,uuid,integer,text,text,text,text,text,text,text,text,text,text,"
    "integer,text,jsonb,text,text)"
)
OUTCOME_SIGNATURE = "app.project_dra_live_outcome(uuid,uuid,uuid)"
TASK_AUTHORITY_SIGNATURE = "app.project_agent_task_live_authority(uuid,uuid,uuid)"

REVOKE_IMPORT_SQL = f"REVOKE ALL ON FUNCTION {IMPORT_SIGNATURE} FROM PUBLIC"
GRANT_IMPORT_SQL = f"GRANT EXECUTE ON FUNCTION {IMPORT_SIGNATURE} TO night_voyager_api"
REVOKE_OUTCOME_SQL = f"REVOKE ALL ON FUNCTION {OUTCOME_SIGNATURE} FROM PUBLIC"
GRANT_OUTCOME_SQL = (
    f"GRANT EXECUTE ON FUNCTION {OUTCOME_SIGNATURE} TO night_voyager_api"
)
REVOKE_TASK_AUTHORITY_SQL = (
    f"REVOKE ALL ON FUNCTION {TASK_AUTHORITY_SIGNATURE} FROM PUBLIC"
)
GRANT_TASK_AUTHORITY_SQL = (
    f"GRANT EXECUTE ON FUNCTION {TASK_AUTHORITY_SIGNATURE} TO night_voyager_api"
)

# Exact import authority present at migration 0009. Downgrade restores this byte-for-byte.
_0009_IMPORT_FUNCTION_SQL = r"""
CREATE FUNCTION app.import_dra_research_candidate(
  p_org uuid,p_actor uuid,p_case uuid,p_candidate uuid,p_revision integer,
  p_producer_release text,p_producer_commit text,p_contract_schema text,p_fixture_sha256 text,
  p_profile_id text,p_request_identity_sha256 text,p_run_id text,
  p_artifact_id text,p_artifact_kind text,p_artifact_media_type text,p_artifact_byte_length integer,p_artifact_sha256 text,
  p_ordered_evidence jsonb,p_request_sha256 text,p_key_sha256 text
) RETURNS TABLE(candidate_id uuid,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE prior app.idempotency_records%ROWTYPE; evidence_item jsonb; evidence_host text; seen_evidence_ids text[] := '{}'; promotable_count integer := 0;
BEGIN
  PERFORM app.assert_m3b_context(p_org,p_actor,'advisor');
  PERFORM pg_advisory_xact_lock(hashtextextended(p_org::text||':'||p_actor::text||':'||'dra_candidate_import'||':'||p_key_sha256,0));
  SELECT * INTO prior FROM app.idempotency_records WHERE organization_id=p_org AND actor_id=p_actor AND operation='dra_candidate_import' AND key_sha256=p_key_sha256;
  IF FOUND THEN
    IF prior.request_sha256<>p_request_sha256 THEN RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='idempotency request mismatch'; END IF;
    RETURN QUERY SELECT prior.response_id,true;
    RETURN;
  END IF;
  IF p_producer_release<>'v0.1.3' OR p_producer_commit<>'87b2a8e335385eb865086f7a69fe2b190567cfa2' OR p_contract_schema<>'dra.downstream-consumer.v1' OR p_fixture_sha256<>'cc602576115ff9b41b0f07fa5f6ee88db15424760a78ab4611675e62e19a8157' OR p_profile_id<>'generic' OR p_artifact_id<>'research-report.md' OR p_artifact_kind<>'research_report_markdown' OR p_artifact_media_type<>'text/markdown' OR p_artifact_byte_length NOT BETWEEN 1 AND 1048576 OR p_request_identity_sha256 !~ '^[0-9a-f]{64}$' OR p_artifact_sha256 !~ '^[0-9a-f]{64}$' OR p_request_sha256 !~ '^[0-9a-f]{64}$' OR p_key_sha256 !~ '^[0-9a-f]{64}$' OR jsonb_typeof(p_ordered_evidence)<>'array' OR jsonb_array_length(p_ordered_evidence)=0 THEN RAISE EXCEPTION USING ERRCODE='NV011', MESSAGE='candidate contract mismatch'; END IF;
  FOR evidence_item IN SELECT value FROM jsonb_array_elements(p_ordered_evidence) item(value) LOOP
    IF jsonb_typeof(evidence_item)<>'object'
      OR NOT evidence_item ?& ARRAY['evidence_id','source_url','source_identity','retrieved_at','citation_status','verification_status']
      OR (SELECT count(*) FROM jsonb_object_keys(evidence_item))<>6
      OR jsonb_typeof(evidence_item->'evidence_id')<>'string'
      OR length(evidence_item->>'evidence_id') NOT BETWEEN 1 AND 200
      OR evidence_item->>'evidence_id'=ANY(seen_evidence_ids)
      OR jsonb_typeof(evidence_item->'source_url') NOT IN ('string','null')
      OR jsonb_typeof(evidence_item->'source_identity')<>'string'
      OR length(evidence_item->>'source_identity') NOT BETWEEN 1 AND 2048
      OR jsonb_typeof(evidence_item->'retrieved_at')<>'string'
      OR NOT pg_input_is_valid(evidence_item->>'retrieved_at','timestamp with time zone')
      OR evidence_item->>'retrieved_at' !~ '(Z|[+-][0-9]{2}:[0-9]{2})$'
      OR evidence_item->>'citation_status'<>'cited'
      OR evidence_item->>'verification_status' NOT IN ('verified','unverified')
    THEN RAISE EXCEPTION USING ERRCODE='NV011', MESSAGE='candidate evidence contract mismatch'; END IF;
    seen_evidence_ids := array_append(seen_evidence_ids,evidence_item->>'evidence_id');
    IF jsonb_typeof(evidence_item->'source_url')='string' THEN
      promotable_count := promotable_count + 1;
      evidence_host := lower(substring(evidence_item->>'source_url' from '^https://([^/:?#]+)'));
      IF evidence_host IS NULL OR position('@' in evidence_item->>'source_url')>0
        OR evidence_host='localhost' OR evidence_host LIKE '%.localhost' OR evidence_host LIKE '%.local'
        OR (evidence_host !~ '^[0-9]+(\.[0-9]+){3}$' AND evidence_host NOT LIKE '%.%')
        OR evidence_host LIKE '[%'
        OR evidence_item->>'source_identity' IS DISTINCT FROM evidence_item->>'source_url'
        OR (evidence_host ~ '^[0-9]+(\.[0-9]+){3}$' AND (
          evidence_host::inet << '0.0.0.0/8'::inet OR evidence_host::inet << '10.0.0.0/8'::inet
          OR evidence_host::inet << '100.64.0.0/10'::inet OR evidence_host::inet << '127.0.0.0/8'::inet
          OR evidence_host::inet << '169.254.0.0/16'::inet OR evidence_host::inet << '172.16.0.0/12'::inet
          OR evidence_host::inet << '192.0.0.0/24'::inet OR evidence_host::inet << '192.0.2.0/24'::inet
          OR evidence_host::inet << '192.168.0.0/16'::inet OR evidence_host::inet << '198.18.0.0/15'::inet
          OR evidence_host::inet << '198.51.100.0/24'::inet OR evidence_host::inet << '203.0.113.0/24'::inet
          OR evidence_host::inet << '224.0.0.0/4'::inet OR evidence_host::inet << '240.0.0.0/4'::inet
        ))
      THEN RAISE EXCEPTION USING ERRCODE='NV011', MESSAGE='candidate evidence source mismatch'; END IF;
    END IF;
  END LOOP;
  IF promotable_count<>1 THEN RAISE EXCEPTION USING ERRCODE='NV011', MESSAGE='candidate promotable evidence mismatch'; END IF;
  IF NOT EXISTS (SELECT 1 FROM app.student_case_participants WHERE organization_id=p_org AND case_id=p_case AND actor_id=p_actor AND role='advisor') THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='candidate unavailable'; END IF;
  PERFORM 1 FROM app.student_cases WHERE organization_id=p_org AND id=p_case AND current_revision=p_revision AND state='planning' FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='candidate case is stale'; END IF;
  INSERT INTO app.dra_research_candidates(organization_id,id,case_id,case_revision,producer_release,producer_commit,contract_schema,fixture_sha256,profile_id,request_identity_sha256,run_id,artifact_id,artifact_kind,artifact_media_type,artifact_byte_length,artifact_sha256,ordered_evidence,import_request_sha256,created_by_actor_id) VALUES(p_org,p_candidate,p_case,p_revision,p_producer_release,p_producer_commit,p_contract_schema,p_fixture_sha256,p_profile_id,p_request_identity_sha256,p_run_id,p_artifact_id,p_artifact_kind,p_artifact_media_type,p_artifact_byte_length,p_artifact_sha256,p_ordered_evidence,p_request_sha256,p_actor);
  INSERT INTO app.idempotency_records VALUES(p_org,p_actor,'dra_candidate_import',p_key_sha256,p_request_sha256,'dra_candidate',p_candidate,clock_timestamp());
  RETURN QUERY SELECT p_candidate,false;
END; $$;
"""

IMPORT_FUNCTION_SQL = _0009_IMPORT_FUNCTION_SQL.replace(
    "p_producer_release<>'v0.1.3' OR "
    "p_producer_commit<>'87b2a8e335385eb865086f7a69fe2b190567cfa2'",
    "p_producer_release<>'v0.1.6' OR "
    "p_producer_commit<>'7d43324b469cb5e445c2e8be83af3be4d841cf1c'",
    1,
)

OUTCOME_FUNCTION_SQL = r"""
CREATE FUNCTION app.project_dra_live_outcome(
  p_org uuid,p_actor uuid,p_candidate uuid
) RETURNS TABLE(
  candidate_id uuid,case_id uuid,case_revision integer,
  producer_release text,producer_commit text,run_id text,artifact_sha256 text,
  verification_count bigint,approved_verification_count bigint,
  verification_id uuid,
  promoted_source_pack_id uuid,promoted_source_pack_version integer,
  promoted_source_entry_id uuid,promoted_evidence_id uuid,
  external_claim text,evidence_role text,external_authority text,
  governed_task_count bigint,task_id uuid,task_state text,planning_run_id uuid,
  planning_run_state text,execution_count bigint,execution_id uuid,
  execution_planning_run_id uuid,terminal_event_count bigint,
  terminal_event_id bigint,terminal_event_planning_run_id uuid,sse_cursor bigint,
  skill_definition_id uuid,skill_version_id uuid,skill_activation_event_id uuid,
  skill_activation_sequence bigint,runtime_binding_sha256 text,
  advisor_review_count bigint,review_id uuid,brief_id uuid,
  family_decision_count bigint,decision_id uuid,
  decision_receipt_count bigint,decision_receipt_id uuid,
  timeline_plan_count bigint,timeline_plan_id uuid
) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  PERFORM app.assert_m3b_context(p_org,p_actor,'advisor');
  IF NOT EXISTS (
    SELECT 1 FROM app.student_case_participants p
    JOIN app.dra_research_candidates c
      ON c.organization_id=p.organization_id AND c.case_id=p.case_id
    WHERE c.organization_id=p_org AND c.id=p_candidate
      AND p.actor_id=p_actor AND p.role='advisor'
  ) THEN
    RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='candidate unavailable';
  END IF;
  RETURN QUERY
  SELECT
    c.id,c.case_id,c.case_revision,c.producer_release,c.producer_commit,
    c.run_id,c.artifact_sha256,
    (SELECT count(*) FROM app.external_evidence_verifications vc
      WHERE vc.organization_id=c.organization_id AND vc.candidate_id=c.id),
    (SELECT count(*) FROM app.external_evidence_verifications vc
      WHERE vc.organization_id=c.organization_id AND vc.candidate_id=c.id
        AND vc.decision='approve'),
    v.id,
    v.baseline_source_pack_id,v.promoted_source_pack_version,
    v.promoted_source_entry_id,v.promoted_evidence_id,
    v.claim,v.evidence_role,v.authority,
    (SELECT count(*) FROM app.agent_tasks tc
      WHERE tc.organization_id=c.organization_id AND tc.case_id=c.case_id
        AND tc.case_revision=c.case_revision
        AND tc.operation='generate_governed_mixed_planning_run_v1'
        AND tc.source_pack_id=v.baseline_source_pack_id
        AND tc.source_pack_version=v.promoted_source_pack_version),
    t.id,t.state,t.result_planning_run_id,r.state,
    (SELECT count(*) FROM app.agent_executions x
      WHERE x.organization_id=t.organization_id AND x.task_id=t.id
        AND x.status='succeeded' AND x.result_planning_run_id=t.result_planning_run_id),
    x.id,x.result_planning_run_id,
    (SELECT count(*) FROM app.agent_task_events te
      WHERE te.organization_id=t.organization_id AND te.task_id=t.id
        AND te.event_code='waiting_review'
        AND te.result_planning_run_id=t.result_planning_run_id),
    te.event_sequence,te.result_planning_run_id,te.event_sequence,
    t.skill_definition_id,t.skill_version_id,t.skill_activation_event_id,
    t.skill_activation_sequence,t.runtime_binding_sha256,
    (SELECT count(*) FROM app.advisor_reviews a
      WHERE a.organization_id=c.organization_id
        AND a.planning_run_id=t.result_planning_run_id),
    a.id,b.id,
    (SELECT count(*) FROM app.family_decisions f
      WHERE f.organization_id=c.organization_id
        AND f.planning_run_id=t.result_planning_run_id),
    f.id,
    (SELECT count(*) FROM app.family_decisions f
      WHERE f.organization_id=c.organization_id
        AND f.planning_run_id=t.result_planning_run_id
        AND f.receipt_id IS NOT NULL),
    f.receipt_id,
    (SELECT count(*) FROM app.timeline_plans l
      JOIN app.family_decisions f
        ON f.organization_id=l.organization_id AND f.id=l.family_decision_id
      WHERE f.organization_id=c.organization_id
        AND f.planning_run_id=t.result_planning_run_id),
    l.id
  FROM app.dra_research_candidates c
  LEFT JOIN LATERAL (
    SELECT selected.* FROM app.external_evidence_verifications selected
    WHERE selected.organization_id=c.organization_id
      AND selected.candidate_id=c.id
    ORDER BY selected.created_at,selected.id
    LIMIT 1
  ) v ON true
  LEFT JOIN LATERAL (
    SELECT selected.* FROM app.agent_tasks selected
    WHERE selected.organization_id=c.organization_id
      AND selected.case_id=c.case_id
      AND selected.case_revision=c.case_revision
      AND selected.operation='generate_governed_mixed_planning_run_v1'
      AND selected.source_pack_id=v.baseline_source_pack_id
      AND selected.source_pack_version=v.promoted_source_pack_version
    ORDER BY selected.created_at,selected.id
    LIMIT 1
  ) t ON true
  LEFT JOIN app.planning_runs r
    ON r.organization_id=t.organization_id AND r.id=t.result_planning_run_id
  LEFT JOIN LATERAL (
    SELECT selected.* FROM app.agent_executions selected
    WHERE selected.organization_id=t.organization_id
      AND selected.task_id=t.id AND selected.status='succeeded'
    ORDER BY selected.attempt_no DESC LIMIT 1
  ) x ON true
  LEFT JOIN LATERAL (
    SELECT selected.* FROM app.agent_task_events selected
    WHERE selected.organization_id=t.organization_id
      AND selected.task_id=t.id AND selected.event_code='waiting_review'
    ORDER BY selected.event_sequence DESC LIMIT 1
  ) te ON true
  LEFT JOIN LATERAL (
    SELECT selected.* FROM app.advisor_reviews selected
    WHERE selected.organization_id=t.organization_id
      AND selected.planning_run_id=t.result_planning_run_id
    ORDER BY selected.review_version DESC LIMIT 1
  ) a ON true
  LEFT JOIN app.decision_briefs b
    ON b.organization_id=a.organization_id AND b.advisor_review_id=a.id
  LEFT JOIN app.family_decisions f
    ON f.organization_id=b.organization_id AND f.decision_brief_id=b.id
  LEFT JOIN app.timeline_plans l
    ON l.organization_id=f.organization_id AND l.family_decision_id=f.id
  WHERE c.organization_id=p_org AND c.id=p_candidate;
END; $$;
"""

TASK_AUTHORITY_FUNCTION_SQL = r"""
CREATE FUNCTION app.project_agent_task_live_authority(
  p_org uuid,p_actor uuid,p_task uuid
) RETURNS TABLE(execution_id uuid,terminal_event_id bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  PERFORM app.assert_m3b_context(p_org,p_actor,'advisor');
  IF NOT EXISTS (
    SELECT 1 FROM app.agent_tasks t
    JOIN app.student_case_participants p
      ON p.organization_id=t.organization_id AND p.case_id=t.case_id
    WHERE t.organization_id=p_org AND t.id=p_task
      AND p.actor_id=p_actor AND p.role='advisor'
  ) THEN
    RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='task unavailable';
  END IF;
  RETURN QUERY
  SELECT
    (SELECT x.id FROM app.agent_executions x
      JOIN app.agent_tasks t
        ON t.organization_id=x.organization_id AND t.id=x.task_id
      WHERE x.organization_id=p_org AND x.task_id=p_task
        AND x.status='succeeded'
        AND x.result_planning_run_id=t.result_planning_run_id
      ORDER BY x.attempt_no DESC LIMIT 1),
    (SELECT max(e.event_sequence) FROM app.agent_task_events e
      WHERE e.organization_id=p_org AND e.task_id=p_task);
END; $$;
"""


def _replace_import(function_sql: str) -> None:
    op.execute(f"DROP FUNCTION {IMPORT_SIGNATURE}")
    op.execute(function_sql.strip())
    op.execute(REVOKE_IMPORT_SQL)
    op.execute(GRANT_IMPORT_SQL)


def upgrade() -> None:
    op.execute(
        "ALTER TABLE app.dra_research_candidates "
        "DROP CONSTRAINT dra_research_candidates_producer_release_check"
    )
    op.execute(
        "ALTER TABLE app.dra_research_candidates "
        "DROP CONSTRAINT dra_research_candidates_producer_commit_check"
    )
    op.execute(
        "ALTER TABLE app.dra_research_candidates "
        "ADD CONSTRAINT dra_research_candidates_producer_identity_check CHECK ("
        "(producer_release='v0.1.3' AND "
        "producer_commit='87b2a8e335385eb865086f7a69fe2b190567cfa2') OR "
        "(producer_release='v0.1.6' AND "
        "producer_commit='7d43324b469cb5e445c2e8be83af3be4d841cf1c'))"
    )
    _replace_import(IMPORT_FUNCTION_SQL)
    op.execute(TASK_AUTHORITY_FUNCTION_SQL.strip())
    op.execute(REVOKE_TASK_AUTHORITY_SQL)
    op.execute(GRANT_TASK_AUTHORITY_SQL)
    op.execute(OUTCOME_FUNCTION_SQL.strip())
    op.execute(REVOKE_OUTCOME_SQL)
    op.execute(GRANT_OUTCOME_SQL)


def downgrade() -> None:
    bind = op.get_bind()
    op.execute(
        "ALTER TABLE app.dra_research_candidates NO FORCE ROW LEVEL SECURITY"
    )
    try:
        has_live_history = bind.execute(
            sa.text(
                "SELECT EXISTS(SELECT 1 FROM app.dra_research_candidates "
                "WHERE producer_release='v0.1.6')"
            )
        ).scalar_one()
    finally:
        op.execute(
            "ALTER TABLE app.dra_research_candidates FORCE ROW LEVEL SECURITY"
        )
    if has_live_history:
        raise RuntimeError("refusing downgrade: DRA v0.1.6 candidate history exists")
    op.execute(f"DROP FUNCTION {OUTCOME_SIGNATURE}")
    op.execute(f"DROP FUNCTION {TASK_AUTHORITY_SIGNATURE}")
    _replace_import(_0009_IMPORT_FUNCTION_SQL)
    op.execute(
        "ALTER TABLE app.dra_research_candidates "
        "DROP CONSTRAINT dra_research_candidates_producer_identity_check"
    )
    op.execute(
        "ALTER TABLE app.dra_research_candidates "
        "ADD CONSTRAINT dra_research_candidates_producer_release_check "
        "CHECK (producer_release = 'v0.1.3')"
    )
    op.execute(
        "ALTER TABLE app.dra_research_candidates "
        "ADD CONSTRAINT dra_research_candidates_producer_commit_check "
        "CHECK (producer_commit = "
        "'87b2a8e335385eb865086f7a69fe2b190567cfa2')"
    )
