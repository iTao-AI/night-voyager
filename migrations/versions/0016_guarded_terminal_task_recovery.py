# ruff: noqa: E501
"""Add advisor consent-bound fresh task recovery without rewriting source history."""

from __future__ import annotations

from collections.abc import Sequence
from importlib import import_module

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BASE = import_module("migrations.versions.0012_versioned_planning_revision")
CREATE_SIGNATURE = _BASE.CREATE_TASK_SIGNATURE
RETRY_SIGNATURE = "app.retry_agent_task(uuid,uuid,uuid,integer,integer,uuid,jsonb,text,text)"
ELIGIBLE_SIGNATURE = "app.project_agent_task_retry_eligible(uuid,uuid,uuid)"

# Keep the actual lineage-aware creation authority. Case serialization now excludes
# concurrent live tasks even when operation or Skill activation pins differ.
CREATE_SQL = _BASE.CREATE_TASK_SQL.replace(
    "  IF EXISTS (\n    SELECT 1 FROM app.agent_tasks t\n    WHERE t.organization_id=p_org AND t.case_id=p_case AND t.operation=p_operation",
    "  IF EXISTS (SELECT 1 FROM app.agent_tasks live_task WHERE live_task.organization_id=p_org AND live_task.case_id=p_case AND live_task.case_revision=p_revision AND live_task.state IN ('queued','leased','running','waiting_review')) THEN RAISE EXCEPTION USING ERRCODE='NV009', MESSAGE='live task already exists'; END IF;\n  IF EXISTS (\n    SELECT 1 FROM app.agent_tasks t\n    WHERE t.organization_id=p_org AND t.case_id=p_case AND t.operation=p_operation",
    1,
)
if CREATE_SQL == _BASE.CREATE_TASK_SQL:
    raise ValueError("creation authority replacement did not match")

ELIGIBLE_SQL = r"""
CREATE FUNCTION app.project_agent_task_retry_eligible(p_org uuid,p_actor uuid,p_source uuid)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE source_task app.agent_tasks%ROWTYPE; current_case app.student_cases%ROWTYPE;
BEGIN
  PERFORM app.assert_m3b_context(p_org,p_actor,'advisor');
  SELECT * INTO source_task FROM app.agent_tasks t WHERE t.organization_id=p_org AND t.id=p_source;
  IF NOT FOUND OR NOT EXISTS (SELECT 1 FROM app.student_case_participants p WHERE p.organization_id=p_org AND p.case_id=source_task.case_id AND p.actor_id=p_actor AND p.role='advisor') THEN
    RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='task unavailable';
  END IF;
  SELECT * INTO current_case FROM app.student_cases c WHERE c.organization_id=p_org AND c.id=source_task.case_id;
  RETURN current_case.state='planning' AND current_case.current_revision=source_task.case_revision
    AND source_task.result_planning_run_id IS NULL
    AND ((source_task.state='failed' AND source_task.terminal_code IN ('transient_unavailable','transport_interrupted','lease_expired')) OR (source_task.state='timed_out' AND source_task.terminal_code='deadline_exceeded'))
    AND source_task.id=(SELECT t.id FROM app.agent_tasks t WHERE t.organization_id=p_org AND t.case_id=source_task.case_id AND t.case_revision=current_case.current_revision ORDER BY t.created_at DESC,t.id LIMIT 1)
    AND NOT EXISTS (SELECT 1 FROM app.agent_tasks t WHERE t.organization_id=p_org AND t.retried_from_task_id=p_source)
    AND NOT EXISTS (SELECT 1 FROM app.agent_tasks t WHERE t.organization_id=p_org AND t.case_id=source_task.case_id AND t.case_revision=source_task.case_revision AND (t.state IN ('queued','leased','running','waiting_review','succeeded') OR t.result_planning_run_id IS NOT NULL))
    AND source_task.policy_version='m3a-policy-v1'
    AND (
      (source_task.operation='generate_planning_run_v1' AND source_task.source_pack_id='50000000-0000-0000-0000-000000000001'::uuid AND source_task.source_pack_version=1 AND EXISTS (SELECT 1 FROM app.source_packs p WHERE p.organization_id=p_org AND p.id=source_task.source_pack_id AND p.version=1 AND p.manifest_sha256='84350ea5705d9681d3e6550e1bd06e3340a9fcf0e7e7bbed4478ed3403405f28'))
      OR (source_task.operation='generate_governed_mixed_planning_run_v1' AND EXISTS (SELECT 1 FROM app.external_evidence_verifications v WHERE v.organization_id=p_org AND v.case_id=source_task.case_id AND v.case_revision=source_task.case_revision AND v.decision='approve' AND v.claim='australia_program_fit' AND v.evidence_role='program_fit' AND v.baseline_source_pack_id=source_task.source_pack_id AND v.promoted_source_pack_version=source_task.source_pack_version AND v.baseline_source_pack_version=1 AND v.baseline_manifest_sha256='84350ea5705d9681d3e6550e1bd06e3340a9fcf0e7e7bbed4478ed3403405f28' AND v.baseline_raw_manifest_sha256='5d455d2c409c322e093f3a116387f3cef0fb7ea0f7357fec5e76e9da5b3a2a25'))
    );
END; $$;
"""

