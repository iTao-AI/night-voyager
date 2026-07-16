# ruff: noqa: E501
"""Add the governed mixed planning operation and worker snapshot authority."""

from collections.abc import Sequence

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CREATE_TASK_SQL = r"""
CREATE FUNCTION app.create_agent_task(p_org uuid,p_actor uuid,p_case uuid,p_task uuid,p_operation text,p_revision integer,p_pack uuid,p_pack_version integer,p_policy text,p_request_hash text,p_key_hash text) RETURNS TABLE(task_id uuid,row_version integer,state text,attempt_count integer,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE prior app.idempotency_records%ROWTYPE; selected app.agent_tasks%ROWTYPE; current_case app.student_cases%ROWTYPE;
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
  IF p_operation NOT IN ('generate_planning_run_v1','generate_governed_mixed_planning_run_v1') OR p_policy<>'m3a-policy-v1' OR p_revision<=0 OR p_pack_version<=0 OR p_request_hash !~ '^[0-9a-f]{64}$' OR p_key_hash !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid task pins'; END IF;
  IF NOT EXISTS (SELECT 1 FROM app.student_case_participants WHERE organization_id=p_org AND case_id=p_case AND actor_id=p_actor AND role='advisor') THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='participant not assigned'; END IF;
  SELECT * INTO current_case FROM app.student_cases c WHERE c.organization_id=p_org AND c.id=p_case FOR SHARE;
  IF NOT FOUND OR current_case.current_revision<>p_revision OR current_case.state<>'planning' OR NOT EXISTS (SELECT 1 FROM app.source_packs s WHERE s.organization_id=p_org AND s.id=p_pack AND s.version=p_pack_version) THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='task input is stale'; END IF;
  IF p_operation='generate_governed_mixed_planning_run_v1' AND NOT EXISTS (
    SELECT 1 FROM app.external_evidence_verifications v
    WHERE v.organization_id=p_org AND v.case_id=p_case AND v.case_revision=p_revision
      AND v.decision='approve' AND v.claim='australia_program_fit' AND v.evidence_role='program_fit'
      AND v.baseline_source_pack_id=p_pack AND v.promoted_source_pack_version=p_pack_version
      AND v.baseline_source_pack_version=1
      AND v.baseline_manifest_sha256='84350ea5705d9681d3e6550e1bd06e3340a9fcf0e7e7bbed4478ed3403405f28'
      AND v.baseline_raw_manifest_sha256='5d455d2c409c322e093f3a116387f3cef0fb7ea0f7357fec5e76e9da5b3a2a25'
  ) THEN RAISE EXCEPTION USING ERRCODE='NV011', MESSAGE='governed mixed approval is unavailable'; END IF;
  IF EXISTS (SELECT 1 FROM app.agent_tasks t WHERE t.organization_id=p_org AND t.case_id=p_case AND t.operation=p_operation AND t.case_revision=p_revision AND t.source_pack_id=p_pack AND t.source_pack_version=p_pack_version AND t.policy_version=p_policy AND t.state IN ('queued','leased','running','waiting_review','succeeded')) THEN RAISE EXCEPTION USING ERRCODE='NV009', MESSAGE='effective task already exists'; END IF;
  INSERT INTO app.agent_tasks(organization_id,id,case_id,operation,case_revision,source_pack_id,source_pack_version,policy_version,request_sha256,created_by_actor_id,state) VALUES(p_org,p_task,p_case,p_operation,p_revision,p_pack,p_pack_version,p_policy,p_request_hash,p_actor,'queued');
  INSERT INTO internal.agent_task_dispatch(task_id,organization_id,available_at) VALUES(p_task,p_org,clock_timestamp());
  PERFORM app.append_agent_task_event(p_org,p_task,'queued','preparing','queued',0,NULL);
  INSERT INTO app.idempotency_records VALUES(p_org,p_actor,'agent_task_create',p_key_hash,p_request_hash,'agent_task',p_task,clock_timestamp());
  SELECT * INTO selected FROM app.agent_tasks WHERE organization_id=p_org AND id=p_task;
  RETURN QUERY SELECT selected.id,selected.row_version,selected.state,selected.attempt_count,false;
END; $$
"""

