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
    op.execute(f"DROP FUNCTION {RETRY_SIGNATURE}")
    op.execute(f"DROP FUNCTION {ELIGIBLE_SIGNATURE}")
    op.execute(_BASE.CREATE_TASK_SQL)
    op.execute("DROP INDEX app.agent_tasks_one_retry_successor")
    op.execute(
        "ALTER TABLE app.agent_tasks DROP CONSTRAINT agent_tasks_retry_source_fk, DROP COLUMN retried_from_task_id, DROP CONSTRAINT agent_tasks_org_case_id_unique"
    )
