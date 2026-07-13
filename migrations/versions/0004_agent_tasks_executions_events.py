# ruff: noqa: E501
"""Create durable AgentTask, execution, event, lease, and dispatch authority."""

from collections.abc import Sequence

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("agent_tasks", "agent_executions", "agent_task_events")

UPGRADE_SQL = r"""
CREATE SCHEMA internal AUTHORIZATION night_voyager_migrator;
REVOKE ALL ON SCHEMA internal FROM PUBLIC;

CREATE TABLE app.agent_tasks (
  organization_id uuid NOT NULL,
  id uuid NOT NULL,
  case_id uuid NOT NULL,
  operation text NOT NULL CHECK (operation = 'generate_planning_run_v1'),
  case_revision integer NOT NULL CHECK (case_revision > 0),
  source_pack_id uuid NOT NULL,
  source_pack_version integer NOT NULL CHECK (source_pack_version > 0),
  policy_version text NOT NULL CHECK (policy_version = 'm3a-policy-v1'),
  request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
  created_by_actor_id uuid NOT NULL,
  row_version integer NOT NULL DEFAULT 1 CHECK (row_version > 0),
  state text NOT NULL CHECK (state IN ('queued','leased','running','waiting_review','succeeded','blocked','timed_out','failed','cancelled')),
  attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count BETWEEN 0 AND 3),
  lease_owner text,
  lease_generation bigint NOT NULL DEFAULT 0 CHECK (lease_generation >= 0),
  lease_expires_at timestamptz,
  result_planning_run_id uuid,
  terminal_code text,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id, id),
  FOREIGN KEY (organization_id, case_id, case_revision) REFERENCES app.student_case_revisions(organization_id, case_id, revision),
  FOREIGN KEY (organization_id, source_pack_id, source_pack_version) REFERENCES app.source_packs(organization_id, id, version),
  FOREIGN KEY (organization_id, created_by_actor_id) REFERENCES app.actors(organization_id, id),
  FOREIGN KEY (organization_id, result_planning_run_id) REFERENCES app.planning_runs(organization_id, id),
  CHECK ((state IN ('leased','running')) = (lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL))
);
CREATE UNIQUE INDEX agent_tasks_one_effective_operation ON app.agent_tasks(
  organization_id, case_id, operation, case_revision, source_pack_id, source_pack_version, policy_version
) WHERE state IN ('queued','leased','running','waiting_review','succeeded');
CREATE INDEX agent_tasks_case_read_idx ON app.agent_tasks(organization_id, case_id, created_at);

CREATE TABLE app.agent_executions (
  organization_id uuid NOT NULL,
  id uuid NOT NULL,
  task_id uuid NOT NULL,
  attempt_no integer NOT NULL CHECK (attempt_no BETWEEN 1 AND 3),
  lease_generation bigint NOT NULL CHECK (lease_generation > 0),
  adapter_id text NOT NULL CHECK (adapter_id = 'deterministic_planning'),
  adapter_version text NOT NULL CHECK (adapter_version = 'm4a-v1'),
  status text NOT NULL CHECK (status IN ('leased','running','succeeded','retry_scheduled','blocked','timed_out','failed','cancelled','discarded')),
  retryable boolean NOT NULL DEFAULT false,
  fallback_used boolean NOT NULL DEFAULT false,
  input_sha256 text CHECK (input_sha256 ~ '^[0-9a-f]{64}$'),
  output_sha256 text CHECK (output_sha256 ~ '^[0-9a-f]{64}$'),
  result_planning_run_id uuid,
  public_code text,
  duration_ms integer CHECK (duration_ms IS NULL OR duration_ms >= 0),
  cost_status text CHECK (cost_status IS NULL OR cost_status IN ('not_applicable','recorded')),
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id, id),
  UNIQUE (organization_id, task_id, attempt_no),
  UNIQUE (organization_id, task_id, lease_generation),
  FOREIGN KEY (organization_id, task_id) REFERENCES app.agent_tasks(organization_id, id),
  FOREIGN KEY (organization_id, result_planning_run_id) REFERENCES app.planning_runs(organization_id, id)
);

CREATE TABLE app.agent_task_events (
  organization_id uuid NOT NULL,
  task_id uuid NOT NULL,
  event_sequence bigint NOT NULL CHECK (event_sequence > 0),
  event_code text NOT NULL CHECK (event_code IN ('queued','lease_acquired','execution_started','retry_scheduled','lease_reclaimed','waiting_review','succeeded','blocked','timed_out','failed','cancelled')),
  public_status text NOT NULL CHECK (public_status IN ('preparing','needs_advisor_review','ready','needs_evidence','timed_out','failed','cancelled','outdated')),
  public_code text,
  attempt_no integer NOT NULL CHECK (attempt_no BETWEEN 0 AND 3),
  result_planning_run_id uuid,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id, task_id, event_sequence),
  FOREIGN KEY (organization_id, task_id) REFERENCES app.agent_tasks(organization_id, id),
  FOREIGN KEY (organization_id, result_planning_run_id) REFERENCES app.planning_runs(organization_id, id)
);

CREATE TABLE internal.agent_task_dispatch (
  task_id uuid NOT NULL,
  organization_id uuid NOT NULL,
  available_at timestamptz NOT NULL,
  PRIMARY KEY (task_id, organization_id),
  FOREIGN KEY (organization_id, task_id) REFERENCES app.agent_tasks(organization_id, id)
);
REVOKE ALL ON TABLE internal.agent_task_dispatch FROM PUBLIC;
REVOKE ALL ON TABLE internal.agent_task_dispatch FROM night_voyager_api;
REVOKE ALL ON TABLE internal.agent_task_dispatch FROM night_voyager_worker;

ALTER TABLE app.agent_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.agent_tasks FORCE ROW LEVEL SECURITY;
CREATE POLICY agent_tasks_tenant_isolation ON app.agent_tasks USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid) WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);
ALTER TABLE app.agent_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.agent_executions FORCE ROW LEVEL SECURITY;
CREATE POLICY agent_executions_tenant_isolation ON app.agent_executions USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid) WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);
ALTER TABLE app.agent_task_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.agent_task_events FORCE ROW LEVEL SECURITY;
CREATE POLICY agent_task_events_tenant_isolation ON app.agent_task_events USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid) WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);

CREATE FUNCTION app.reject_agent_task_event_mutation() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='durable task event is immutable';
END; $$;
CREATE TRIGGER agent_task_events_immutable BEFORE UPDATE OR DELETE ON app.agent_task_events FOR EACH ROW EXECUTE FUNCTION app.reject_agent_task_event_mutation();

CREATE FUNCTION app.append_agent_task_event(p_org uuid,p_task uuid,p_event text,p_status text,p_code text,p_attempt integer,p_result uuid) RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE next_sequence bigint;
BEGIN
  SELECT COALESCE(max(event_sequence),0)+1 INTO next_sequence FROM app.agent_task_events WHERE organization_id=p_org AND task_id=p_task;
  INSERT INTO app.agent_task_events(organization_id,task_id,event_sequence,event_code,public_status,public_code,attempt_no,result_planning_run_id) VALUES(p_org,p_task,next_sequence,p_event,p_status,p_code,p_attempt,p_result);
  RETURN next_sequence;
END; $$;

CREATE FUNCTION app.create_agent_task(p_org uuid,p_actor uuid,p_case uuid,p_task uuid,p_revision integer,p_pack uuid,p_pack_version integer,p_policy text,p_request_hash text,p_key_hash text) RETURNS TABLE(task_id uuid,row_version integer,state text,attempt_count integer,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE prior app.idempotency_records%ROWTYPE; selected app.agent_tasks%ROWTYPE;
BEGIN
  PERFORM app.assert_m3b_context(p_org,p_actor,'advisor');
  SELECT * INTO prior FROM app.idempotency_records WHERE organization_id=p_org AND actor_id=p_actor AND operation='agent_task_create' AND key_sha256=p_key_hash;
  IF FOUND THEN
    IF prior.request_sha256<>p_request_hash THEN RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='idempotency request mismatch'; END IF;
    SELECT * INTO selected FROM app.agent_tasks WHERE organization_id=p_org AND id=prior.response_id;
    RETURN QUERY SELECT selected.id,selected.row_version,selected.state,selected.attempt_count,true;
    RETURN;
  END IF;
  IF p_policy<>'m3a-policy-v1' OR p_revision<=0 OR p_pack_version<=0 OR p_request_hash !~ '^[0-9a-f]{64}$' OR p_key_hash !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid task pins'; END IF;
  IF NOT EXISTS (SELECT 1 FROM app.student_case_participants WHERE organization_id=p_org AND case_id=p_case AND actor_id=p_actor AND role='advisor') THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='participant not assigned'; END IF;
  IF NOT EXISTS (SELECT 1 FROM app.student_cases c WHERE c.organization_id=p_org AND c.id=p_case AND c.current_revision=p_revision AND c.state='planning') OR NOT EXISTS (SELECT 1 FROM app.source_packs s WHERE s.organization_id=p_org AND s.id=p_pack AND s.version=p_pack_version) THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='task input is stale'; END IF;
  IF EXISTS (SELECT 1 FROM app.agent_tasks t WHERE t.organization_id=p_org AND t.case_id=p_case AND t.operation='generate_planning_run_v1' AND t.case_revision=p_revision AND t.source_pack_id=p_pack AND t.source_pack_version=p_pack_version AND t.policy_version=p_policy AND t.state IN ('queued','leased','running','waiting_review','succeeded')) THEN RAISE EXCEPTION USING ERRCODE='NV009', MESSAGE='effective task already exists'; END IF;
  INSERT INTO app.agent_tasks(organization_id,id,case_id,operation,case_revision,source_pack_id,source_pack_version,policy_version,request_sha256,created_by_actor_id,state) VALUES(p_org,p_task,p_case,'generate_planning_run_v1',p_revision,p_pack,p_pack_version,p_policy,p_request_hash,p_actor,'queued');
  INSERT INTO internal.agent_task_dispatch(task_id,organization_id,available_at) VALUES(p_task,p_org,clock_timestamp());
  PERFORM app.append_agent_task_event(p_org,p_task,'queued','preparing','queued',0,NULL);
  INSERT INTO app.idempotency_records VALUES(p_org,p_actor,'agent_task_create',p_key_hash,p_request_hash,'agent_task',p_task,clock_timestamp());
  SELECT * INTO selected FROM app.agent_tasks WHERE organization_id=p_org AND id=p_task;
  RETURN QUERY SELECT selected.id,selected.row_version,selected.state,selected.attempt_count,false;
END; $$;

CREATE FUNCTION app.cancel_agent_task(p_org uuid,p_actor uuid,p_task uuid,p_expected_version integer,p_request_hash text,p_key_hash text) RETURNS TABLE(task_id uuid,row_version integer,state text,attempt_count integer,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE prior app.idempotency_records%ROWTYPE; selected app.agent_tasks%ROWTYPE;
BEGIN
  PERFORM app.assert_m3b_context(p_org,p_actor,'advisor');
  SELECT * INTO prior FROM app.idempotency_records WHERE organization_id=p_org AND actor_id=p_actor AND operation='agent_task_cancel' AND key_sha256=p_key_hash;
  IF FOUND THEN
    IF prior.request_sha256<>p_request_hash THEN RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='idempotency request mismatch'; END IF;
    SELECT * INTO selected FROM app.agent_tasks WHERE organization_id=p_org AND id=prior.response_id;
    RETURN QUERY SELECT selected.id,selected.row_version,selected.state,selected.attempt_count,true;
    RETURN;
  END IF;
  SELECT t.* INTO selected FROM app.agent_tasks t JOIN app.student_case_participants p ON p.organization_id=t.organization_id AND p.case_id=t.case_id AND p.actor_id=p_actor AND p.role='advisor' WHERE t.organization_id=p_org AND t.id=p_task FOR UPDATE OF t;
  IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='task unavailable'; END IF;
  IF selected.row_version<>p_expected_version OR selected.state NOT IN ('queued','leased','running') THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='task cancel target is stale'; END IF;
  UPDATE app.agent_executions e SET status='cancelled',retryable=false,public_code='cancelled',finished_at=clock_timestamp() WHERE e.organization_id=p_org AND e.task_id=p_task AND e.lease_generation=selected.lease_generation AND e.status IN ('leased','running');
  UPDATE app.agent_tasks t SET state='cancelled',row_version=t.row_version+1,lease_owner=NULL,lease_expires_at=NULL,terminal_code='cancelled',updated_at=clock_timestamp() WHERE t.organization_id=p_org AND t.id=p_task;
  DELETE FROM internal.agent_task_dispatch d WHERE d.organization_id=p_org AND d.task_id=p_task;
  PERFORM app.append_agent_task_event(p_org,p_task,'cancelled','cancelled','cancelled',selected.attempt_count,NULL);
  INSERT INTO app.idempotency_records VALUES(p_org,p_actor,'agent_task_cancel',p_key_hash,p_request_hash,'agent_task',p_task,clock_timestamp());
  SELECT * INTO selected FROM app.agent_tasks WHERE organization_id=p_org AND id=p_task;
  RETURN QUERY SELECT selected.id,selected.row_version,selected.state,selected.attempt_count,false;
END; $$;

CREATE FUNCTION app.claim_agent_task(p_worker text) RETURNS TABLE(task_id uuid,organization_id uuid,lease_generation bigint) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE candidate record; selected app.agent_tasks%ROWTYPE; reclaimed boolean := false; next_attempt integer; next_generation bigint; new_expiry timestamptz;
BEGIN
  IF NULLIF(btrim(p_worker),'') IS NULL OR length(p_worker)>200 THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid worker identity'; END IF;
  SELECT d.task_id,d.organization_id INTO candidate FROM internal.agent_task_dispatch d WHERE d.available_at<=clock_timestamp() ORDER BY d.available_at,d.task_id FOR UPDATE SKIP LOCKED LIMIT 1;
  IF NOT FOUND THEN RETURN; END IF;
  PERFORM set_config('night_voyager.organization_id',candidate.organization_id::text,true);
  SELECT * INTO selected FROM app.agent_tasks t WHERE t.organization_id=candidate.organization_id AND t.id=candidate.task_id FOR UPDATE;
  IF NOT FOUND OR selected.state IN ('waiting_review','succeeded','blocked','timed_out','failed','cancelled') THEN
    DELETE FROM internal.agent_task_dispatch d WHERE d.organization_id=candidate.organization_id AND d.task_id=candidate.task_id;
    RETURN;
  END IF;
  IF selected.state IN ('leased','running') THEN
    IF selected.lease_expires_at>clock_timestamp() THEN
      UPDATE internal.agent_task_dispatch d SET available_at=selected.lease_expires_at WHERE d.organization_id=candidate.organization_id AND d.task_id=candidate.task_id;
      RETURN;
    END IF;
    reclaimed := true;
    UPDATE app.agent_executions e SET status='retry_scheduled',retryable=true,public_code='lease_expired',finished_at=clock_timestamp() WHERE e.organization_id=selected.organization_id AND e.task_id=selected.id AND e.lease_generation=selected.lease_generation AND e.status IN ('leased','running');
    IF selected.attempt_count>=3 THEN
      UPDATE app.agent_tasks t SET state='failed',row_version=t.row_version+1,lease_owner=NULL,lease_expires_at=NULL,terminal_code='lease_expired',updated_at=clock_timestamp() WHERE t.organization_id=selected.organization_id AND t.id=selected.id;
      DELETE FROM internal.agent_task_dispatch d WHERE d.organization_id=selected.organization_id AND d.task_id=selected.id;
      PERFORM app.append_agent_task_event(selected.organization_id,selected.id,'failed','failed','lease_expired',selected.attempt_count,NULL);
      RETURN;
    END IF;
  ELSIF selected.state<>'queued' THEN
    RETURN;
  END IF;
  next_attempt := selected.attempt_count+1;
  next_generation := selected.lease_generation+1;
  new_expiry := clock_timestamp()+interval '60 seconds';
  UPDATE app.agent_tasks t SET state='leased',row_version=t.row_version+1,attempt_count=next_attempt,lease_owner=p_worker,lease_generation=next_generation,lease_expires_at=new_expiry,terminal_code=NULL,updated_at=clock_timestamp() WHERE t.organization_id=selected.organization_id AND t.id=selected.id;
  UPDATE internal.agent_task_dispatch d SET available_at=new_expiry WHERE d.organization_id=selected.organization_id AND d.task_id=selected.id;
  INSERT INTO app.agent_executions(organization_id,id,task_id,attempt_no,lease_generation,adapter_id,adapter_version,status,cost_status) VALUES(selected.organization_id,gen_random_uuid(),selected.id,next_attempt,next_generation,'deterministic_planning','m4a-v1','leased','not_applicable');
  IF reclaimed THEN PERFORM app.append_agent_task_event(selected.organization_id,selected.id,'lease_reclaimed','preparing','lease_expired',next_attempt,NULL); END IF;
  PERFORM app.append_agent_task_event(selected.organization_id,selected.id,'lease_acquired','preparing','lease_acquired',next_attempt,NULL);
  RETURN QUERY SELECT selected.id,selected.organization_id,next_generation;
END; $$;

CREATE FUNCTION app.start_agent_task(p_org uuid,p_task uuid,p_worker text,p_generation bigint) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE selected app.agent_tasks%ROWTYPE;
BEGIN
  PERFORM app.assert_context(p_org);
  SELECT * INTO selected FROM app.agent_tasks WHERE organization_id=p_org AND id=p_task FOR UPDATE;
  IF NOT FOUND OR selected.state<>'leased' OR selected.lease_owner IS DISTINCT FROM p_worker OR selected.lease_generation<>p_generation OR selected.lease_expires_at<=clock_timestamp() THEN RAISE EXCEPTION USING ERRCODE='NV010', MESSAGE='lease generation lost'; END IF;
  UPDATE app.agent_tasks SET state='running',row_version=row_version+1,updated_at=clock_timestamp() WHERE organization_id=p_org AND id=p_task;
  UPDATE app.agent_executions SET status='running',started_at=clock_timestamp() WHERE organization_id=p_org AND task_id=p_task AND lease_generation=p_generation;
  PERFORM app.append_agent_task_event(p_org,p_task,'execution_started','preparing','execution_started',selected.attempt_count,NULL);
END; $$;

CREATE FUNCTION app.heartbeat_agent_task(p_org uuid,p_task uuid,p_worker text,p_generation bigint) RETURNS timestamptz LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE new_expiry timestamptz := clock_timestamp()+interval '60 seconds';
BEGIN
  PERFORM app.assert_context(p_org);
  UPDATE app.agent_tasks SET lease_expires_at=new_expiry,updated_at=clock_timestamp() WHERE organization_id=p_org AND id=p_task AND state IN ('leased','running') AND lease_owner=p_worker AND lease_generation=p_generation AND lease_expires_at>clock_timestamp();
  IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV010', MESSAGE='lease generation lost'; END IF;
  UPDATE internal.agent_task_dispatch SET available_at=new_expiry WHERE organization_id=p_org AND task_id=p_task;
  RETURN new_expiry;
END; $$;

CREATE FUNCTION app.fail_agent_task(p_org uuid,p_task uuid,p_worker text,p_generation bigint,p_code text,p_retryable boolean) RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE selected app.agent_tasks%ROWTYPE; terminal_state text; event_code text; public_status text;
BEGIN
  PERFORM app.assert_context(p_org);
  SELECT * INTO selected FROM app.agent_tasks WHERE organization_id=p_org AND id=p_task FOR UPDATE;
  IF NOT FOUND OR selected.state NOT IN ('leased','running') OR selected.lease_owner IS DISTINCT FROM p_worker OR selected.lease_generation<>p_generation OR selected.lease_expires_at<=clock_timestamp() THEN RAISE EXCEPTION USING ERRCODE='NV010', MESSAGE='lease generation lost'; END IF;
  IF p_retryable AND selected.attempt_count<3 THEN
    UPDATE app.agent_executions SET status='retry_scheduled',retryable=true,public_code=p_code,finished_at=clock_timestamp() WHERE organization_id=p_org AND task_id=p_task AND lease_generation=p_generation;
    UPDATE app.agent_tasks SET state='queued',row_version=row_version+1,lease_owner=NULL,lease_expires_at=NULL,terminal_code=NULL,updated_at=clock_timestamp() WHERE organization_id=p_org AND id=p_task;
    UPDATE internal.agent_task_dispatch SET available_at=clock_timestamp() WHERE organization_id=p_org AND task_id=p_task;
    PERFORM app.append_agent_task_event(p_org,p_task,'retry_scheduled','preparing',p_code,selected.attempt_count,NULL);
    RETURN 'queued';
  END IF;
  terminal_state := CASE WHEN p_code='deadline_exceeded' THEN 'timed_out' WHEN p_code='required_evidence_gap' THEN 'blocked' ELSE 'failed' END;
  event_code := terminal_state;
  public_status := CASE WHEN terminal_state='blocked' THEN 'needs_evidence' ELSE terminal_state END;
  UPDATE app.agent_executions SET status=terminal_state,retryable=false,public_code=p_code,finished_at=clock_timestamp() WHERE organization_id=p_org AND task_id=p_task AND lease_generation=p_generation;
  UPDATE app.agent_tasks SET state=terminal_state,row_version=row_version+1,lease_owner=NULL,lease_expires_at=NULL,terminal_code=p_code,updated_at=clock_timestamp() WHERE organization_id=p_org AND id=p_task;
  DELETE FROM internal.agent_task_dispatch WHERE organization_id=p_org AND task_id=p_task;
  PERFORM app.append_agent_task_event(p_org,p_task,event_code,public_status,p_code,selected.attempt_count,NULL);
  RETURN terminal_state;
END; $$;

CREATE FUNCTION app.finalize_agent_task_result(p_org uuid,p_task uuid,p_worker text,p_generation bigint,p_run uuid,p_evidence_hash text,p_state text,p_reason text,p_output_hash text,p_output jsonb,p_supersedes uuid) RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE selected app.agent_tasks%ROWTYPE; target_state text; target_status text; target_event text;
BEGIN
  PERFORM app.assert_context(p_org);
  SELECT * INTO selected FROM app.agent_tasks WHERE organization_id=p_org AND id=p_task FOR UPDATE;
  IF NOT FOUND OR selected.state NOT IN ('leased','running') OR selected.lease_owner IS DISTINCT FROM p_worker OR selected.lease_generation<>p_generation OR selected.lease_expires_at<=clock_timestamp() THEN RAISE EXCEPTION USING ERRCODE='NV010', MESSAGE='lease generation lost'; END IF;
  IF p_state NOT IN ('review_required','blocked','failed') THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid planning result state'; END IF;
  PERFORM app.persist_planning_result(p_org,p_run,selected.case_id,selected.case_revision,selected.source_pack_id,selected.source_pack_version,selected.policy_version,p_evidence_hash,p_state,p_reason,p_output_hash,p_supersedes,p_output);
  target_state := CASE WHEN p_state='review_required' THEN 'waiting_review' ELSE p_state END;
  target_status := CASE WHEN p_state='review_required' THEN 'needs_advisor_review' WHEN p_state='blocked' THEN 'needs_evidence' ELSE 'failed' END;
  target_event := CASE WHEN p_state='review_required' THEN 'waiting_review' ELSE p_state END;
  UPDATE app.agent_executions SET status=CASE WHEN p_state='review_required' THEN 'succeeded' ELSE p_state END,retryable=false,output_sha256=p_output_hash,result_planning_run_id=p_run,public_code=p_reason,finished_at=clock_timestamp() WHERE organization_id=p_org AND task_id=p_task AND lease_generation=p_generation;
  UPDATE app.agent_tasks SET state=target_state,row_version=row_version+1,lease_owner=NULL,lease_expires_at=NULL,result_planning_run_id=p_run,terminal_code=CASE WHEN p_state='review_required' THEN NULL ELSE p_reason END,updated_at=clock_timestamp() WHERE organization_id=p_org AND id=p_task;
  DELETE FROM internal.agent_task_dispatch WHERE organization_id=p_org AND task_id=p_task;
  PERFORM app.append_agent_task_event(p_org,p_task,target_event,target_status,p_reason,selected.attempt_count,p_run);
  RETURN target_state;
END; $$;

REVOKE ALL ON FUNCTION app.append_agent_task_event(uuid,uuid,text,text,text,integer,uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.create_agent_task(uuid,uuid,uuid,uuid,integer,uuid,integer,text,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.cancel_agent_task(uuid,uuid,uuid,integer,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.claim_agent_task(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.start_agent_task(uuid,uuid,text,bigint) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.heartbeat_agent_task(uuid,uuid,text,bigint) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.fail_agent_task(uuid,uuid,text,bigint,text,boolean) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.finalize_agent_task_result(uuid,uuid,text,bigint,uuid,text,text,text,text,jsonb,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.create_agent_task(uuid,uuid,uuid,uuid,integer,uuid,integer,text,text,text) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.cancel_agent_task(uuid,uuid,uuid,integer,text,text) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.claim_agent_task(text) TO night_voyager_worker;
GRANT EXECUTE ON FUNCTION app.start_agent_task(uuid,uuid,text,bigint) TO night_voyager_worker;
GRANT EXECUTE ON FUNCTION app.heartbeat_agent_task(uuid,uuid,text,bigint) TO night_voyager_worker;
GRANT EXECUTE ON FUNCTION app.fail_agent_task(uuid,uuid,text,bigint,text,boolean) TO night_voyager_worker;
GRANT EXECUTE ON FUNCTION app.finalize_agent_task_result(uuid,uuid,text,bigint,uuid,text,text,text,text,jsonb,uuid) TO night_voyager_worker;
GRANT SELECT ON app.agent_tasks,app.agent_task_events TO night_voyager_api;
GRANT SELECT ON app.agent_tasks TO night_voyager_worker;
"""