CLAIM_TASK_SQL = r"""
CREATE FUNCTION app.claim_agent_task(p_worker text) RETURNS TABLE(task_id uuid,organization_id uuid,lease_generation bigint) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE candidate record; selected app.agent_tasks%ROWTYPE; reclaimed boolean := false; next_attempt integer; next_generation bigint; new_expiry timestamptz; selected_adapter text; selected_adapter_version text;
BEGIN
  IF NULLIF(btrim(p_worker),'') IS NULL OR length(p_worker)>200 THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid worker identity'; END IF;
  SELECT d.task_id,d.organization_id INTO candidate FROM internal.agent_task_dispatch d WHERE d.available_at<=clock_timestamp() ORDER BY d.available_at,d.task_id FOR UPDATE SKIP LOCKED LIMIT 1;
  IF NOT FOUND THEN RETURN; END IF;
  PERFORM set_config('night_voyager.organization_id',candidate.organization_id::text,true);
  SELECT * INTO selected FROM app.agent_tasks t WHERE t.organization_id=candidate.organization_id AND t.id=candidate.task_id FOR UPDATE;
  IF NOT FOUND OR selected.state IN ('waiting_review','succeeded','blocked','timed_out','failed','cancelled') THEN DELETE FROM internal.agent_task_dispatch d WHERE d.organization_id=candidate.organization_id AND d.task_id=candidate.task_id; RETURN; END IF;
  IF selected.state IN ('leased','running') THEN
    IF selected.lease_expires_at>clock_timestamp() THEN UPDATE internal.agent_task_dispatch d SET available_at=selected.lease_expires_at WHERE d.organization_id=candidate.organization_id AND d.task_id=candidate.task_id; RETURN; END IF;
    reclaimed := true;
    IF selected.attempt_count>=3 THEN
      UPDATE app.agent_executions e SET status='failed',retryable=false,public_code='lease_expired',duration_ms=GREATEST(0,floor(extract(epoch FROM (clock_timestamp()-COALESCE(e.started_at,e.created_at)))*1000)::integer),finished_at=clock_timestamp() WHERE e.organization_id=selected.organization_id AND e.task_id=selected.id AND e.lease_generation=selected.lease_generation AND e.status IN ('leased','running');
      UPDATE app.agent_tasks t SET state='failed',row_version=t.row_version+1,lease_owner=NULL,lease_expires_at=NULL,terminal_code='lease_expired',updated_at=clock_timestamp() WHERE t.organization_id=selected.organization_id AND t.id=selected.id;
      DELETE FROM internal.agent_task_dispatch d WHERE d.organization_id=selected.organization_id AND d.task_id=selected.id;
      PERFORM app.append_agent_task_event(selected.organization_id,selected.id,'failed','failed','lease_expired',selected.attempt_count,NULL); RETURN;
    END IF;
    UPDATE app.agent_executions e SET status='retry_scheduled',retryable=true,public_code='lease_expired',duration_ms=GREATEST(0,floor(extract(epoch FROM (clock_timestamp()-COALESCE(e.started_at,e.created_at)))*1000)::integer),finished_at=clock_timestamp() WHERE e.organization_id=selected.organization_id AND e.task_id=selected.id AND e.lease_generation=selected.lease_generation AND e.status IN ('leased','running');
  ELSIF selected.state<>'queued' THEN RETURN; END IF;
  next_attempt := selected.attempt_count+1; next_generation := selected.lease_generation+1; new_expiry := clock_timestamp()+interval '60 seconds';
  selected_adapter := CASE selected.operation WHEN 'generate_planning_run_v1' THEN 'deterministic_planning' WHEN 'generate_governed_mixed_planning_run_v1' THEN 'governed_mixed_planning' ELSE NULL END;
  selected_adapter_version := CASE selected.operation WHEN 'generate_planning_run_v1' THEN 'm4a-v1' WHEN 'generate_governed_mixed_planning_run_v1' THEN 'dra-mixed-v1' ELSE NULL END;
  IF selected_adapter IS NULL THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid task operation'; END IF;
  UPDATE app.agent_tasks t SET state='leased',row_version=t.row_version+1,attempt_count=next_attempt,lease_owner=p_worker,lease_generation=next_generation,lease_expires_at=new_expiry,terminal_code=NULL,updated_at=clock_timestamp() WHERE t.organization_id=selected.organization_id AND t.id=selected.id;
  UPDATE internal.agent_task_dispatch d SET available_at=new_expiry WHERE d.organization_id=selected.organization_id AND d.task_id=selected.id;
  INSERT INTO app.agent_executions(organization_id,id,task_id,attempt_no,lease_generation,adapter_id,adapter_version,status,cost_status) VALUES(selected.organization_id,gen_random_uuid(),selected.id,next_attempt,next_generation,selected_adapter,selected_adapter_version,'leased','not_applicable');
  IF reclaimed THEN PERFORM app.append_agent_task_event(selected.organization_id,selected.id,'lease_reclaimed','preparing','lease_expired',next_attempt,NULL); END IF;
  PERFORM app.append_agent_task_event(selected.organization_id,selected.id,'lease_acquired','preparing','lease_acquired',next_attempt,NULL);
  RETURN QUERY SELECT selected.id,selected.organization_id,next_generation;
END; $$
"""