RETRY_SQL = r"""
CREATE FUNCTION app.retry_agent_task(p_org uuid,p_actor uuid,p_source uuid,p_expected_row_version integer,p_expected_case_revision integer,p_task uuid,p_skill_manifest jsonb,p_request_hash text,p_key_hash text)
RETURNS TABLE(task_id uuid,row_version integer,state text,attempt_count integer,replayed boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE source_task app.agent_tasks%ROWTYPE; current_case app.student_cases%ROWTYPE; prior app.idempotency_records%ROWTYPE; successor app.agent_tasks%ROWTYPE; inner_key text; created record;
BEGIN
  PERFORM app.assert_m3b_context(p_org,p_actor,'advisor');
  IF p_source IS NULL OR p_task IS NULL OR p_expected_row_version IS NULL OR p_expected_row_version<=0 OR p_expected_case_revision IS NULL OR p_expected_case_revision<=0 OR p_request_hash IS NULL OR p_request_hash !~ '^[0-9a-f]{64}$' OR p_key_hash IS NULL OR p_key_hash !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid retry command';
  END IF;
  PERFORM pg_advisory_xact_lock(hashtextextended(p_org::text||':'||p_actor::text||':agent_task_retry:'||p_key_hash,0));
  inner_key := encode(sha256(convert_to('agent_task_retry_create:'||p_source::text||':'||p_key_hash,'UTF8')),'hex');
  -- The nested creation lock is taken before Skill/Case, matching ordinary create.
  PERFORM pg_advisory_xact_lock(hashtextextended(p_org::text||':'||p_actor::text||':agent_task_create:'||inner_key,0));
  PERFORM 1 FROM app.skill_definitions d WHERE d.organization_id=p_org AND d.skill_key='study-destination-compare' AND d.binding_kind='planning_runtime' FOR SHARE;
  SELECT * INTO source_task FROM app.agent_tasks t WHERE t.organization_id=p_org AND t.id=p_source;
  IF NOT FOUND OR NOT EXISTS (SELECT 1 FROM app.student_case_participants p WHERE p.organization_id=p_org AND p.case_id=source_task.case_id AND p.actor_id=p_actor AND p.role='advisor') THEN
    RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='task unavailable';
  END IF;
  SELECT * INTO current_case FROM app.student_cases c WHERE c.organization_id=p_org AND c.id=source_task.case_id FOR UPDATE;
  PERFORM 1 FROM app.student_case_participants p WHERE p.organization_id=p_org AND p.case_id=source_task.case_id AND p.actor_id=p_actor AND p.role='advisor' FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='task unavailable'; END IF;
  -- Re-read after Case serialization; no source diagnostic is ever written.
  SELECT * INTO source_task FROM app.agent_tasks t WHERE t.organization_id=p_org AND t.id=p_source;
  IF current_case.current_revision IS DISTINCT FROM p_expected_case_revision OR source_task.case_revision IS DISTINCT FROM p_expected_case_revision OR source_task.row_version IS DISTINCT FROM p_expected_row_version THEN
    RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='retry source is stale';
  END IF;
  SELECT * INTO prior FROM app.idempotency_records r WHERE r.organization_id=p_org AND r.actor_id=p_actor AND r.operation='agent_task_retry' AND r.key_sha256=p_key_hash;
  IF FOUND THEN
    IF prior.request_sha256<>p_request_hash THEN RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='retry request mismatch'; END IF;
    SELECT * INTO successor FROM app.agent_tasks t WHERE t.organization_id=p_org AND t.id=prior.response_id;
    IF successor.retried_from_task_id IS DISTINCT FROM p_source OR successor.case_revision IS DISTINCT FROM p_expected_case_revision THEN RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='retry source mismatch'; END IF;
    RETURN QUERY SELECT successor.id,successor.row_version,successor.state,successor.attempt_count,true;
    RETURN;
  END IF;
  IF NOT COALESCE(app.project_agent_task_retry_eligible(p_org,p_actor,p_source),false) THEN
    RAISE EXCEPTION USING ERRCODE='NV023', MESSAGE='terminal task recovery ineligible';
  END IF;
  SELECT * INTO created FROM app.create_agent_task(p_org,p_actor,source_task.case_id,p_task,source_task.operation,p_expected_case_revision,source_task.source_pack_id,source_task.source_pack_version,source_task.policy_version,p_skill_manifest,p_request_hash,inner_key);
  UPDATE app.agent_tasks t SET retried_from_task_id=p_source WHERE t.organization_id=p_org AND t.id=created.task_id;
  INSERT INTO app.idempotency_records VALUES(p_org,p_actor,'agent_task_retry',p_key_hash,p_request_hash,'agent_task',created.task_id,clock_timestamp());
  RETURN QUERY SELECT created.task_id,created.row_version,created.state,created.attempt_count,false;
END; $$;
"""