def upgrade() -> None:
    for statement in _split_statements(UPGRADE_SQL):
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS app.finalize_agent_task_result(uuid,uuid,text,bigint,uuid,text,text,text,text,jsonb,uuid)")
    op.execute("DROP FUNCTION IF EXISTS app.fail_agent_task(uuid,uuid,text,bigint,text,boolean)")
    op.execute("DROP FUNCTION IF EXISTS app.heartbeat_agent_task(uuid,uuid,text,bigint)")
    op.execute("DROP FUNCTION IF EXISTS app.start_agent_task(uuid,uuid,text,bigint)")
    op.execute("DROP FUNCTION IF EXISTS app.claim_agent_task(text)")
    op.execute("DROP FUNCTION IF EXISTS app.cancel_agent_task(uuid,uuid,uuid,integer,text,text)")
    op.execute("DROP FUNCTION IF EXISTS app.create_agent_task(uuid,uuid,uuid,uuid,integer,uuid,integer,text,text,text)")
    op.execute("DROP FUNCTION IF EXISTS app.append_agent_task_event(uuid,uuid,text,text,text,integer,uuid)")
    op.execute("DROP TABLE internal.agent_task_dispatch")
    op.execute("DROP SCHEMA internal")
    op.execute("DROP TABLE app.agent_task_events")
    op.execute("DROP TABLE app.agent_executions")
    op.execute("DROP TABLE app.agent_tasks")
    op.execute("DROP FUNCTION IF EXISTS app.reject_agent_task_event_mutation()")


def _split_statements(sql: str) -> list[str]:
    statements: list[str] = []
    buffer: list[str] = []
    in_dollar_quote = False
    index = 0
    while index < len(sql):
        if sql[index : index + 2] == "$$":
            in_dollar_quote = not in_dollar_quote
            buffer.append("$$")
            index += 2
            continue
        character = sql[index]
        if character == ";" and not in_dollar_quote:
            statement = "".join(buffer).strip()
            if statement:
                statements.append(statement)
            buffer = []
        else:
            buffer.append(character)
        index += 1
    if remainder := "".join(buffer).strip():
        statements.append(remainder)
    return statements