SNAPSHOT_SQL = r"""
CREATE FUNCTION app.load_governed_mixed_planning_snapshot(p_org uuid,p_case uuid,p_revision integer,p_pack uuid,p_pack_version integer,p_policy text) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE selected_case app.student_cases%ROWTYPE; selected_revision app.student_case_revisions%ROWTYPE; verification app.external_evidence_verifications%ROWTYPE; pack app.source_packs%ROWTYPE; entries jsonb; evidence jsonb; invalid_count integer;
BEGIN
  PERFORM app.assert_context(p_org);
  IF p_policy<>'m3a-policy-v1' OR p_revision<=0 OR p_pack_version<=1 THEN RAISE EXCEPTION USING ERRCODE='NV011', MESSAGE='governed mixed snapshot pins are invalid'; END IF;
  SELECT * INTO selected_case FROM app.student_cases c WHERE c.organization_id=p_org AND c.id=p_case FOR SHARE;
  IF NOT FOUND OR selected_case.current_revision<>p_revision OR selected_case.state<>'planning' THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='governed mixed Case is stale'; END IF;
  SELECT * INTO selected_revision FROM app.student_case_revisions r WHERE r.organization_id=p_org AND r.case_id=p_case AND r.revision=p_revision;
  SELECT * INTO pack FROM app.source_packs s WHERE s.organization_id=p_org AND s.id=p_pack AND s.version=p_pack_version;
  IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV011', MESSAGE='governed mixed source pack is unavailable'; END IF;
  SELECT * INTO verification FROM app.external_evidence_verifications v WHERE v.organization_id=p_org AND v.case_id=p_case AND v.case_revision=p_revision AND v.decision='approve' AND v.claim='australia_program_fit' AND v.evidence_role='program_fit' AND v.baseline_source_pack_id=p_pack AND v.baseline_source_pack_version=1 AND v.promoted_source_pack_version=p_pack_version;
  IF NOT FOUND OR verification.baseline_manifest_sha256<>'84350ea5705d9681d3e6550e1bd06e3340a9fcf0e7e7bbed4478ed3403405f28' OR verification.baseline_raw_manifest_sha256<>'5d455d2c409c322e093f3a116387f3cef0fb7ea0f7357fec5e76e9da5b3a2a25' THEN RAISE EXCEPTION USING ERRCODE='NV011', MESSAGE='governed mixed verification is unavailable'; END IF;
  SELECT count(*) INTO invalid_count FROM app.evidence_refs e LEFT JOIN app.source_pack_entries s ON (s.organization_id,s.source_pack_id,s.source_pack_version,s.id)=(e.organization_id,e.source_pack_id,e.source_pack_version,e.source_entry_id) WHERE e.organization_id=p_org AND e.source_pack_id=p_pack AND e.source_pack_version=p_pack_version AND (s.id IS NULL OR s.sha256<>e.source_sha256 OR NOT (s.coverage ? e.claim));
  IF invalid_count<>0 THEN RAISE EXCEPTION USING ERRCODE='NV011', MESSAGE='governed mixed Evidence provenance is invalid'; END IF;
  SELECT count(*) INTO invalid_count FROM app.evidence_refs e WHERE e.organization_id=p_org AND e.source_pack_id=p_pack AND e.source_pack_version=p_pack_version AND ((e.claim='australia_program_fit' AND (e.authority<>'externally_verified' OR e.id<>verification.promoted_evidence_id OR e.source_entry_id<>verification.promoted_source_entry_id OR e.source_sha256<>verification.source_sha256)) OR (e.claim<>'australia_program_fit' AND e.authority<>'accepted_synthetic_demo'));
  IF invalid_count<>0 OR (SELECT count(*) FROM app.evidence_refs e WHERE e.organization_id=p_org AND e.source_pack_id=p_pack AND e.source_pack_version=p_pack_version)<>6 OR (SELECT count(DISTINCT e.claim) FROM app.evidence_refs e WHERE e.organization_id=p_org AND e.source_pack_id=p_pack AND e.source_pack_version=p_pack_version AND e.claim IN ('australia_program_fit','australia_tuition','australia_living_cost','australia_fx','japan_program_fit','australia_ranking'))<>6 THEN RAISE EXCEPTION USING ERRCODE='NV011', MESSAGE='governed mixed Evidence authority is invalid'; END IF;
  IF NOT EXISTS (SELECT 1 FROM app.source_pack_entries s WHERE s.organization_id=p_org AND s.source_pack_id=p_pack AND s.source_pack_version=p_pack_version AND s.id='51000000-0000-0000-0000-000000000001' AND s.declared_path='sources/australia.txt' AND s.sha256='ec5c5ae9dd8b7575dac15f8e4fcfb1332be2832a0f773a5c4fcd690638038cce' AND s.publisher='Synthetic Demo Publisher' AND s.institution='Synthetic Australia Institution' AND s.coverage='["australia_tuition","australia_living_cost","australia_fx","australia_ranking"]'::jsonb)
     OR NOT EXISTS (SELECT 1 FROM app.source_pack_entries s WHERE s.organization_id=p_org AND s.source_pack_id=p_pack AND s.source_pack_version=p_pack_version AND s.id='51000000-0000-0000-0000-000000000002' AND s.declared_path='sources/japan.txt' AND s.sha256='02aaaf05433d55389d95ba22a18f5dd1c05b59d318ca10e83f7f2485115ba92a' AND s.coverage='["japan_program_fit"]'::jsonb)
     OR NOT EXISTS (SELECT 1 FROM app.source_pack_entries s WHERE s.organization_id=p_org AND s.source_pack_id=p_pack AND s.source_pack_version=p_pack_version AND s.id='51000000-0000-0000-0000-000000000003' AND s.declared_path='sources/malaysia.txt' AND s.sha256='6c9c0de61110663cba5af542c571bda26791e029f98267790f1065a9ed707179' AND s.coverage='["malaysia_context"]'::jsonb)
     OR NOT EXISTS (SELECT 1 FROM app.source_pack_entries s WHERE s.organization_id=p_org AND s.source_pack_id=p_pack AND s.source_pack_version=p_pack_version AND s.id=verification.promoted_source_entry_id AND s.sha256=verification.source_sha256 AND s.coverage='["australia_program_fit"]'::jsonb AND s.redistribution_class='link_only' AND s.canonical_url=verification.source_url) THEN RAISE EXCEPTION USING ERRCODE='NV011', MESSAGE='governed mixed source baseline is invalid'; END IF;
  IF (SELECT count(*) FROM app.source_pack_entries s WHERE s.organization_id=p_org AND s.source_pack_id=p_pack AND s.source_pack_version=p_pack_version)<>4 THEN RAISE EXCEPTION USING ERRCODE='NV011', MESSAGE='governed mixed source entry cardinality is invalid'; END IF;
  SELECT jsonb_agg(jsonb_build_object('schema_version',1,'entry_id',s.id,'path',s.declared_path,'sha256',s.sha256,'snapshot_date',s.snapshot_date,'publisher',s.publisher,'institution',s.institution,'canonical_url',s.canonical_url,'freshness_days',s.freshness_days,'redistribution_class',s.redistribution_class,'evidence_class',s.evidence_class,'coverage',s.coverage,'known_gaps',s.known_gaps) ORDER BY s.id) INTO entries FROM app.source_pack_entries s WHERE s.organization_id=p_org AND s.source_pack_id=p_pack AND s.source_pack_version=p_pack_version;
  SELECT jsonb_agg(jsonb_build_object('schema_version',1,'organization_id',e.organization_id,'evidence_id',e.id,'claim',e.claim,'source_pack_id',e.source_pack_id,'source_pack_version',e.source_pack_version,'source_entry_id',e.source_entry_id,'source_sha256',e.source_sha256,'authority',e.authority) ORDER BY e.claim) INTO evidence FROM app.evidence_refs e WHERE e.organization_id=p_org AND e.source_pack_id=p_pack AND e.source_pack_version=p_pack_version;
  RETURN jsonb_build_object('schema_version',1,'organization_id',p_org,'case',jsonb_build_object('schema_version',1,'organization_id',p_org,'case_id',p_case,'revision',p_revision,'student',selected_revision.student_preferences,'family',selected_revision.family_preferences),'source_pack',jsonb_build_object('schema_version',1,'organization_id',p_org,'pack_id',p_pack,'version',p_pack_version,'entries',entries),'evidence',evidence,'verification_decision','approve','verification_claim','australia_program_fit','verification_evidence_role','program_fit','baseline_source_pack_id',verification.baseline_source_pack_id,'baseline_source_pack_version',verification.baseline_source_pack_version,'baseline_manifest_sha256',verification.baseline_manifest_sha256,'baseline_raw_manifest_sha256',verification.baseline_raw_manifest_sha256,'promoted_source_pack_version',verification.promoted_source_pack_version,'promoted_source_entry_id',verification.promoted_source_entry_id,'promoted_evidence_id',verification.promoted_evidence_id);
END; $$
"""