# Closed synthetic INITIAL budget lineage for fresh canonical pilot volumes only.
BUDGET_SEED_SIGNATURE = "app.seed_demo_planning_revision_budget(uuid,uuid)"
BUDGET_SEED_SQL = r"""
CREATE FUNCTION app.seed_demo_planning_revision_budget(p_org uuid,p_case uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
  has_any boolean;
  exact_chain boolean;
  country_exact boolean;
  p_advisor uuid := '20000000-0000-0000-0000-000000000001';
  p_parent uuid := '20000000-0000-0000-0000-000000000003';
  c_student uuid := '20000000-0000-0000-0000-000000000002';
  p_thread uuid := CASE p_case WHEN '49000000-0000-0000-0000-000000000001'::uuid THEN '4b000000-0000-0000-0000-000000000001'::uuid WHEN '49000000-0000-0000-0000-000000000002'::uuid THEN '4b000000-0000-0000-0000-000000000002'::uuid END;
  p_message uuid := CASE p_case WHEN '49000000-0000-0000-0000-000000000001'::uuid THEN '4c000000-0000-0000-0000-000000000101'::uuid WHEN '49000000-0000-0000-0000-000000000002'::uuid THEN '4c000000-0000-0000-0000-000000000102'::uuid END;
  c_message uuid := CASE p_case WHEN '49000000-0000-0000-0000-000000000001'::uuid THEN '4c000000-0000-0000-0000-000000000001'::uuid WHEN '49000000-0000-0000-0000-000000000002'::uuid THEN '4c000000-0000-0000-0000-000000000002'::uuid END;
  p_candidate uuid := CASE p_case WHEN '49000000-0000-0000-0000-000000000001'::uuid THEN '4d000000-0000-0000-0000-000000000101'::uuid WHEN '49000000-0000-0000-0000-000000000002'::uuid THEN '4d000000-0000-0000-0000-000000000102'::uuid END;
  c_candidate uuid := CASE p_case WHEN '49000000-0000-0000-0000-000000000001'::uuid THEN '4d000000-0000-0000-0000-000000000001'::uuid WHEN '49000000-0000-0000-0000-000000000002'::uuid THEN '4d000000-0000-0000-0000-000000000002'::uuid END;
  p_verification uuid := CASE p_case WHEN '49000000-0000-0000-0000-000000000001'::uuid THEN '4e000000-0000-0000-0000-000000000101'::uuid WHEN '49000000-0000-0000-0000-000000000002'::uuid THEN '4e000000-0000-0000-0000-000000000102'::uuid END;
  c_verification uuid := CASE p_case WHEN '49000000-0000-0000-0000-000000000001'::uuid THEN '4e000000-0000-0000-0000-000000000001'::uuid WHEN '49000000-0000-0000-0000-000000000002'::uuid THEN '4e000000-0000-0000-0000-000000000002'::uuid END;
  p_fact uuid := CASE p_case WHEN '49000000-0000-0000-0000-000000000001'::uuid THEN '4f000000-0000-0000-0000-000000000101'::uuid WHEN '49000000-0000-0000-0000-000000000002'::uuid THEN '4f000000-0000-0000-0000-000000000102'::uuid END;
  c_fact uuid := CASE p_case WHEN '49000000-0000-0000-0000-000000000001'::uuid THEN '4f000000-0000-0000-0000-000000000001'::uuid WHEN '49000000-0000-0000-0000-000000000002'::uuid THEN '4f000000-0000-0000-0000-000000000002'::uuid END;
  p_budget jsonb := '{"currency": "CNY", "elasticity_bps": 1000, "hard_ceiling_minor": 40000000, "period": "program_total", "preferred_minor": 34000000, "refused": false, "schema_version": 1}';
  p_value_sha256 text := '699323365c6cf5158b03addf8815e3793203ce0e3c0b97a37668dc83644d5d31';
  c_preferred_countries jsonb := '["australia","japan","malaysia"]';
  c_value_sha256 text := '1a94b49fe4387c325f901de7f581b6b0c18ebbbef296c37b75f9cfb29e6aa2b7';
  p_message_request_sha256 text := CASE p_case WHEN '49000000-0000-0000-0000-000000000001'::uuid THEN '80a928d2fb39b4d4b7e1a3c13a66c19f4257bff3f917484fa3062d7459064725' WHEN '49000000-0000-0000-0000-000000000002'::uuid THEN '58269bd021db349c1c69a19aec9b799c7ff9e2d8c90ba669b0e49b9319b0132c' END;
  c_message_request_sha256 text := CASE p_case WHEN '49000000-0000-0000-0000-000000000001'::uuid THEN '73c0530d8c132d21b6b0d14586af5dc3e73e87e9f8ef19e50991b055011f1244' WHEN '49000000-0000-0000-0000-000000000002'::uuid THEN '7f877001d19e08e9596b7d2750ec360b7d4acf9b90b89286a9864f8dac1f1725' END;
  p_candidate_request_sha256 text := CASE p_case WHEN '49000000-0000-0000-0000-000000000001'::uuid THEN '0fca0291531c47d22835593bf9bcdcfae4f289945b1ac20b5eb54535fd0c520f' WHEN '49000000-0000-0000-0000-000000000002'::uuid THEN 'b7efe455f25508e8230d411d15c17afc96f53eeb340848a4a0937afc095a07c9' END;
  c_candidate_request_sha256 text := CASE p_case WHEN '49000000-0000-0000-0000-000000000001'::uuid THEN '8d260f0ae2dc3a421c5a7409f950f9f3f9e4743a1632791e576bd508b215dd63' WHEN '49000000-0000-0000-0000-000000000002'::uuid THEN 'c3c418833190b6dcfb3fcbc22d686b69048a5e7a166f5b25d6a22fe48aa80135' END;
  p_verification_request_sha256 text := CASE p_case WHEN '49000000-0000-0000-0000-000000000001'::uuid THEN '810abc7858e8844814f4732443d57e5121569b754134fa60a817d6c6ab7ed7c0' WHEN '49000000-0000-0000-0000-000000000002'::uuid THEN 'e019f3b7883d3bab507bc1eb3f8b4bc5553aab908d0134d3d72870c5762e1598' END;
  c_verification_request_sha256 text := CASE p_case WHEN '49000000-0000-0000-0000-000000000001'::uuid THEN '5a93792cc96bdc4aeb4957cf1280397f9028810c0d32f53bb15a75c284d6c036' WHEN '49000000-0000-0000-0000-000000000002'::uuid THEN '0f8dedd651fe442331f397304920fde252f08d2af0fff38645a27291ccfbbfd6' END;
BEGIN
  PERFORM app.assert_context(p_org);

  IF p_org IS DISTINCT FROM '10000000-0000-0000-0000-000000000001'::uuid
     OR p_case IS NULL OR p_case NOT IN ('49000000-0000-0000-0000-000000000001'::uuid,'49000000-0000-0000-0000-000000000002'::uuid) THEN
    RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='planning revision demo seed mismatch';
  END IF;
  PERFORM 1 FROM app.student_cases WHERE organization_id=p_org AND id=p_case FOR UPDATE;

  IF NOT EXISTS (SELECT 1 FROM app.organizations WHERE id=p_org AND is_synthetic)
  OR NOT EXISTS (
    SELECT 1
      FROM app.student_cases selected_case
      JOIN app.student_case_revisions revision_row
        ON revision_row.organization_id=selected_case.organization_id
       AND revision_row.case_id=selected_case.id
       AND revision_row.revision=1
     WHERE selected_case.organization_id=p_org
       AND selected_case.id=p_case
       AND selected_case.current_revision=1
       AND selected_case.state='planning'
       AND revision_row.schema_version=1
       AND revision_row.revision_requested_by_review_id IS NULL
       AND revision_row.superseded_planning_run_id IS NULL
       AND revision_row.student_preferences='{"intake": "2027-02", "intended_field": "computing", "preferred_countries": ["australia", "japan", "malaysia"], "schema_version": 1}'::jsonb
       AND revision_row.family_preferences='{"budget": {"currency": "CNY", "elasticity_bps": 1000, "hard_ceiling_minor": 40000000, "period": "program_total", "preferred_minor": 34000000, "refused": false, "schema_version": 1}, "japan_risk_accepted": true, "risk_tolerance": "high", "schema_version": 1}'::jsonb
       AND (SELECT count(*) FROM app.student_case_revisions r WHERE r.organization_id=p_org AND r.case_id=p_case)=1
       AND NOT EXISTS(SELECT 1 FROM app.planning_runs r WHERE r.organization_id=p_org AND r.case_id=p_case)
       AND NOT EXISTS(SELECT 1 FROM app.agent_tasks t WHERE t.organization_id=p_org AND t.case_id=p_case)
  ) OR NOT EXISTS (
    SELECT 1
      FROM app.collaboration_threads thread_row
     WHERE thread_row.organization_id=p_org
       AND thread_row.case_id=p_case
       AND thread_row.id=p_thread
       AND thread_row.created_by_actor_id=p_advisor
       AND thread_row.created_by_role='advisor'
       AND thread_row.created_at=timestamptz '2026-01-01 00:00:00+00'
       AND (
         SELECT count(*)
           FROM app.collaboration_threads case_thread
          WHERE case_thread.organization_id=p_org
            AND case_thread.case_id=p_case
       )=1
  ) OR NOT EXISTS (
    SELECT 1
      FROM app.student_case_participants participant
     WHERE participant.organization_id=p_org
       AND participant.case_id=p_case
       AND participant.actor_id=p_advisor
       AND participant.role='advisor'
  ) OR NOT EXISTS (
    SELECT 1
      FROM app.student_case_participants participant
     WHERE participant.organization_id=p_org
       AND participant.case_id=p_case
       AND participant.actor_id=p_parent
       AND participant.role='parent'
  ) THEN
    RAISE EXCEPTION USING
      ERRCODE='NV003',
      MESSAGE='planning revision demo seed mismatch';
  END IF;

  IF (SELECT count(*) FROM app.student_case_participants WHERE organization_id=p_org AND case_id=p_case)<>3
     OR NOT EXISTS(SELECT 1 FROM app.student_case_participants WHERE organization_id=p_org AND case_id=p_case AND actor_id=c_student AND role='student') THEN
    RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='planning revision demo seed mismatch';
  END IF;
    SELECT
      (SELECT count(*)=1 AND count(*) FILTER (
         WHERE id=c_message
           AND thread_id=p_thread
           AND sequence_no=1
           AND actor_id=c_student
           AND actor_role='student'
           AND body='Synthetic initial preferred countries.'
           AND content_sha256=
             '2e5e0c34691d199e9b3ddc52cc8b869c8e0f03eee68f30eb08407cf3c01455c0'
           AND request_sha256=c_message_request_sha256
           AND created_at=timestamptz '2026-01-01 00:00:01+00'
         )=1
         FROM app.message_events
        WHERE organization_id=p_org AND case_id=p_case AND id<>p_message)
      AND
      (SELECT count(*)=1 AND count(*) FILTER (
         WHERE id=c_candidate
           AND case_revision=1
           AND message_event_id=c_message
           AND subject_actor_id=c_student
           AND subject_role='student'
           AND proposing_actor_id=c_student
           AND proposing_role='student'
           AND fact_key='student.preferred_countries'
           AND proposed_value=c_preferred_countries
           AND value_sha256=c_value_sha256
           AND request_sha256=c_candidate_request_sha256
           AND provenance_kind='participant_proposal'
           AND created_at=timestamptz '2026-01-01 00:00:02+00'
           AND expires_at=timestamptz '2026-01-08 00:00:02+00'
         )=1
         FROM app.memory_candidates
        WHERE organization_id=p_org AND case_id=p_case AND id<>p_candidate)
      AND
      (SELECT count(*)=1 AND count(*) FILTER (
         WHERE id=c_fact
           AND fact_key='student.preferred_countries'
           AND value=c_preferred_countries
           AND value_sha256=c_value_sha256
           AND source_candidate_id=c_candidate
           AND source_message_event_id=c_message
           AND subject_actor_id=c_student
           AND subject_role='student'
           AND confirming_advisor_actor_id=p_advisor
           AND confirming_advisor_role='advisor'
           AND supersedes_fact_id IS NULL
           AND fact_version=1
           AND confirmed_at=timestamptz '2026-01-01 00:00:03+00'
         )=1
         FROM app.confirmed_facts
        WHERE organization_id=p_org AND case_id=p_case AND id<>p_fact)
      AND
      (SELECT count(*)=1 AND count(*) FILTER (
         WHERE id=c_verification
           AND candidate_id=c_candidate
           AND advisor_actor_id=p_advisor
           AND advisor_role='advisor'
           AND decision='confirm'
           AND reason='Synthetic initial fact seed.'
           AND request_sha256=c_verification_request_sha256
           AND result_fact_id=c_fact
           AND result_revision=1
           AND created_at=timestamptz '2026-01-01 00:00:03+00'
         )=1
         FROM app.memory_candidate_verifications
        WHERE organization_id=p_org AND case_id=p_case AND id<>p_verification)
      AND
      (SELECT count(*)=1 AND count(*) FILTER (
         WHERE confirmed_fact_id=c_fact
           AND created_at=timestamptz '2026-01-01 00:00:03+00'
         )=1
         FROM app.case_revision_confirmed_fact_refs
        WHERE organization_id=p_org
          AND case_id=p_case
          AND case_revision=1
          AND fact_key='student.preferred_countries')
    INTO country_exact;

  IF country_exact IS DISTINCT FROM true THEN
    RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='planning revision demo seed mismatch';
  END IF;

  SELECT
    EXISTS(
      SELECT 1 FROM app.message_events
       WHERE organization_id=p_org
         AND (id=p_message OR (case_id=p_case AND id<>c_message))
    ) OR EXISTS(
      SELECT 1 FROM app.memory_candidates
       WHERE organization_id=p_org
         AND (id=p_candidate OR (case_id=p_case AND id<>c_candidate))
    ) OR EXISTS(
      SELECT 1 FROM app.memory_candidate_verifications
       WHERE organization_id=p_org
         AND (id=p_verification OR (case_id=p_case AND id<>c_verification))
    ) OR EXISTS(
      SELECT 1 FROM app.confirmed_facts
       WHERE organization_id=p_org
         AND (id=p_fact OR (case_id=p_case AND id<>c_fact))
    ) OR EXISTS(
      SELECT 1 FROM app.case_revision_confirmed_fact_refs
       WHERE organization_id=p_org
         AND case_id=p_case
         AND case_revision=1
         AND fact_key='family.budget'
    )
  INTO has_any;

  IF has_any THEN
    SELECT
      (SELECT count(*)=1 AND count(*) FILTER (
         WHERE id=p_message
           AND thread_id=p_thread
           AND sequence_no=2
           AND actor_id=p_parent
           AND actor_role='parent'
           AND body='Synthetic initial family budget.'
           AND content_sha256=
             'b9e7fcbfbe9b3a42f60938b5101a546e05ae97b6594e6565c4e6d02a5fa0e5ea'
           AND request_sha256=p_message_request_sha256
           AND created_at=timestamptz '2026-01-01 00:00:01+00'
         )=1
         FROM app.message_events
        WHERE organization_id=p_org AND case_id=p_case AND id<>c_message)
      AND
      (SELECT count(*)=1 AND count(*) FILTER (
         WHERE id=p_candidate
           AND case_revision=1
           AND message_event_id=p_message
           AND subject_actor_id=p_parent
           AND subject_role='parent'
           AND proposing_actor_id=p_parent
           AND proposing_role='parent'
           AND fact_key='family.budget'
           AND proposed_value=p_budget
           AND value_sha256=p_value_sha256
           AND request_sha256=p_candidate_request_sha256
           AND provenance_kind='participant_proposal'
           AND created_at=timestamptz '2026-01-01 00:00:02+00'
           AND expires_at=timestamptz '2026-01-08 00:00:02+00'
         )=1
         FROM app.memory_candidates
        WHERE organization_id=p_org AND case_id=p_case AND id<>c_candidate)
      AND
      (SELECT count(*)=1 AND count(*) FILTER (
         WHERE id=p_fact
           AND fact_key='family.budget'
           AND value=p_budget
           AND value_sha256=p_value_sha256
           AND source_candidate_id=p_candidate
           AND source_message_event_id=p_message
           AND subject_actor_id=p_parent
           AND subject_role='parent'
           AND confirming_advisor_actor_id=p_advisor
           AND confirming_advisor_role='advisor'
           AND supersedes_fact_id IS NULL
           AND fact_version=1
           AND confirmed_at=timestamptz '2026-01-01 00:00:03+00'
         )=1
         FROM app.confirmed_facts
        WHERE organization_id=p_org AND case_id=p_case AND id<>c_fact)
      AND
      (SELECT count(*)=1 AND count(*) FILTER (
         WHERE id=p_verification
           AND candidate_id=p_candidate
           AND advisor_actor_id=p_advisor
           AND advisor_role='advisor'
           AND decision='confirm'
           AND reason='Synthetic initial budget fact seed.'
           AND request_sha256=p_verification_request_sha256
           AND result_fact_id=p_fact
           AND result_revision=1
           AND created_at=timestamptz '2026-01-01 00:00:03+00'
         )=1
         FROM app.memory_candidate_verifications
        WHERE organization_id=p_org AND case_id=p_case AND id<>c_verification)
      AND
      (SELECT count(*)=1 AND count(*) FILTER (
         WHERE confirmed_fact_id=p_fact
           AND created_at=timestamptz '2026-01-01 00:00:03+00'
         )=1
         FROM app.case_revision_confirmed_fact_refs
        WHERE organization_id=p_org
          AND case_id=p_case
          AND case_revision=1
          AND fact_key='family.budget')
    INTO exact_chain;

    IF exact_chain IS DISTINCT FROM true THEN
      RAISE EXCEPTION USING
        ERRCODE='NV003',
        MESSAGE='planning revision demo seed mismatch';
    END IF;
    RETURN;
  END IF;

  INSERT INTO app.message_events(
    organization_id,id,thread_id,case_id,sequence_no,actor_id,actor_role,
    body,content_sha256,request_sha256,created_at
  ) VALUES(
    p_org,p_message,p_thread,p_case,2,p_parent,'parent',
    'Synthetic initial family budget.',
    'b9e7fcbfbe9b3a42f60938b5101a546e05ae97b6594e6565c4e6d02a5fa0e5ea',
    p_message_request_sha256,timestamptz '2026-01-01 00:00:01+00'
  );
  INSERT INTO app.memory_candidates(
    organization_id,id,case_id,case_revision,message_event_id,
    subject_actor_id,subject_role,proposing_actor_id,proposing_role,
    fact_key,proposed_value,value_sha256,request_sha256,created_at,expires_at
  ) VALUES(
    p_org,p_candidate,p_case,1,p_message,p_parent,'parent',p_parent,'parent',
    'family.budget',p_budget,p_value_sha256,
    p_candidate_request_sha256,timestamptz '2026-01-01 00:00:02+00',
    timestamptz '2026-01-08 00:00:02+00'
  );
  INSERT INTO app.confirmed_facts(
    organization_id,id,case_id,fact_key,value,value_sha256,
    source_candidate_id,source_message_event_id,subject_actor_id,subject_role,
    confirming_advisor_actor_id,confirming_advisor_role,supersedes_fact_id,
    fact_version,confirmed_at
  ) VALUES(
    p_org,p_fact,p_case,'family.budget',p_budget,
    p_value_sha256,p_candidate,p_message,p_parent,'parent',p_advisor,'advisor',
    NULL,1,timestamptz '2026-01-01 00:00:03+00'
  );
  INSERT INTO app.memory_candidate_verifications(
    organization_id,id,candidate_id,case_id,advisor_actor_id,advisor_role,
    decision,reason,request_sha256,result_fact_id,result_revision,created_at
  ) VALUES(
    p_org,p_verification,p_candidate,p_case,p_advisor,'advisor','confirm',
    'Synthetic initial budget fact seed.',p_verification_request_sha256,p_fact,1,
    timestamptz '2026-01-01 00:00:03+00'
  );
  INSERT INTO app.case_revision_confirmed_fact_refs(
    organization_id,case_id,case_revision,fact_key,confirmed_fact_id,created_at
  ) VALUES(
    p_org,p_case,1,'family.budget',p_fact,
    timestamptz '2026-01-01 00:00:03+00'
  );
END; $$;

"""


