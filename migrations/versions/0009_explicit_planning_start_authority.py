# ruff: noqa: E501
"""Make first deterministic task creation the explicit planning-start authority."""

from collections.abc import Sequence

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CREATE_TASK_SIGNATURE = (
    "app.create_agent_task(uuid,uuid,uuid,uuid,text,integer,uuid,integer,"
    "text,jsonb,text,text)"
)
TRANSITION_CASE_SIGNATURE = "app.transition_case(uuid,uuid,text,text)"
REVOKE_TASK_SQL = "REVOKE ALL ON FUNCTION app.create_agent_task(uuid,uuid,uuid,uuid,text,integer,uuid,integer,text,jsonb,text,text) FROM PUBLIC"
GRANT_TASK_SQL = "GRANT EXECUTE ON FUNCTION app.create_agent_task(uuid,uuid,uuid,uuid,text,integer,uuid,integer,text,jsonb,text,text) TO night_voyager_api"
REVOKE_TRANSITION_PUBLIC_SQL = (
    "REVOKE ALL ON FUNCTION app.transition_case(uuid,uuid,text,text) FROM PUBLIC"
)
REVOKE_TRANSITION_API_SQL = "REVOKE ALL ON FUNCTION app.transition_case(uuid,uuid,text,text) FROM night_voyager_api"
GRANT_TRANSITION_API_SQL = "GRANT EXECUTE ON FUNCTION app.transition_case(uuid,uuid,text,text) TO night_voyager_api"