OLD_CREATE_TASK_SQL = CREATE_TASK_SQL.replace(
    "p_task uuid,p_operation text,p_revision", "p_task uuid,p_revision"
).replace(
    "    IF selected.operation<>p_operation THEN RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='idempotency operation mismatch'; END IF;\n",
    "",
).replace(
    "p_operation NOT IN ('generate_planning_run_v1','generate_governed_mixed_planning_run_v1') OR ",
    "",
).replace(
    "  SELECT * INTO current_case FROM app.student_cases c WHERE c.organization_id=p_org AND c.id=p_case FOR SHARE;\n  IF NOT FOUND OR current_case.current_revision<>p_revision OR current_case.state<>'planning' OR",
    "  IF NOT EXISTS (SELECT 1 FROM app.student_cases c WHERE c.organization_id=p_org AND c.id=p_case AND c.current_revision=p_revision AND c.state='planning') OR",
).replace(
    "  IF p_operation='generate_governed_mixed_planning_run_v1' AND NOT EXISTS (\n    SELECT 1 FROM app.external_evidence_verifications v\n    WHERE v.organization_id=p_org AND v.case_id=p_case AND v.case_revision=p_revision\n      AND v.decision='approve' AND v.claim='australia_program_fit' AND v.evidence_role='program_fit'\n      AND v.baseline_source_pack_id=p_pack AND v.promoted_source_pack_version=p_pack_version\n      AND v.baseline_source_pack_version=1\n      AND v.baseline_manifest_sha256='84350ea5705d9681d3e6550e1bd06e3340a9fcf0e7e7bbed4478ed3403405f28'\n      AND v.baseline_raw_manifest_sha256='5d455d2c409c322e093f3a116387f3cef0fb7ea0f7357fec5e76e9da5b3a2a25'\n  ) THEN RAISE EXCEPTION USING ERRCODE='NV011', MESSAGE='governed mixed approval is unavailable'; END IF;\n",
    "",
).replace("t.operation=p_operation", "t.operation='generate_planning_run_v1'").replace(
    "VALUES(p_org,p_task,p_case,p_operation,p_revision", "VALUES(p_org,p_task,p_case,'generate_planning_run_v1',p_revision"
)