def upgrade() -> None:
    op.execute(
        "ALTER TABLE app.agent_tasks ADD CONSTRAINT agent_tasks_org_case_id_unique UNIQUE (organization_id,case_id,id)"
    )
    op.execute(
        "ALTER TABLE app.agent_tasks ADD COLUMN retried_from_task_id uuid, ADD CONSTRAINT agent_tasks_retry_source_fk FOREIGN KEY (organization_id,case_id,retried_from_task_id) REFERENCES app.agent_tasks(organization_id,case_id,id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX agent_tasks_one_retry_successor ON app.agent_tasks(organization_id,retried_from_task_id) WHERE retried_from_task_id IS NOT NULL"
    )
    op.execute(CREATE_SQL)
    op.execute(ELIGIBLE_SQL)
    op.execute(RETRY_SQL)
    op.execute(BUDGET_SEED_SQL)
    op.execute(f"REVOKE ALL ON FUNCTION {BUDGET_SEED_SIGNATURE} FROM PUBLIC, night_voyager_api, night_voyager_worker")
    for signature in (CREATE_SIGNATURE, RETRY_SIGNATURE, ELIGIBLE_SIGNATURE):
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC, night_voyager_worker")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO night_voyager_api")


def downgrade() -> None:
    op.execute("LOCK TABLE app.agent_tasks,app.idempotency_records IN ACCESS EXCLUSIVE MODE")
    op.execute("ALTER TABLE app.agent_tasks NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE app.idempotency_records NO FORCE ROW LEVEL SECURITY")
    try:
        history = (
            op.get_bind()
            .exec_driver_sql(
                "SELECT EXISTS(SELECT 1 FROM app.agent_tasks WHERE retried_from_task_id IS NOT NULL) OR EXISTS(SELECT 1 FROM app.idempotency_records WHERE operation='agent_task_retry')"
            )
            .scalar_one()
        )
    finally:
        op.execute("ALTER TABLE app.agent_tasks FORCE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE app.idempotency_records FORCE ROW LEVEL SECURITY")
    if history:
        raise RuntimeError("refusing downgrade: terminal task recovery history exists")
    op.execute(f"DROP FUNCTION {BUDGET_SEED_SIGNATURE}")
    op.execute(f"DROP FUNCTION {RETRY_SIGNATURE}")
    op.execute(f"DROP FUNCTION {ELIGIBLE_SIGNATURE}")
    op.execute(_BASE.CREATE_TASK_SQL)
    op.execute("DROP INDEX app.agent_tasks_one_retry_successor")
    op.execute(
        "ALTER TABLE app.agent_tasks DROP CONSTRAINT agent_tasks_retry_source_fk, DROP COLUMN retried_from_task_id, DROP CONSTRAINT agent_tasks_org_case_id_unique"
    )