CREATE_TASK_SQL = r"""
CREATE FUNCTION app.create_agent_task(p_org uuid,p_actor uuid,p_case uuid,p_task uuid,p_operation text,p_revision integer,p_pack uuid,p_pack_version integer,p_policy text,p_skill_manifest jsonb,p_request_hash text,p_key_hash text) RETURNS TABLE(task_id uuid,row_version integer,state text,attempt_count integer,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE prior app.idempotency_records%ROWTYPE; selected app.agent_tasks%ROWTYPE; current_case app.student_cases%ROWTYPE; definition app.skill_definitions%ROWTYPE; activation app.skill_activation_events%ROWTYPE; version app.skill_versions%ROWTYPE; starts_planning boolean := false;
BEGIN
  PERFORM app.assert_m3b_context(p_org,p_actor,'advisor');
  PERFORM pg_advisory_xact_lock(hashtextextended(p_org::text||':'||p_actor::text||':agent_task_create:'||p_key_hash,0));
  SELECT * INTO prior FROM app.idempotency_records WHERE organization_id=p_org AND actor_id=p_actor AND operation='agent_task_create' AND key_sha256=p_key_hash;
  IF FOUND THEN
    IF prior.request_sha256<>p_request_hash THEN RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='idempotency request mismatch'; END IF;
    SELECT * INTO selected FROM app.agent_tasks WHERE organization_id=p_org AND id=prior.response_id;
    IF selected.operation<>p_operation THEN RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='idempotency operation mismatch'; END IF;
    RETURN QUERY SELECT selected.id,selected.row_version,selected.state,selected.attempt_count,true;
    RETURN;
  END IF;
  IF p_operation NOT IN ('generate_planning_run_v1','generate_governed_mixed_planning_run_v1')
     OR p_policy<>'m3a-policy-v1' OR p_revision<=0 OR p_pack_version<=0
     OR p_request_hash !~ '^[0-9a-f]{64}$' OR p_key_hash !~ '^[0-9a-f]{64}$'
     OR jsonb_typeof(p_skill_manifest)<>'object' THEN
    RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid task pins';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM app.student_case_participants
    WHERE organization_id=p_org AND case_id=p_case AND actor_id=p_actor AND role='advisor'
  ) THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='participant not assigned'; END IF;
  SELECT * INTO definition FROM app.skill_definitions
   WHERE organization_id=p_org AND skill_key='study-destination-compare'
     AND binding_kind='planning_runtime' FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV015', MESSAGE='active Skill version unavailable'; END IF;
  SELECT * INTO activation FROM app.skill_activation_events
   WHERE organization_id=p_org AND definition_id=definition.id
   ORDER BY activation_sequence DESC LIMIT 1;
  IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV015', MESSAGE='active Skill version unavailable'; END IF;
  SELECT * INTO version FROM app.skill_versions
   WHERE organization_id=p_org AND definition_id=definition.id AND id=activation.activated_version_id;
  IF NOT FOUND OR version.binding_kind<>'planning_runtime' OR version.manifest_projection<>p_skill_manifest
     OR version.runtime_binding_sha256 IS NULL THEN
    RAISE EXCEPTION USING ERRCODE='NV022', MESSAGE='Skill runtime pin is invalid';
  END IF;
  SELECT * INTO current_case FROM app.student_cases c
   WHERE c.organization_id=p_org AND c.id=p_case FOR UPDATE;
  IF NOT FOUND OR current_case.current_revision<>p_revision
     OR NOT EXISTS (
       SELECT 1 FROM app.source_packs s
       WHERE s.organization_id=p_org AND s.id=p_pack AND s.version=p_pack_version
     ) THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='task input is stale'; END IF;
  IF current_case.state='intake' AND p_operation='generate_planning_run_v1' THEN
    starts_planning := true;
  ELSIF current_case.state<>'planning' THEN
    RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='task input is stale';
  END IF;
  IF p_operation='generate_governed_mixed_planning_run_v1' AND NOT EXISTS (
    SELECT 1 FROM app.external_evidence_verifications v
    WHERE v.organization_id=p_org AND v.case_id=p_case AND v.case_revision=p_revision
      AND v.decision='approve' AND v.claim='australia_program_fit' AND v.evidence_role='program_fit'
      AND v.baseline_source_pack_id=p_pack AND v.promoted_source_pack_version=p_pack_version
      AND v.baseline_source_pack_version=1
      AND v.baseline_manifest_sha256='84350ea5705d9681d3e6550e1bd06e3340a9fcf0e7e7bbed4478ed3403405f28'
      AND v.baseline_raw_manifest_sha256='5d455d2c409c322e093f3a116387f3cef0fb7ea0f7357fec5e76e9da5b3a2a25'
  ) THEN RAISE EXCEPTION USING ERRCODE='NV011', MESSAGE='governed mixed approval is unavailable'; END IF;
  IF EXISTS (
    SELECT 1 FROM app.agent_tasks t
    WHERE t.organization_id=p_org AND t.case_id=p_case AND t.operation=p_operation
      AND t.case_revision=p_revision AND t.source_pack_id=p_pack
      AND t.source_pack_version=p_pack_version AND t.policy_version=p_policy
      AND t.skill_definition_id=definition.id AND t.skill_version_id=version.id
      AND t.skill_activation_event_id=activation.id
      AND t.skill_activation_sequence=activation.activation_sequence
      AND t.runtime_binding_sha256=version.runtime_binding_sha256
      AND t.state IN ('queued','leased','running','waiting_review','succeeded')
  ) THEN RAISE EXCEPTION USING ERRCODE='NV009', MESSAGE='effective task already exists'; END IF;
  IF starts_planning THEN
    UPDATE app.student_cases AS c
       SET state='planning'
     WHERE c.organization_id=p_org AND c.id=p_case
       AND c.state='intake' AND c.current_revision=p_revision;
    IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='task input is stale'; END IF;
  END IF;
  INSERT INTO app.agent_tasks(
    organization_id,id,case_id,operation,case_revision,source_pack_id,source_pack_version,
    policy_version,request_sha256,created_by_actor_id,state,skill_definition_id,
    skill_version_id,skill_activation_event_id,skill_activation_sequence,runtime_binding_sha256
  ) VALUES(
    p_org,p_task,p_case,p_operation,p_revision,p_pack,p_pack_version,p_policy,p_request_hash,
    p_actor,'queued',definition.id,version.id,activation.id,activation.activation_sequence,
    version.runtime_binding_sha256
  );
  INSERT INTO internal.agent_task_dispatch(task_id,organization_id,available_at) VALUES(p_task,p_org,clock_timestamp());
  PERFORM app.append_agent_task_event(p_org,p_task,'queued','preparing','queued',0,NULL);
  INSERT INTO app.idempotency_records VALUES(p_org,p_actor,'agent_task_create',p_key_hash,p_request_hash,'agent_task',p_task,clock_timestamp());
  SELECT * INTO selected FROM app.agent_tasks WHERE organization_id=p_org AND id=p_task;
  RETURN QUERY SELECT selected.id,selected.row_version,selected.state,selected.attempt_count,false;
END; $$;
"""