OLD_CLAIM_TASK_SQL = CLAIM_TASK_SQL.replace(
    "; selected_adapter text; selected_adapter_version text", ""
).replace(
    "  selected_adapter := CASE selected.operation WHEN 'generate_planning_run_v1' THEN 'deterministic_planning' WHEN 'generate_governed_mixed_planning_run_v1' THEN 'governed_mixed_planning' ELSE NULL END;\n  selected_adapter_version := CASE selected.operation WHEN 'generate_planning_run_v1' THEN 'm4a-v1' WHEN 'generate_governed_mixed_planning_run_v1' THEN 'dra-mixed-v1' ELSE NULL END;\n  IF selected_adapter IS NULL THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid task operation'; END IF;\n",
    "",
).replace(
    "selected_adapter,selected_adapter_version,'leased'",
    "'deterministic_planning','m4a-v1','leased'",
).replace(
    "IF NOT FOUND OR selected.state IN ('waiting_review'",
    "IF NOT FOUND OR selected.operation<>'generate_planning_run_v1' OR selected.state IN ('waiting_review'",
)

FREEZE_NONTERMINAL_MIXED_TASKS_SQL = r"""
DO $$
DECLARE candidate record; selected record;
BEGIN
  FOR candidate IN
    SELECT d.organization_id,d.task_id
    FROM internal.agent_task_dispatch d
    ORDER BY d.organization_id,d.task_id
    FOR UPDATE
  LOOP
    PERFORM set_config('night_voyager.organization_id',candidate.organization_id::text,true);
    SELECT t.organization_id,t.id,t.attempt_count,t.lease_generation INTO selected
    FROM app.agent_tasks t
    WHERE t.organization_id=candidate.organization_id AND t.id=candidate.task_id
      AND t.operation='generate_governed_mixed_planning_run_v1'
      AND t.state IN ('queued','leased','running')
    FOR UPDATE;
    CONTINUE WHEN NOT FOUND;
    UPDATE app.agent_executions e
    SET status='cancelled',retryable=false,public_code='migration_downgrade',
        duration_ms=GREATEST(0,floor(extract(epoch FROM (clock_timestamp()-COALESCE(e.started_at,e.created_at)))*1000)::integer),
        finished_at=clock_timestamp()
    WHERE e.organization_id=selected.organization_id AND e.task_id=selected.id
      AND e.lease_generation=selected.lease_generation AND e.status IN ('leased','running');
    UPDATE app.agent_tasks t
    SET state='cancelled',row_version=t.row_version+1,lease_owner=NULL,
        lease_expires_at=NULL,terminal_code='migration_downgrade',updated_at=clock_timestamp()
    WHERE t.organization_id=selected.organization_id AND t.id=selected.id;
    DELETE FROM internal.agent_task_dispatch d
    WHERE d.organization_id=selected.organization_id AND d.task_id=selected.id;
    PERFORM app.append_agent_task_event(
      selected.organization_id,selected.id,'cancelled','cancelled',
      'migration_downgrade',selected.attempt_count,NULL
    );
  END LOOP;
END; $$;
"""


def _execute(sql: str) -> None:
    op.execute(sql.strip())


def upgrade() -> None:
    op.execute("DROP FUNCTION app.create_agent_task(uuid,uuid,uuid,uuid,integer,uuid,integer,text,text,text)")
    op.execute("DROP FUNCTION app.claim_agent_task(text)")
    op.execute("ALTER TABLE app.agent_tasks DROP CONSTRAINT agent_tasks_operation_check")
    op.execute("ALTER TABLE app.agent_tasks ADD CONSTRAINT agent_tasks_operation_check CHECK (operation IN ('generate_planning_run_v1','generate_governed_mixed_planning_run_v1'))")
    op.execute("ALTER TABLE app.agent_executions DROP CONSTRAINT agent_executions_adapter_id_check")
    op.execute("ALTER TABLE app.agent_executions DROP CONSTRAINT agent_executions_adapter_version_check")
    op.execute("ALTER TABLE app.agent_executions ADD CONSTRAINT agent_executions_adapter_pair_check CHECK ((adapter_id='deterministic_planning' AND adapter_version='m4a-v1') OR (adapter_id='governed_mixed_planning' AND adapter_version='dra-mixed-v1'))")
    _execute(CREATE_TASK_SQL)
    _execute(CLAIM_TASK_SQL)
    _execute(SNAPSHOT_SQL)
    op.execute("REVOKE ALL ON FUNCTION app.create_agent_task(uuid,uuid,uuid,uuid,text,integer,uuid,integer,text,text,text) FROM PUBLIC")
    op.execute("REVOKE ALL ON FUNCTION app.claim_agent_task(text) FROM PUBLIC")
    op.execute("REVOKE ALL ON FUNCTION app.load_governed_mixed_planning_snapshot(uuid,uuid,integer,uuid,integer,text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.create_agent_task(uuid,uuid,uuid,uuid,text,integer,uuid,integer,text,text,text) TO night_voyager_api")
    op.execute("GRANT EXECUTE ON FUNCTION app.claim_agent_task(text) TO night_voyager_worker")
    op.execute("GRANT EXECUTE ON FUNCTION app.load_governed_mixed_planning_snapshot(uuid,uuid,integer,uuid,integer,text) TO night_voyager_worker")