# Exact migration 0008 authority restored by downgrade.
_0008_CREATE_TASK_SQL = r"""
CREATE FUNCTION app.create_agent_task(p_org uuid,p_actor uuid,p_case uuid,p_task uuid,p_operation text,p_revision integer,p_pack uuid,p_pack_version integer,p_policy text,p_skill_manifest jsonb,p_request_hash text,p_key_hash text) RETURNS TABLE(task_id uuid,row_version integer,state text,attempt_count integer,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE prior app.idempotency_records%ROWTYPE; selected app.agent_tasks%ROWTYPE; current_case app.student_cases%ROWTYPE; definition app.skill_definitions%ROWTYPE; activation app.skill_activation_events%ROWTYPE; version app.skill_versions%ROWTYPE;
BEGIN
  PERFORM app.assert_m3b_context(p_org,p_actor,'advisor');
  SELECT * INTO prior FROM app.idempotency_records WHERE organization_id=p_org AND actor_id=p_actor AND operation='agent_task_create' AND key_sha256=p_key_hash;
  IF FOUND THEN
    IF prior.request_sha256<>p_request_hash THEN RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='idempotency request mismatch'; END IF;
    SELECT * INTO selected FROM app.agent_tasks WHERE organization_id=p_org AND id=prior.response_id;
    IF selected.operation<>p_operation THEN RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='idempotency operation mismatch'; END IF;
    RETURN QUERY SELECT selected.id,selected.row_version,selected.state,selected.attempt_count,true;
    RETURN;
  END IF;
  IF p_operation NOT IN ('generate_planning_run_v1','generate_governed_mixed_planning_run_v1')
     OR p_policy<>'m3a-policy-v1' OR p_revision<=0 OR p_pack_version<=0
     OR p_request_hash !~ '^[0-9a-f]{64}$' OR p_key_hash !~ '^[0-9a-f]{64}$'
     OR jsonb_typeof(p_skill_manifest)<>'object' THEN
    RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid task pins';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM app.student_case_participants
    WHERE organization_id=p_org AND case_id=p_case AND actor_id=p_actor AND role='advisor'
  ) THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='participant not assigned'; END IF;
  SELECT * INTO definition FROM app.skill_definitions
   WHERE organization_id=p_org AND skill_key='study-destination-compare'
     AND binding_kind='planning_runtime' FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV015', MESSAGE='active Skill version unavailable'; END IF;
  SELECT * INTO activation FROM app.skill_activation_events
   WHERE organization_id=p_org AND definition_id=definition.id
   ORDER BY activation_sequence DESC LIMIT 1;
  IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV015', MESSAGE='active Skill version unavailable'; END IF;
  SELECT * INTO version FROM app.skill_versions
   WHERE organization_id=p_org AND definition_id=definition.id AND id=activation.activated_version_id;
  IF NOT FOUND OR version.binding_kind<>'planning_runtime' OR version.manifest_projection<>p_skill_manifest
     OR version.runtime_binding_sha256 IS NULL THEN
    RAISE EXCEPTION USING ERRCODE='NV022', MESSAGE='Skill runtime pin is invalid';
  END IF;
  SELECT * INTO current_case FROM app.student_cases c
   WHERE c.organization_id=p_org AND c.id=p_case FOR SHARE;
  IF NOT FOUND OR current_case.current_revision<>p_revision OR current_case.state<>'planning'
     OR NOT EXISTS (
       SELECT 1 FROM app.source_packs s
       WHERE s.organization_id=p_org AND s.id=p_pack AND s.version=p_pack_version
     ) THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='task input is stale'; END IF;
  IF p_operation='generate_governed_mixed_planning_run_v1' AND NOT EXISTS (
    SELECT 1 FROM app.external_evidence_verifications v
    WHERE v.organization_id=p_org AND v.case_id=p_case AND v.case_revision=p_revision
      AND v.decision='approve' AND v.claim='australia_program_fit' AND v.evidence_role='program_fit'
      AND v.baseline_source_pack_id=p_pack AND v.promoted_source_pack_version=p_pack_version
      AND v.baseline_source_pack_version=1
      AND v.baseline_manifest_sha256='84350ea5705d9681d3e6550e1bd06e3340a9fcf0e7e7bbed4478ed3403405f28'
      AND v.baseline_raw_manifest_sha256='5d455d2c409c322e093f3a116387f3cef0fb7ea0f7357fec5e76e9da5b3a2a25'
  ) THEN RAISE EXCEPTION USING ERRCODE='NV011', MESSAGE='governed mixed approval is unavailable'; END IF;
  IF EXISTS (
    SELECT 1 FROM app.agent_tasks t
    WHERE t.organization_id=p_org AND t.case_id=p_case AND t.operation=p_operation
      AND t.case_revision=p_revision AND t.source_pack_id=p_pack
      AND t.source_pack_version=p_pack_version AND t.policy_version=p_policy
      AND t.skill_definition_id=definition.id AND t.skill_version_id=version.id
      AND t.skill_activation_event_id=activation.id
      AND t.skill_activation_sequence=activation.activation_sequence
      AND t.runtime_binding_sha256=version.runtime_binding_sha256
      AND t.state IN ('queued','leased','running','waiting_review','succeeded')
  ) THEN RAISE EXCEPTION USING ERRCODE='NV009', MESSAGE='effective task already exists'; END IF;
  INSERT INTO app.agent_tasks(
    organization_id,id,case_id,operation,case_revision,source_pack_id,source_pack_version,
    policy_version,request_sha256,created_by_actor_id,state,skill_definition_id,
    skill_version_id,skill_activation_event_id,skill_activation_sequence,runtime_binding_sha256
  ) VALUES(
    p_org,p_task,p_case,p_operation,p_revision,p_pack,p_pack_version,p_policy,p_request_hash,
    p_actor,'queued',definition.id,version.id,activation.id,activation.activation_sequence,
    version.runtime_binding_sha256
  );
  INSERT INTO internal.agent_task_dispatch(task_id,organization_id,available_at) VALUES(p_task,p_org,clock_timestamp());
  PERFORM app.append_agent_task_event(p_org,p_task,'queued','preparing','queued',0,NULL);
  INSERT INTO app.idempotency_records VALUES(p_org,p_actor,'agent_task_create',p_key_hash,p_request_hash,'agent_task',p_task,clock_timestamp());
  SELECT * INTO selected FROM app.agent_tasks WHERE organization_id=p_org AND id=p_task;
  RETURN QUERY SELECT selected.id,selected.row_version,selected.state,selected.attempt_count,false;
END; $$;
"""


def _execute(sql: str) -> None:
    op.execute(sql.strip())


def _replace(function_sql: str) -> None:
    op.execute(f"DROP FUNCTION {CREATE_TASK_SIGNATURE}")
    _execute(function_sql)
    op.execute(REVOKE_TASK_SQL)
    op.execute(GRANT_TASK_SQL)


def upgrade() -> None:
    _replace(CREATE_TASK_SQL)
    op.execute(REVOKE_TRANSITION_PUBLIC_SQL)
    op.execute(REVOKE_TRANSITION_API_SQL)


def downgrade() -> None:
    _replace(_0008_CREATE_TASK_SQL)
    op.execute(REVOKE_TRANSITION_PUBLIC_SQL)
    op.execute(GRANT_TRANSITION_API_SQL)