def downgrade() -> None:
    op.execute("DROP FUNCTION app.load_governed_mixed_planning_snapshot(uuid,uuid,integer,uuid,integer,text)")
    op.execute("DROP FUNCTION app.create_agent_task(uuid,uuid,uuid,uuid,text,integer,uuid,integer,text,text,text)")
    op.execute("DROP FUNCTION app.claim_agent_task(text)")
    _execute(FREEZE_NONTERMINAL_MIXED_TASKS_SQL)
    op.execute("ALTER TABLE app.agent_tasks DROP CONSTRAINT agent_tasks_operation_check")
    op.execute("ALTER TABLE app.agent_tasks ADD CONSTRAINT agent_tasks_operation_check CHECK (operation = 'generate_planning_run_v1') NOT VALID")
    op.execute("ALTER TABLE app.agent_executions DROP CONSTRAINT agent_executions_adapter_pair_check")
    op.execute("ALTER TABLE app.agent_executions ADD CONSTRAINT agent_executions_adapter_id_check CHECK (adapter_id = 'deterministic_planning') NOT VALID")
    op.execute("ALTER TABLE app.agent_executions ADD CONSTRAINT agent_executions_adapter_version_check CHECK (adapter_version = 'm4a-v1') NOT VALID")
    _execute(OLD_CREATE_TASK_SQL)
    _execute(OLD_CLAIM_TASK_SQL)
    op.execute("REVOKE ALL ON FUNCTION app.create_agent_task(uuid,uuid,uuid,uuid,integer,uuid,integer,text,text,text) FROM PUBLIC")
    op.execute("REVOKE ALL ON FUNCTION app.claim_agent_task(text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.create_agent_task(uuid,uuid,uuid,uuid,integer,uuid,integer,text,text,text) TO night_voyager_api")
    op.execute("GRANT EXECUTE ON FUNCTION app.claim_agent_task(text) TO night_voyager_worker")
