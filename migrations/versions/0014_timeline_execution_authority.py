# ruff: noqa: E501
"""Add governed timeline execution storage and database authority declarations."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "timeline_executions",
    "timeline_checkpoints",
    "timeline_checkpoint_attestations",
    "timeline_checkpoint_verifications",
    "timeline_reassessment_requests",
    "timeline_mutation_receipts",
)

FUNCTION_SIGNATURES = (
    "app.read_plan_execution_context(uuid,uuid,text,text)",
    "app.read_timeline_execution(uuid,uuid,text,uuid)",
    "app.start_timeline_execution(uuid,uuid,text,uuid,uuid,integer,uuid,uuid,text,text)",
    "app.attest_timeline_checkpoint(uuid,uuid,text,uuid,uuid,uuid,integer,integer,text,text,text,text,uuid,uuid,text,text)",
    "app.verify_timeline_checkpoint(uuid,uuid,text,uuid,uuid,uuid,uuid,integer,integer,text,text,uuid,uuid,text,text)",
    "app.request_timeline_reassessment(uuid,uuid,text,uuid,uuid,uuid,uuid,integer,integer,text,uuid,uuid,text,text)",
)

UPGRADE_SQL = r"""
ALTER TABLE app.family_decisions
  ADD CONSTRAINT family_decisions_timeline_execution_anchor_unique
  UNIQUE (organization_id,id,receipt_id,case_id);
ALTER TABLE app.timeline_plans
  ADD CONSTRAINT timeline_plans_execution_anchor_unique
  UNIQUE (organization_id,id,family_decision_id);

CREATE TABLE app.timeline_executions (
  organization_id uuid NOT NULL,
  id uuid NOT NULL,
  case_id uuid NOT NULL,
  case_revision integer NOT NULL CHECK (case_revision > 0),
  family_decision_id uuid NOT NULL,
  decision_receipt_id uuid NOT NULL,
  timeline_plan_id uuid NOT NULL,
  schema_version integer NOT NULL CHECK (schema_version=1),
  state text NOT NULL CHECK (state IN ('active','reassessment_required','completed')),
  row_version integer NOT NULL CHECK (row_version > 0),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id,id),
  UNIQUE (organization_id,timeline_plan_id),
  UNIQUE (organization_id,id,case_id,case_revision),
  UNIQUE (
    organization_id,id,case_id,case_revision,family_decision_id,
    decision_receipt_id,timeline_plan_id
  ),
  FOREIGN KEY (organization_id,case_id,case_revision)
    REFERENCES app.student_case_revisions(organization_id,case_id,revision),
  FOREIGN KEY (organization_id,family_decision_id,decision_receipt_id,case_id)
    REFERENCES app.family_decisions(organization_id,id,receipt_id,case_id),
  FOREIGN KEY (organization_id,timeline_plan_id,family_decision_id)
    REFERENCES app.timeline_plans(organization_id,id,family_decision_id)
);

CREATE TABLE app.timeline_checkpoints (
  organization_id uuid NOT NULL,
  id uuid NOT NULL,
  execution_id uuid NOT NULL,
  ordinal integer NOT NULL CHECK (ordinal > 0),
  milestone_key text NOT NULL CHECK (milestone_key IN ('documents','application','visa','arrival')),
  due_date date NOT NULL,
  accountable_role text NOT NULL CHECK (accountable_role IN ('student','parent')),
  state text NOT NULL CHECK (state IN ('pending','in_progress','awaiting_advisor','verified','blocked')),
  row_version integer NOT NULL CHECK (row_version > 0),
  attested_at timestamptz,
  verified_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id,id),
  UNIQUE (organization_id,execution_id,id),
  UNIQUE (organization_id,execution_id,ordinal),
  UNIQUE (organization_id,execution_id,milestone_key),
  FOREIGN KEY (organization_id,execution_id)
    REFERENCES app.timeline_executions(organization_id,id)
);

CREATE TABLE app.timeline_checkpoint_attestations (
  organization_id uuid NOT NULL,
  attestation_id uuid NOT NULL,
  execution_id uuid NOT NULL,
  checkpoint_id uuid NOT NULL,
  reporter_actor_id uuid NOT NULL,
  reporter_role text NOT NULL CHECK (reporter_role IN ('student','parent')),
  attestation_kind text NOT NULL CHECK (attestation_kind IN ('progress','completion','blocked')),
  status_code text NOT NULL CHECK (status_code IN ('work_in_progress','ready_for_advisor','work_blocked')),
  attestation_code text NOT NULL CHECK (attestation_code IN ('documents_status_confirmed','application_status_confirmed','visa_status_confirmed','arrival_status_confirmed')),
  reason_code text NOT NULL CHECK (reason_code IN ('not_applicable','missing_required_input','external_dependency_unavailable','deadline_at_risk')),
  observed_execution_version integer NOT NULL CHECK (observed_execution_version > 0),
  observed_checkpoint_version integer NOT NULL CHECK (observed_checkpoint_version > 0),
  request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id,attestation_id),
  UNIQUE (organization_id,execution_id,checkpoint_id,attestation_id),
  FOREIGN KEY (organization_id,execution_id,checkpoint_id)
    REFERENCES app.timeline_checkpoints(organization_id,execution_id,id),
  FOREIGN KEY (organization_id,reporter_actor_id,reporter_role)
    REFERENCES app.memberships(organization_id,actor_id,role)
);

CREATE TABLE app.timeline_checkpoint_verifications (
  organization_id uuid NOT NULL,
  verification_id uuid NOT NULL,
  execution_id uuid NOT NULL,
  checkpoint_id uuid NOT NULL,
  attestation_id uuid NOT NULL,
  advisor_actor_id uuid NOT NULL,
  action text NOT NULL CHECK (action IN ('verify','request_update')),
  reason_code text NOT NULL CHECK (reason_code IN ('attestation_verified','status_update_required','status_inconsistent')),
  observed_execution_version integer NOT NULL CHECK (observed_execution_version > 0),
  observed_checkpoint_version integer NOT NULL CHECK (observed_checkpoint_version > 0),
  request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id,verification_id),
  FOREIGN KEY (organization_id,execution_id,checkpoint_id)
    REFERENCES app.timeline_checkpoints(organization_id,execution_id,id),
  FOREIGN KEY (organization_id,execution_id,checkpoint_id,attestation_id)
    REFERENCES app.timeline_checkpoint_attestations(
      organization_id,execution_id,checkpoint_id,attestation_id
    ),
  FOREIGN KEY (organization_id,advisor_actor_id)
    REFERENCES app.actors(organization_id,id)
);

CREATE TABLE app.timeline_reassessment_requests (
  organization_id uuid NOT NULL,
  reassessment_id uuid NOT NULL,
  execution_id uuid NOT NULL,
  checkpoint_id uuid NOT NULL,
  advisor_actor_id uuid NOT NULL,
  trigger text NOT NULL CHECK (trigger IN ('blocked_attestation','deadline_elapsed')),
  trigger_reference_id uuid,
  observed_execution_version integer NOT NULL CHECK (observed_execution_version > 0),
  observed_checkpoint_version integer NOT NULL CHECK (observed_checkpoint_version > 0),
  request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
  accepted_database_date date NOT NULL,
  accepted_trigger_projection_sha256 text NOT NULL CHECK (accepted_trigger_projection_sha256 ~ '^[0-9a-f]{64}$'),
  handoff_schema_version integer NOT NULL CHECK (handoff_schema_version=1),
  predecessor_case_id uuid NOT NULL,
  predecessor_case_revision integer NOT NULL CHECK (predecessor_case_revision > 0),
  predecessor_decision_id uuid NOT NULL,
  predecessor_decision_receipt_id uuid NOT NULL,
  predecessor_timeline_plan_id uuid NOT NULL,
  predecessor_execution_id uuid NOT NULL,
  predecessor_checkpoint_id uuid NOT NULL,
  owner_role text NOT NULL CHECK (owner_role='advisor'),
  successor_status text NOT NULL CHECK (successor_status='pending_future_authorization'),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id,reassessment_id),
  UNIQUE (organization_id,execution_id),
  FOREIGN KEY (organization_id,execution_id,checkpoint_id)
    REFERENCES app.timeline_checkpoints(organization_id,execution_id,id),
  FOREIGN KEY (organization_id,advisor_actor_id)
    REFERENCES app.actors(organization_id,id),
  FOREIGN KEY (organization_id,predecessor_case_id,predecessor_case_revision)
    REFERENCES app.student_case_revisions(organization_id,case_id,revision),
  FOREIGN KEY (
    organization_id,predecessor_execution_id,predecessor_case_id,
    predecessor_case_revision,predecessor_decision_id,
    predecessor_decision_receipt_id,predecessor_timeline_plan_id
  ) REFERENCES app.timeline_executions(
    organization_id,id,case_id,case_revision,family_decision_id,
    decision_receipt_id,timeline_plan_id
  ),
  FOREIGN KEY (organization_id,predecessor_execution_id,predecessor_checkpoint_id)
    REFERENCES app.timeline_checkpoints(organization_id,execution_id,id)
);

CREATE TABLE app.timeline_mutation_receipts (
  organization_id uuid NOT NULL,
  receipt_id uuid NOT NULL,
  actor_id uuid NOT NULL,
  operation text NOT NULL CHECK (operation IN ('start','attest','verify','reassess')),
  key_sha256 text NOT NULL CHECK (key_sha256 ~ '^[0-9a-f]{64}$'),
  request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
  result_kind text NOT NULL CHECK (result_kind IN ('timeline_execution_started','timeline_checkpoint_attested','timeline_checkpoint_verified','timeline_reassessment_requested')),
  result_id uuid NOT NULL,
  execution_id uuid NOT NULL,
  checkpoint_id uuid,
  before_execution_version integer CHECK (before_execution_version > 0),
  after_execution_version integer NOT NULL CHECK (after_execution_version > 0),
  before_checkpoint_version integer CHECK (before_checkpoint_version > 0),
  after_checkpoint_version integer CHECK (after_checkpoint_version > 0),
  schema_version integer NOT NULL CHECK (schema_version=1),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id,receipt_id),
  UNIQUE (organization_id,actor_id,operation,key_sha256),
  FOREIGN KEY (organization_id,actor_id)
    REFERENCES app.actors(organization_id,id),
  FOREIGN KEY (organization_id,execution_id)
    REFERENCES app.timeline_executions(organization_id,id),
  FOREIGN KEY (organization_id,execution_id,checkpoint_id)
    REFERENCES app.timeline_checkpoints(organization_id,execution_id,id)
);

CREATE INDEX timeline_checkpoint_attestations_activity_idx
  ON app.timeline_checkpoint_attestations
  (organization_id,execution_id,created_at DESC,attestation_id DESC);
CREATE INDEX timeline_checkpoint_verifications_activity_idx
  ON app.timeline_checkpoint_verifications
  (organization_id,execution_id,created_at DESC,verification_id DESC);
CREATE INDEX timeline_reassessment_requests_activity_idx
  ON app.timeline_reassessment_requests
  (organization_id,execution_id,created_at DESC,reassessment_id DESC);
CREATE INDEX timeline_mutation_receipts_activity_idx
  ON app.timeline_mutation_receipts
  (organization_id,execution_id,created_at DESC,receipt_id DESC);

CREATE FUNCTION app.reject_timeline_execution_history_mutation()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='immutable timeline execution history';
END; $$;
CREATE TRIGGER timeline_checkpoint_attestations_immutable
  BEFORE UPDATE OR DELETE ON app.timeline_checkpoint_attestations
  FOR EACH ROW EXECUTE FUNCTION app.reject_timeline_execution_history_mutation();
CREATE TRIGGER timeline_checkpoint_verifications_immutable
  BEFORE UPDATE OR DELETE ON app.timeline_checkpoint_verifications
  FOR EACH ROW EXECUTE FUNCTION app.reject_timeline_execution_history_mutation();
CREATE TRIGGER timeline_reassessment_requests_immutable
  BEFORE UPDATE OR DELETE ON app.timeline_reassessment_requests
  FOR EACH ROW EXECUTE FUNCTION app.reject_timeline_execution_history_mutation();
CREATE TRIGGER timeline_mutation_receipts_immutable
  BEFORE UPDATE OR DELETE ON app.timeline_mutation_receipts
  FOR EACH ROW EXECUTE FUNCTION app.reject_timeline_execution_history_mutation();

ALTER TABLE app.timeline_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.timeline_executions FORCE ROW LEVEL SECURITY;
CREATE POLICY timeline_executions_tenant_isolation ON app.timeline_executions
  USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid)
  WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);
ALTER TABLE app.timeline_checkpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.timeline_checkpoints FORCE ROW LEVEL SECURITY;
CREATE POLICY timeline_checkpoints_tenant_isolation ON app.timeline_checkpoints
  USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid)
  WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);
ALTER TABLE app.timeline_checkpoint_attestations ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.timeline_checkpoint_attestations FORCE ROW LEVEL SECURITY;
CREATE POLICY timeline_checkpoint_attestations_tenant_isolation ON app.timeline_checkpoint_attestations
  USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid)
  WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);
ALTER TABLE app.timeline_checkpoint_verifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.timeline_checkpoint_verifications FORCE ROW LEVEL SECURITY;
CREATE POLICY timeline_checkpoint_verifications_tenant_isolation ON app.timeline_checkpoint_verifications
  USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid)
  WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);
ALTER TABLE app.timeline_reassessment_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.timeline_reassessment_requests FORCE ROW LEVEL SECURITY;
CREATE POLICY timeline_reassessment_requests_tenant_isolation ON app.timeline_reassessment_requests
  USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid)
  WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);
ALTER TABLE app.timeline_mutation_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.timeline_mutation_receipts FORCE ROW LEVEL SECURITY;
CREATE POLICY timeline_mutation_receipts_tenant_isolation ON app.timeline_mutation_receipts
  USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid)
  WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);

CREATE FUNCTION app.read_plan_execution_context(p_org uuid,p_actor uuid,p_role text,p_scenario text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN RAISE EXCEPTION USING ERRCODE='NV003',MESSAGE='timeline execution projection unavailable'; END; $$;
CREATE FUNCTION app.read_timeline_execution(p_org uuid,p_actor uuid,p_role text,p_case uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN RAISE EXCEPTION USING ERRCODE='NV003',MESSAGE='timeline execution projection unavailable'; END; $$;
CREATE FUNCTION app.start_timeline_execution(p_org uuid,p_actor uuid,p_role text,p_timeline uuid,p_case uuid,p_expected_case_revision integer,p_execution uuid,p_receipt uuid,p_key_hash text,p_request_hash text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN RAISE EXCEPTION USING ERRCODE='NV003',MESSAGE='timeline execution mutation unavailable'; END; $$;
CREATE FUNCTION app.attest_timeline_checkpoint(p_org uuid,p_actor uuid,p_role text,p_case uuid,p_execution uuid,p_checkpoint uuid,p_expected_execution_version integer,p_expected_checkpoint_version integer,p_kind text,p_status text,p_attestation_code text,p_reason_code text,p_attestation uuid,p_receipt uuid,p_key_hash text,p_request_hash text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN RAISE EXCEPTION USING ERRCODE='NV003',MESSAGE='timeline execution mutation unavailable'; END; $$;
CREATE FUNCTION app.verify_timeline_checkpoint(p_org uuid,p_actor uuid,p_role text,p_case uuid,p_execution uuid,p_checkpoint uuid,p_attestation uuid,p_expected_execution_version integer,p_expected_checkpoint_version integer,p_action text,p_reason_code text,p_verification uuid,p_receipt uuid,p_key_hash text,p_request_hash text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN RAISE EXCEPTION USING ERRCODE='NV003',MESSAGE='timeline execution mutation unavailable'; END; $$;
CREATE FUNCTION app.request_timeline_reassessment(p_org uuid,p_actor uuid,p_role text,p_case uuid,p_execution uuid,p_checkpoint uuid,p_trigger_reference uuid,p_expected_execution_version integer,p_expected_checkpoint_version integer,p_trigger text,p_reassessment uuid,p_receipt uuid,p_key_hash text,p_request_hash text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN RAISE EXCEPTION USING ERRCODE='NV003',MESSAGE='timeline execution mutation unavailable'; END; $$;

REVOKE ALL ON FUNCTION app.read_plan_execution_context(uuid,uuid,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.read_timeline_execution(uuid,uuid,text,uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.start_timeline_execution(uuid,uuid,text,uuid,uuid,integer,uuid,uuid,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.attest_timeline_checkpoint(uuid,uuid,text,uuid,uuid,uuid,integer,integer,text,text,text,text,uuid,uuid,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.verify_timeline_checkpoint(uuid,uuid,text,uuid,uuid,uuid,uuid,integer,integer,text,text,uuid,uuid,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.request_timeline_reassessment(uuid,uuid,text,uuid,uuid,uuid,uuid,integer,integer,text,uuid,uuid,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.read_plan_execution_context(uuid,uuid,text,text) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.read_timeline_execution(uuid,uuid,text,uuid) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.start_timeline_execution(uuid,uuid,text,uuid,uuid,integer,uuid,uuid,text,text) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.attest_timeline_checkpoint(uuid,uuid,text,uuid,uuid,uuid,integer,integer,text,text,text,text,uuid,uuid,text,text) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.verify_timeline_checkpoint(uuid,uuid,text,uuid,uuid,uuid,uuid,integer,integer,text,text,uuid,uuid,text,text) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.request_timeline_reassessment(uuid,uuid,text,uuid,uuid,uuid,uuid,integer,integer,text,uuid,uuid,text,text) TO night_voyager_api;
GRANT SELECT ON app.timeline_executions,app.timeline_checkpoints,
  app.timeline_checkpoint_attestations,app.timeline_checkpoint_verifications,
  app.timeline_reassessment_requests,app.timeline_mutation_receipts
  TO night_voyager_api;
REVOKE ALL ON app.timeline_executions,app.timeline_checkpoints,
  app.timeline_checkpoint_attestations,app.timeline_checkpoint_verifications,
  app.timeline_reassessment_requests,app.timeline_mutation_receipts
  FROM night_voyager_worker;
"""

AUTHORITY_SQL = r"""
CREATE OR REPLACE FUNCTION app.read_plan_execution_context(p_org uuid,p_actor uuid,p_role text,p_scenario text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
  v_count integer;
  v_result jsonb;
BEGIN
  IF p_scenario IS DISTINCT FROM 'governed-plan-execution-v1'
     OR p_role NOT IN ('advisor','student','parent') THEN
    RAISE EXCEPTION USING ERRCODE='NV003',MESSAGE='plan execution context unavailable';
  END IF;
  PERFORM app.assert_m3b_context(p_org,p_actor,p_role);
  SELECT count(*),(array_agg(jsonb_build_object(
    'schema_version',1,
    'scenario','governed-plan-execution-v1',
    'case_id',d.case_id,
    'case_revision',c.current_revision,
    'decision_id',d.id,
    'decision_receipt_id',d.receipt_id,
    'timeline_plan_id',t.id,
    'execution_id',e.id,
    'active_role',p_role,
    'assignment_status','assigned'
  )))[1] INTO v_count,v_result
  FROM app.timeline_plans t
  JOIN app.family_decisions d
    ON (d.organization_id,d.id)=(t.organization_id,t.family_decision_id)
  JOIN app.student_cases c
    ON (c.organization_id,c.id)=(d.organization_id,d.case_id)
  JOIN app.student_case_participants participant
    ON participant.organization_id=d.organization_id
   AND participant.case_id=d.case_id
   AND participant.actor_id=p_actor
   AND participant.role=p_role
  LEFT JOIN app.timeline_executions e
    ON e.organization_id=t.organization_id AND e.timeline_plan_id=t.id
  WHERE t.organization_id=p_org;
  IF v_count<>1 THEN
    RAISE EXCEPTION USING ERRCODE='NV003',MESSAGE='plan execution context unavailable';
  END IF;
  RETURN v_result;
END; $$;

CREATE OR REPLACE FUNCTION app.start_timeline_execution(p_org uuid,p_actor uuid,p_role text,p_timeline uuid,p_case uuid,p_expected_case_revision integer,p_execution uuid,p_receipt uuid,p_key_hash text,p_request_hash text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
  v_anchor record;
  v_prior app.idempotency_records%ROWTYPE;
  v_milestones jsonb;
  v_now timestamptz := clock_timestamp();
  v_result jsonb;
BEGIN
  IF p_role NOT IN ('student','parent') OR p_timeline IS NULL OR p_case IS NULL
     OR p_expected_case_revision<=0
     OR p_execution IS NULL OR p_receipt IS NULL
     OR p_key_hash !~ '^[0-9a-f]{64}$'
     OR p_request_hash !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION USING ERRCODE='NV006',MESSAGE='invalid timeline execution start';
  END IF;
  PERFORM app.assert_m3b_context(p_org,p_actor,p_role);
  PERFORM pg_advisory_xact_lock(hashtextextended(
    p_org::text||':'||p_actor::text||':timeline_execution_start:'||p_key_hash,0
  ));
  SELECT * INTO v_prior FROM app.idempotency_records
   WHERE organization_id=p_org AND actor_id=p_actor
     AND operation='timeline_execution_start' AND key_sha256=p_key_hash;
  IF FOUND THEN
    IF v_prior.request_sha256<>p_request_hash
       OR v_prior.response_kind<>'timeline_execution_started' THEN
      RAISE EXCEPTION USING ERRCODE='NV008',MESSAGE='idempotency request mismatch';
    END IF;
    SELECT jsonb_build_object(
      'schema_version',schema_version,'receipt_id',receipt_id,
      'operation',operation,'result_kind',result_kind,'result_id',result_id,
      'execution_id',execution_id,'checkpoint_id',checkpoint_id,
      'before_execution_version',before_execution_version,
      'after_execution_version',after_execution_version,
      'before_checkpoint_version',before_checkpoint_version,
      'after_checkpoint_version',after_checkpoint_version,'created_at',created_at
    ) INTO v_result FROM app.timeline_mutation_receipts
     WHERE organization_id=p_org AND receipt_id=v_prior.response_id;
    IF v_result IS NULL THEN
      RAISE EXCEPTION USING ERRCODE='NV006',MESSAGE='idempotency receipt unavailable';
    END IF;
    RETURN v_result;
  END IF;
  SELECT t.id AS timeline_id,t.milestones,d.id AS decision_id,d.receipt_id,
         d.case_id,c.current_revision
    INTO v_anchor
    FROM app.timeline_plans t
    JOIN app.family_decisions d
      ON (d.organization_id,d.id)=(t.organization_id,t.family_decision_id)
    JOIN app.student_cases c
      ON (c.organization_id,c.id)=(d.organization_id,d.case_id)
    JOIN app.student_case_participants participant
      ON participant.organization_id=d.organization_id
     AND participant.case_id=d.case_id
     AND participant.actor_id=p_actor
     AND participant.role=p_role
   WHERE t.organization_id=p_org AND t.id=p_timeline
   FOR SHARE OF t,d,c;
  IF NOT FOUND THEN
    RAISE EXCEPTION USING ERRCODE='NV003',MESSAGE='timeline execution target unavailable';
  END IF;
  IF v_anchor.case_id IS DISTINCT FROM p_case THEN
    RAISE EXCEPTION USING ERRCODE='NV003',MESSAGE='timeline execution target unavailable';
  END IF;
  IF v_anchor.current_revision IS DISTINCT FROM p_expected_case_revision THEN
    RAISE EXCEPTION USING ERRCODE='NV020',MESSAGE='case revision is stale';
  END IF;
  v_milestones := v_anchor.milestones;
  IF jsonb_typeof(v_milestones)<>'array' OR jsonb_array_length(v_milestones)<>4
     OR v_milestones->0->>'key'<>'documents'
     OR v_milestones->1->>'key'<>'application'
     OR v_milestones->2->>'key'<>'visa'
     OR v_milestones->3->>'key'<>'arrival'
     OR EXISTS (
       SELECT 1
         FROM jsonb_array_elements(v_milestones) item
         CROSS JOIN LATERAL jsonb_object_keys(item) item_key
        WHERE item_key NOT IN ('key','due_date')
     ) THEN
    RAISE EXCEPTION USING ERRCODE='NV006',MESSAGE='timeline milestone snapshot mismatch';
  END IF;
  IF EXISTS (
    SELECT 1 FROM app.timeline_executions
     WHERE organization_id=p_org AND timeline_plan_id=p_timeline
  ) THEN
    RAISE EXCEPTION USING ERRCODE='NV023',MESSAGE='timeline execution already exists';
  END IF;
  INSERT INTO app.timeline_executions(
    organization_id,id,case_id,case_revision,family_decision_id,
    decision_receipt_id,timeline_plan_id,schema_version,state,row_version,
    created_at,updated_at
  ) VALUES(
    p_org,p_execution,v_anchor.case_id,v_anchor.current_revision,
    v_anchor.decision_id,v_anchor.receipt_id,p_timeline,1,'active',1,v_now,v_now
  );
  INSERT INTO app.timeline_checkpoints(
    organization_id,id,execution_id,ordinal,milestone_key,due_date,
    accountable_role,state,row_version,created_at,updated_at
  )
  SELECT p_org,gen_random_uuid(),p_execution,ordinality,
         milestone->>'key',(milestone->>'due_date')::date,
         CASE WHEN ordinality=4 THEN 'parent' ELSE 'student' END,
         CASE WHEN ordinality=1 THEN 'in_progress' ELSE 'pending' END,
         1,v_now,v_now
    FROM jsonb_array_elements(v_milestones) WITH ORDINALITY item(milestone,ordinality);
  INSERT INTO app.timeline_mutation_receipts(
    organization_id,receipt_id,actor_id,operation,key_sha256,request_sha256,
    result_kind,result_id,execution_id,checkpoint_id,before_execution_version,
    after_execution_version,before_checkpoint_version,after_checkpoint_version,
    schema_version,created_at
  ) VALUES(
    p_org,p_receipt,p_actor,'start',p_key_hash,p_request_hash,
    'timeline_execution_started',p_execution,p_execution,NULL,NULL,1,NULL,NULL,1,v_now
  );
  INSERT INTO app.idempotency_records(
    organization_id,actor_id,operation,key_sha256,request_sha256,
    response_kind,response_id,created_at
  ) VALUES(
    p_org,p_actor,'timeline_execution_start',p_key_hash,p_request_hash,
    'timeline_execution_started',p_receipt,v_now
  );
  SELECT jsonb_build_object(
    'schema_version',schema_version,'receipt_id',receipt_id,
    'operation',operation,'result_kind',result_kind,'result_id',result_id,
    'execution_id',execution_id,'checkpoint_id',checkpoint_id,
    'before_execution_version',before_execution_version,
    'after_execution_version',after_execution_version,
    'before_checkpoint_version',before_checkpoint_version,
    'after_checkpoint_version',after_checkpoint_version,'created_at',created_at
  ) INTO v_result FROM app.timeline_mutation_receipts
   WHERE organization_id=p_org AND receipt_id=p_receipt;
  RETURN v_result;
END; $$;

CREATE OR REPLACE FUNCTION app.attest_timeline_checkpoint(p_org uuid,p_actor uuid,p_role text,p_case uuid,p_execution uuid,p_checkpoint uuid,p_expected_execution_version integer,p_expected_checkpoint_version integer,p_kind text,p_status text,p_attestation_code text,p_reason_code text,p_attestation uuid,p_receipt uuid,p_key_hash text,p_request_hash text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
  v_execution app.timeline_executions%ROWTYPE;
  v_checkpoint app.timeline_checkpoints%ROWTYPE;
  v_current_count integer;
  v_prior app.idempotency_records%ROWTYPE;
  v_now timestamptz := clock_timestamp();
  v_target_state text;
  v_expected_code text;
  v_result jsonb;
BEGIN
  IF p_role NOT IN ('student','parent') OR p_case IS NULL
     OR p_execution IS NULL OR p_checkpoint IS NULL
     OR p_attestation IS NULL OR p_receipt IS NULL
     OR p_expected_execution_version<=0 OR p_expected_checkpoint_version<=0
     OR p_key_hash !~ '^[0-9a-f]{64}$'
     OR p_request_hash !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION USING ERRCODE='NV006',MESSAGE='invalid checkpoint attestation';
  END IF;
  PERFORM app.assert_m3b_context(p_org,p_actor,p_role);
  SELECT * INTO v_execution FROM app.timeline_executions
   WHERE organization_id=p_org AND id=p_execution FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION USING ERRCODE='NV003',MESSAGE='timeline execution unavailable';
  END IF;
  SELECT * INTO v_prior FROM app.idempotency_records
   WHERE organization_id=p_org AND actor_id=p_actor
     AND operation='timeline_checkpoint_attest' AND key_sha256=p_key_hash;
  IF FOUND THEN
    IF v_prior.request_sha256<>p_request_hash
       OR v_prior.response_kind<>'timeline_checkpoint_attested' THEN
      RAISE EXCEPTION USING ERRCODE='NV008',MESSAGE='idempotency request mismatch';
    END IF;
    SELECT jsonb_build_object(
      'schema_version',schema_version,'receipt_id',receipt_id,
      'operation',operation,'result_kind',result_kind,'result_id',result_id,
      'execution_id',execution_id,'checkpoint_id',checkpoint_id,
      'before_execution_version',before_execution_version,
      'after_execution_version',after_execution_version,
      'before_checkpoint_version',before_checkpoint_version,
      'after_checkpoint_version',after_checkpoint_version,'created_at',created_at
    ) INTO v_result FROM app.timeline_mutation_receipts
     WHERE organization_id=p_org AND receipt_id=v_prior.response_id;
    RETURN v_result;
  END IF;
  IF v_execution.case_id IS DISTINCT FROM p_case THEN
    RAISE EXCEPTION USING ERRCODE='NV003',MESSAGE='timeline execution unavailable';
  END IF;
  IF v_execution.state='completed' THEN
    RAISE EXCEPTION USING ERRCODE='NV022',MESSAGE='timeline execution is completed';
  END IF;
  IF v_execution.state<>'active' THEN
    RAISE EXCEPTION USING ERRCODE='NV026',MESSAGE='timeline reassessment is required';
  END IF;
  SELECT count(*) INTO v_current_count FROM app.timeline_checkpoints
   WHERE organization_id=p_org AND execution_id=p_execution
     AND state NOT IN ('pending','verified');
  IF v_current_count<>1 THEN
    RAISE EXCEPTION USING ERRCODE='NV023',MESSAGE='current checkpoint unavailable';
  END IF;
  SELECT * INTO STRICT v_checkpoint FROM app.timeline_checkpoints
   WHERE organization_id=p_org AND execution_id=p_execution
     AND state NOT IN ('pending','verified')
   FOR UPDATE;
  IF v_checkpoint.id IS DISTINCT FROM p_checkpoint THEN
    RAISE EXCEPTION USING ERRCODE='NV023',MESSAGE='checkpoint is not current';
  END IF;
  IF v_execution.row_version<>p_expected_execution_version THEN
    RAISE EXCEPTION USING ERRCODE='NV020',MESSAGE='execution version is stale';
  END IF;
  IF v_checkpoint.row_version<>p_expected_checkpoint_version THEN
    RAISE EXCEPTION USING ERRCODE='NV021',MESSAGE='checkpoint version is stale';
  END IF;
  IF v_checkpoint.state<>'in_progress' OR v_checkpoint.accountable_role<>p_role
     OR NOT EXISTS (
       SELECT 1 FROM app.student_case_participants participant
        WHERE participant.organization_id=p_org
          AND participant.case_id=v_execution.case_id
          AND participant.actor_id=p_actor AND participant.role=p_role
     ) THEN
    RAISE EXCEPTION USING ERRCODE='NV024',MESSAGE='checkpoint attestation conflict';
  END IF;
  v_expected_code := v_checkpoint.milestone_key||'_status_confirmed';
  IF p_attestation_code<>v_expected_code
     OR (p_kind='progress' AND (p_status<>'work_in_progress' OR p_reason_code<>'not_applicable'))
     OR (p_kind='completion' AND (p_status<>'ready_for_advisor' OR p_reason_code<>'not_applicable'))
     OR (p_kind='blocked' AND (p_status<>'work_blocked' OR p_reason_code NOT IN ('missing_required_input','external_dependency_unavailable','deadline_at_risk')))
     OR p_kind NOT IN ('progress','completion','blocked') THEN
    RAISE EXCEPTION USING ERRCODE='NV024',MESSAGE='invalid checkpoint attestation codes';
  END IF;
  v_target_state := CASE p_kind WHEN 'progress' THEN 'in_progress'
    WHEN 'completion' THEN 'awaiting_advisor' ELSE 'blocked' END;
  INSERT INTO app.timeline_checkpoint_attestations(
    organization_id,attestation_id,execution_id,checkpoint_id,
    reporter_actor_id,reporter_role,attestation_kind,status_code,
    attestation_code,reason_code,observed_execution_version,
    observed_checkpoint_version,request_sha256,created_at
  ) VALUES(
    p_org,p_attestation,p_execution,p_checkpoint,p_actor,p_role,p_kind,p_status,
    p_attestation_code,p_reason_code,p_expected_execution_version,
    p_expected_checkpoint_version,p_request_hash,v_now
  );
  UPDATE app.timeline_checkpoints SET state=v_target_state,
    row_version=row_version+1,attested_at=v_now,updated_at=v_now
   WHERE organization_id=p_org AND id=p_checkpoint;
  UPDATE app.timeline_executions SET row_version=row_version+1,updated_at=v_now
   WHERE organization_id=p_org AND id=p_execution;
  INSERT INTO app.timeline_mutation_receipts(
    organization_id,receipt_id,actor_id,operation,key_sha256,request_sha256,
    result_kind,result_id,execution_id,checkpoint_id,before_execution_version,
    after_execution_version,before_checkpoint_version,after_checkpoint_version,
    schema_version,created_at
  ) VALUES(
    p_org,p_receipt,p_actor,'attest',p_key_hash,p_request_hash,
    'timeline_checkpoint_attested',p_attestation,p_execution,p_checkpoint,
    p_expected_execution_version,p_expected_execution_version+1,
    p_expected_checkpoint_version,p_expected_checkpoint_version+1,1,v_now
  );
  INSERT INTO app.idempotency_records(
    organization_id,actor_id,operation,key_sha256,request_sha256,
    response_kind,response_id,created_at
  ) VALUES(
    p_org,p_actor,'timeline_checkpoint_attest',p_key_hash,p_request_hash,
    'timeline_checkpoint_attested',p_receipt,v_now
  );
  SELECT jsonb_build_object(
    'schema_version',schema_version,'receipt_id',receipt_id,
    'operation',operation,'result_kind',result_kind,'result_id',result_id,
    'execution_id',execution_id,'checkpoint_id',checkpoint_id,
    'before_execution_version',before_execution_version,
    'after_execution_version',after_execution_version,
    'before_checkpoint_version',before_checkpoint_version,
    'after_checkpoint_version',after_checkpoint_version,'created_at',created_at
  ) INTO v_result FROM app.timeline_mutation_receipts
   WHERE organization_id=p_org AND receipt_id=p_receipt;
  RETURN v_result;
END; $$;

CREATE OR REPLACE FUNCTION app.verify_timeline_checkpoint(p_org uuid,p_actor uuid,p_role text,p_case uuid,p_execution uuid,p_checkpoint uuid,p_attestation uuid,p_expected_execution_version integer,p_expected_checkpoint_version integer,p_action text,p_reason_code text,p_verification uuid,p_receipt uuid,p_key_hash text,p_request_hash text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
  v_execution app.timeline_executions%ROWTYPE;
  v_checkpoint app.timeline_checkpoints%ROWTYPE;
  v_current_count integer;
  v_prior app.idempotency_records%ROWTYPE;
  v_latest uuid;
  v_now timestamptz := clock_timestamp();
  v_result jsonb;
BEGIN
  IF p_role<>'advisor' OR p_case IS NULL OR p_execution IS NULL OR p_checkpoint IS NULL
     OR p_attestation IS NULL OR p_verification IS NULL OR p_receipt IS NULL
     OR p_expected_execution_version<=0 OR p_expected_checkpoint_version<=0
     OR p_key_hash !~ '^[0-9a-f]{64}$'
     OR p_request_hash !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION USING ERRCODE='NV006',MESSAGE='invalid checkpoint verification';
  END IF;
  PERFORM app.assert_m3b_context(p_org,p_actor,p_role);
  SELECT * INTO v_execution FROM app.timeline_executions
   WHERE organization_id=p_org AND id=p_execution FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION USING ERRCODE='NV003',MESSAGE='timeline execution unavailable';
  END IF;
  SELECT * INTO v_prior FROM app.idempotency_records
   WHERE organization_id=p_org AND actor_id=p_actor
     AND operation='timeline_checkpoint_verify' AND key_sha256=p_key_hash;
  IF FOUND THEN
    IF v_prior.request_sha256<>p_request_hash
       OR v_prior.response_kind<>'timeline_checkpoint_verified' THEN
      RAISE EXCEPTION USING ERRCODE='NV008',MESSAGE='idempotency request mismatch';
    END IF;
    SELECT jsonb_build_object(
      'schema_version',schema_version,'receipt_id',receipt_id,
      'operation',operation,'result_kind',result_kind,'result_id',result_id,
      'execution_id',execution_id,'checkpoint_id',checkpoint_id,
      'before_execution_version',before_execution_version,
      'after_execution_version',after_execution_version,
      'before_checkpoint_version',before_checkpoint_version,
      'after_checkpoint_version',after_checkpoint_version,'created_at',created_at
    ) INTO v_result FROM app.timeline_mutation_receipts
     WHERE organization_id=p_org AND receipt_id=v_prior.response_id;
    RETURN v_result;
  END IF;
  IF v_execution.case_id IS DISTINCT FROM p_case THEN
    RAISE EXCEPTION USING ERRCODE='NV003',MESSAGE='timeline execution unavailable';
  END IF;
  IF v_execution.state='completed' THEN
    RAISE EXCEPTION USING ERRCODE='NV022',MESSAGE='timeline execution is completed';
  END IF;
  IF v_execution.state<>'active' THEN
    RAISE EXCEPTION USING ERRCODE='NV026',MESSAGE='timeline reassessment is required';
  END IF;
  SELECT count(*) INTO v_current_count FROM app.timeline_checkpoints
   WHERE organization_id=p_org AND execution_id=p_execution
     AND state NOT IN ('pending','verified');
  IF v_current_count<>1 THEN
    RAISE EXCEPTION USING ERRCODE='NV023',MESSAGE='current checkpoint unavailable';
  END IF;
  SELECT * INTO STRICT v_checkpoint FROM app.timeline_checkpoints
   WHERE organization_id=p_org AND execution_id=p_execution
     AND state NOT IN ('pending','verified')
   FOR UPDATE;
  IF v_checkpoint.id IS DISTINCT FROM p_checkpoint THEN
    RAISE EXCEPTION USING ERRCODE='NV023',MESSAGE='checkpoint is not current';
  END IF;
  SELECT attestation_id INTO v_latest
    FROM app.timeline_checkpoint_attestations
   WHERE organization_id=p_org AND execution_id=p_execution
     AND checkpoint_id=p_checkpoint AND attestation_kind='completion'
   ORDER BY created_at DESC,attestation_id DESC LIMIT 1;
  IF v_execution.row_version<>p_expected_execution_version THEN
    RAISE EXCEPTION USING ERRCODE='NV020',MESSAGE='execution version is stale';
  END IF;
  IF v_checkpoint.row_version<>p_expected_checkpoint_version THEN
    RAISE EXCEPTION USING ERRCODE='NV021',MESSAGE='checkpoint version is stale';
  END IF;
  IF v_checkpoint.state<>'awaiting_advisor'
     OR v_latest IS DISTINCT FROM p_attestation
     OR NOT EXISTS (
       SELECT 1 FROM app.student_case_participants participant
        WHERE participant.organization_id=p_org
          AND participant.case_id=v_execution.case_id
          AND participant.actor_id=p_actor AND participant.role='advisor'
     )
     OR (p_action='verify' AND p_reason_code<>'attestation_verified')
     OR (p_action='request_update' AND p_reason_code NOT IN ('status_update_required','status_inconsistent'))
     OR p_action NOT IN ('verify','request_update') THEN
    RAISE EXCEPTION USING ERRCODE='NV025',MESSAGE='advisor verification is required';
  END IF;
  INSERT INTO app.timeline_checkpoint_verifications(
    organization_id,verification_id,execution_id,checkpoint_id,attestation_id,
    advisor_actor_id,action,reason_code,observed_execution_version,
    observed_checkpoint_version,request_sha256,created_at
  ) VALUES(
    p_org,p_verification,p_execution,p_checkpoint,p_attestation,p_actor,p_action,
    p_reason_code,p_expected_execution_version,p_expected_checkpoint_version,
    p_request_hash,v_now
  );
  IF p_action='request_update' THEN
    UPDATE app.timeline_checkpoints SET state='in_progress',
      row_version=row_version+1,verified_at=NULL,updated_at=v_now
     WHERE organization_id=p_org AND id=p_checkpoint;
  ELSE
    UPDATE app.timeline_checkpoints SET state='verified',
      row_version=row_version+1,verified_at=v_now,updated_at=v_now
     WHERE organization_id=p_org AND id=p_checkpoint;
    IF v_checkpoint.milestone_key='arrival' THEN
      UPDATE app.timeline_executions SET state='completed',
        row_version=row_version+1,updated_at=v_now
       WHERE organization_id=p_org AND id=p_execution;
    ELSE
      UPDATE app.timeline_checkpoints SET state='in_progress',
        row_version=row_version+1,updated_at=v_now
       WHERE organization_id=p_org AND execution_id=p_execution
         AND ordinal=v_checkpoint.ordinal+1 AND state='pending';
      UPDATE app.timeline_executions SET row_version=row_version+1,updated_at=v_now
       WHERE organization_id=p_org AND id=p_execution;
    END IF;
  END IF;
  IF p_action='request_update' THEN
    UPDATE app.timeline_executions SET row_version=row_version+1,updated_at=v_now
     WHERE organization_id=p_org AND id=p_execution;
  END IF;
  INSERT INTO app.timeline_mutation_receipts(
    organization_id,receipt_id,actor_id,operation,key_sha256,request_sha256,
    result_kind,result_id,execution_id,checkpoint_id,before_execution_version,
    after_execution_version,before_checkpoint_version,after_checkpoint_version,
    schema_version,created_at
  ) VALUES(
    p_org,p_receipt,p_actor,'verify',p_key_hash,p_request_hash,
    'timeline_checkpoint_verified',p_verification,p_execution,p_checkpoint,
    p_expected_execution_version,p_expected_execution_version+1,
    p_expected_checkpoint_version,p_expected_checkpoint_version+1,1,v_now
  );
  INSERT INTO app.idempotency_records(
    organization_id,actor_id,operation,key_sha256,request_sha256,
    response_kind,response_id,created_at
  ) VALUES(
    p_org,p_actor,'timeline_checkpoint_verify',p_key_hash,p_request_hash,
    'timeline_checkpoint_verified',p_receipt,v_now
  );
  SELECT jsonb_build_object(
    'schema_version',schema_version,'receipt_id',receipt_id,
    'operation',operation,'result_kind',result_kind,'result_id',result_id,
    'execution_id',execution_id,'checkpoint_id',checkpoint_id,
    'before_execution_version',before_execution_version,
    'after_execution_version',after_execution_version,
    'before_checkpoint_version',before_checkpoint_version,
    'after_checkpoint_version',after_checkpoint_version,'created_at',created_at
  ) INTO v_result FROM app.timeline_mutation_receipts
   WHERE organization_id=p_org AND receipt_id=p_receipt;
  RETURN v_result;
END; $$;

CREATE OR REPLACE FUNCTION app.request_timeline_reassessment(p_org uuid,p_actor uuid,p_role text,p_case uuid,p_execution uuid,p_checkpoint uuid,p_trigger_reference uuid,p_expected_execution_version integer,p_expected_checkpoint_version integer,p_trigger text,p_reassessment uuid,p_receipt uuid,p_key_hash text,p_request_hash text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
  v_execution app.timeline_executions%ROWTYPE;
  v_checkpoint app.timeline_checkpoints%ROWTYPE;
  v_current_count integer;
  v_prior app.idempotency_records%ROWTYPE;
  v_now timestamptz := clock_timestamp();
  v_observed_date date := CURRENT_DATE;
  v_projection_hash text;
  v_result jsonb;
BEGIN
  IF p_role<>'advisor' OR p_case IS NULL OR p_execution IS NULL OR p_checkpoint IS NULL
     OR p_reassessment IS NULL OR p_receipt IS NULL
     OR p_expected_execution_version<=0 OR p_expected_checkpoint_version<=0
     OR p_trigger NOT IN ('blocked_attestation','deadline_elapsed')
     OR p_key_hash !~ '^[0-9a-f]{64}$'
     OR p_request_hash !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION USING ERRCODE='NV006',MESSAGE='invalid timeline reassessment';
  END IF;
  PERFORM app.assert_m3b_context(p_org,p_actor,p_role);
  SELECT * INTO v_execution FROM app.timeline_executions
   WHERE organization_id=p_org AND id=p_execution FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION USING ERRCODE='NV003',MESSAGE='timeline execution unavailable';
  END IF;
  SELECT * INTO v_prior FROM app.idempotency_records
   WHERE organization_id=p_org AND actor_id=p_actor
     AND operation='timeline_reassessment_request' AND key_sha256=p_key_hash;
  IF FOUND THEN
    IF v_prior.request_sha256<>p_request_hash
       OR v_prior.response_kind<>'timeline_reassessment_requested' THEN
      RAISE EXCEPTION USING ERRCODE='NV008',MESSAGE='idempotency request mismatch';
    END IF;
    SELECT jsonb_build_object(
      'schema_version',schema_version,'receipt_id',receipt_id,
      'operation',operation,'result_kind',result_kind,'result_id',result_id,
      'execution_id',execution_id,'checkpoint_id',checkpoint_id,
      'before_execution_version',before_execution_version,
      'after_execution_version',after_execution_version,
      'before_checkpoint_version',before_checkpoint_version,
      'after_checkpoint_version',after_checkpoint_version,'created_at',created_at
    ) INTO v_result FROM app.timeline_mutation_receipts
     WHERE organization_id=p_org AND receipt_id=v_prior.response_id;
    RETURN v_result;
  END IF;
  IF v_execution.case_id IS DISTINCT FROM p_case THEN
    RAISE EXCEPTION USING ERRCODE='NV003',MESSAGE='timeline execution unavailable';
  END IF;
  IF v_execution.state='completed' THEN
    RAISE EXCEPTION USING ERRCODE='NV022',MESSAGE='timeline execution is completed';
  END IF;
  IF v_execution.state<>'active' THEN
    RAISE EXCEPTION USING ERRCODE='NV026',MESSAGE='timeline reassessment is required';
  END IF;
  SELECT count(*) INTO v_current_count FROM app.timeline_checkpoints
   WHERE organization_id=p_org AND execution_id=p_execution
     AND state NOT IN ('pending','verified');
  IF v_current_count<>1 THEN
    RAISE EXCEPTION USING ERRCODE='NV023',MESSAGE='current checkpoint unavailable';
  END IF;
  SELECT * INTO STRICT v_checkpoint FROM app.timeline_checkpoints
   WHERE organization_id=p_org AND execution_id=p_execution
     AND state NOT IN ('pending','verified')
   FOR UPDATE;
  IF v_checkpoint.id IS DISTINCT FROM p_checkpoint THEN
    RAISE EXCEPTION USING ERRCODE='NV023',MESSAGE='checkpoint is not current';
  END IF;
  IF v_execution.row_version<>p_expected_execution_version THEN
    RAISE EXCEPTION USING ERRCODE='NV020',MESSAGE='execution version is stale';
  END IF;
  IF v_checkpoint.row_version<>p_expected_checkpoint_version THEN
    RAISE EXCEPTION USING ERRCODE='NV021',MESSAGE='checkpoint version is stale';
  END IF;
  IF NOT EXISTS (
       SELECT 1 FROM app.student_case_participants participant
        WHERE participant.organization_id=p_org
          AND participant.case_id=v_execution.case_id
          AND participant.actor_id=p_actor AND participant.role='advisor'
     ) THEN
    RAISE EXCEPTION USING ERRCODE='NV026',MESSAGE='timeline reassessment is required';
  END IF;
  IF p_trigger='blocked_attestation' THEN
    IF v_checkpoint.state<>'blocked' OR p_trigger_reference IS NULL
       OR NOT EXISTS (
         SELECT 1 FROM app.timeline_checkpoint_attestations a
          WHERE a.organization_id=p_org AND a.execution_id=p_execution
            AND a.checkpoint_id=p_checkpoint AND a.attestation_id=p_trigger_reference
            AND a.attestation_kind='blocked'
            AND a.attestation_id=(
              SELECT latest.attestation_id
                FROM app.timeline_checkpoint_attestations latest
               WHERE latest.organization_id=p_org
                 AND latest.execution_id=p_execution
                 AND latest.checkpoint_id=p_checkpoint
               ORDER BY latest.created_at DESC,latest.attestation_id DESC LIMIT 1
            )
       ) THEN
      RAISE EXCEPTION USING ERRCODE='NV026',MESSAGE='blocked reassessment proof unavailable';
    END IF;
  ELSE
    IF p_trigger_reference IS NOT NULL OR v_checkpoint.state='verified'
       OR v_observed_date<=v_checkpoint.due_date THEN
      RAISE EXCEPTION USING ERRCODE='NV026',MESSAGE='deadline reassessment proof unavailable';
    END IF;
  END IF;
  v_projection_hash := encode(sha256(convert_to(jsonb_build_object(
    'trigger',p_trigger,'trigger_reference_id',p_trigger_reference,
    'execution_id',p_execution,'checkpoint_id',p_checkpoint,
    'checkpoint_state',v_checkpoint.state,'due_date',v_checkpoint.due_date,
    'observed_date',v_observed_date
  )::text,'UTF8')),'hex');
  INSERT INTO app.timeline_reassessment_requests(
    organization_id,reassessment_id,execution_id,checkpoint_id,advisor_actor_id,
    trigger,trigger_reference_id,observed_execution_version,
    observed_checkpoint_version,request_sha256,accepted_database_date,
    accepted_trigger_projection_sha256,handoff_schema_version,
    predecessor_case_id,predecessor_case_revision,predecessor_decision_id,
    predecessor_decision_receipt_id,predecessor_timeline_plan_id,
    predecessor_execution_id,predecessor_checkpoint_id,owner_role,
    successor_status,created_at
  ) VALUES(
    p_org,p_reassessment,p_execution,p_checkpoint,p_actor,p_trigger,
    p_trigger_reference,p_expected_execution_version,p_expected_checkpoint_version,
    p_request_hash,v_observed_date,v_projection_hash,1,v_execution.case_id,
    v_execution.case_revision,v_execution.family_decision_id,
    v_execution.decision_receipt_id,v_execution.timeline_plan_id,p_execution,
    p_checkpoint,'advisor','pending_future_authorization',v_now
  );
  UPDATE app.timeline_executions SET state='reassessment_required',
    row_version=row_version+1,updated_at=v_now
   WHERE organization_id=p_org AND id=p_execution;
  INSERT INTO app.timeline_mutation_receipts(
    organization_id,receipt_id,actor_id,operation,key_sha256,request_sha256,
    result_kind,result_id,execution_id,checkpoint_id,before_execution_version,
    after_execution_version,before_checkpoint_version,after_checkpoint_version,
    schema_version,created_at
  ) VALUES(
    p_org,p_receipt,p_actor,'reassess',p_key_hash,p_request_hash,
    'timeline_reassessment_requested',p_reassessment,p_execution,p_checkpoint,
    p_expected_execution_version,p_expected_execution_version+1,
    p_expected_checkpoint_version,p_expected_checkpoint_version,1,v_now
  );
  INSERT INTO app.idempotency_records(
    organization_id,actor_id,operation,key_sha256,request_sha256,
    response_kind,response_id,created_at
  ) VALUES(
    p_org,p_actor,'timeline_reassessment_request',p_key_hash,p_request_hash,
    'timeline_reassessment_requested',p_receipt,v_now
  );
  SELECT jsonb_build_object(
    'schema_version',schema_version,'receipt_id',receipt_id,
    'operation',operation,'result_kind',result_kind,'result_id',result_id,
    'execution_id',execution_id,'checkpoint_id',checkpoint_id,
    'before_execution_version',before_execution_version,
    'after_execution_version',after_execution_version,
    'before_checkpoint_version',before_checkpoint_version,
    'after_checkpoint_version',after_checkpoint_version,'created_at',created_at
  ) INTO v_result FROM app.timeline_mutation_receipts
   WHERE organization_id=p_org AND receipt_id=p_receipt;
  RETURN v_result;
END; $$;

CREATE OR REPLACE FUNCTION app.read_timeline_execution(p_org uuid,p_actor uuid,p_role text,p_case uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
  v_execution app.timeline_executions%ROWTYPE;
  v_execution_count integer;
  v_observed_date date := CURRENT_DATE;
  v_current_count integer;
  v_current jsonb;
  v_current_action jsonb;
  v_activity jsonb;
  v_activity_count integer;
  v_result jsonb;
BEGIN
  IF p_role NOT IN ('advisor','student','parent') THEN
    RAISE EXCEPTION USING ERRCODE='NV003',MESSAGE='timeline execution unavailable';
  END IF;
  PERFORM app.assert_m3b_context(p_org,p_actor,p_role);
  SELECT count(*) INTO v_execution_count
    FROM app.timeline_executions e
   WHERE e.organization_id=p_org AND e.case_id=p_case
     AND EXISTS (
       SELECT 1 FROM app.student_case_participants participant
        WHERE participant.organization_id=e.organization_id
          AND participant.case_id=e.case_id
          AND participant.actor_id=p_actor AND participant.role=p_role
     );
  IF v_execution_count=0 THEN RETURN NULL; END IF;
  IF v_execution_count>1 THEN
    RAISE EXCEPTION USING ERRCODE='NV006',MESSAGE='timeline projection contradictory';
  END IF;
  SELECT e.* INTO STRICT v_execution
    FROM app.timeline_executions e
   WHERE e.organization_id=p_org AND e.case_id=p_case
     AND EXISTS (
       SELECT 1 FROM app.student_case_participants participant
        WHERE participant.organization_id=e.organization_id
          AND participant.case_id=e.case_id
          AND participant.actor_id=p_actor AND participant.role=p_role
     );
  SELECT count(*),(array_agg(jsonb_build_object(
    'schema_version',1,'checkpoint_id',c.id,'execution_id',c.execution_id,
    'ordinal',c.ordinal,'milestone_key',c.milestone_key,'due_date',c.due_date,
    'accountable_role',c.accountable_role,'state',c.state,
    'risk_state',CASE WHEN c.state='verified' THEN 'on_track'
      WHEN v_observed_date>c.due_date THEN 'overdue'
      WHEN c.due_date-v_observed_date BETWEEN 0 AND 14 THEN 'due_soon'
      ELSE 'on_track' END,
    'row_version',c.row_version,'created_at',c.created_at,'updated_at',c.updated_at
  )))[1] INTO v_current_count,v_current
  FROM app.timeline_checkpoints c
  WHERE c.organization_id=p_org AND c.execution_id=v_execution.id
    AND c.state NOT IN ('pending','verified');
  IF (v_execution.state='active' AND v_current_count<>1)
     OR (v_execution.state='completed' AND v_current_count<>0)
     OR (v_execution.state='reassessment_required' AND v_current_count>1) THEN
    RAISE EXCEPTION USING ERRCODE='NV006',MESSAGE='timeline projection contradictory';
  END IF;
  v_current_action := CASE
    WHEN v_execution.state='completed' THEN jsonb_build_object(
      'schema_version',1,'code','execution_completed','owner_role','none',
      'checkpoint_id',NULL,'execution_version',v_execution.row_version,
      'checkpoint_version',NULL
    )
    WHEN v_execution.state='reassessment_required' THEN jsonb_build_object(
      'schema_version',1,'code','reassessment_handoff_required',
      'owner_role','advisor','checkpoint_id',v_current->>'checkpoint_id',
      'execution_version',v_execution.row_version,
      'checkpoint_version',(v_current->>'row_version')::integer
    )
    WHEN v_current->>'state'='awaiting_advisor' THEN jsonb_build_object(
      'schema_version',1,'code','advisor_verification_required',
      'owner_role','advisor','checkpoint_id',v_current->>'checkpoint_id',
      'execution_version',v_execution.row_version,
      'checkpoint_version',(v_current->>'row_version')::integer
    )
    WHEN v_current->>'state'='blocked' THEN jsonb_build_object(
      'schema_version',1,'code','reassessment_handoff_required',
      'owner_role','advisor','checkpoint_id',v_current->>'checkpoint_id',
      'execution_version',v_execution.row_version,
      'checkpoint_version',(v_current->>'row_version')::integer
    )
    ELSE jsonb_build_object(
      'schema_version',1,'code','checkpoint_attestation_required',
      'owner_role',v_current->>'accountable_role',
      'checkpoint_id',v_current->>'checkpoint_id',
      'execution_version',v_execution.row_version,
      'checkpoint_version',(v_current->>'row_version')::integer
    )
  END;
  WITH activity_rows AS (
    (SELECT 'attestation_recorded'::text kind,attestation_id durable_id,
            execution_id,checkpoint_id,created_at
       FROM app.timeline_checkpoint_attestations
      WHERE organization_id=p_org AND execution_id=v_execution.id
      ORDER BY created_at DESC,attestation_id DESC LIMIT 64)
    UNION ALL
    (SELECT 'verification_recorded',verification_id,execution_id,checkpoint_id,created_at
       FROM app.timeline_checkpoint_verifications
      WHERE organization_id=p_org AND execution_id=v_execution.id
      ORDER BY created_at DESC,verification_id DESC LIMIT 64)
    UNION ALL
    (SELECT 'reassessment_recorded',reassessment_id,execution_id,checkpoint_id,created_at
       FROM app.timeline_reassessment_requests
      WHERE organization_id=p_org AND execution_id=v_execution.id
      ORDER BY created_at DESC,reassessment_id DESC LIMIT 64)
    UNION ALL
    (SELECT 'mutation_receipt_recorded',receipt_id,execution_id,checkpoint_id,created_at
       FROM app.timeline_mutation_receipts
      WHERE organization_id=p_org AND execution_id=v_execution.id
      ORDER BY created_at DESC,receipt_id DESC LIMIT 64)
  ), latest AS (
    SELECT * FROM activity_rows ORDER BY created_at DESC,durable_id DESC LIMIT 64
  )
  SELECT COALESCE(jsonb_agg(jsonb_build_object(
    'schema_version',1,'kind',kind,'durable_id',durable_id,
    'execution_id',execution_id,'checkpoint_id',checkpoint_id,'created_at',created_at
  ) ORDER BY created_at DESC,durable_id DESC),'[]'::jsonb)
  INTO v_activity FROM latest;
  SELECT
    (SELECT count(*) FROM app.timeline_checkpoint_attestations WHERE organization_id=p_org AND execution_id=v_execution.id)
    +(SELECT count(*) FROM app.timeline_checkpoint_verifications WHERE organization_id=p_org AND execution_id=v_execution.id)
    +(SELECT count(*) FROM app.timeline_reassessment_requests WHERE organization_id=p_org AND execution_id=v_execution.id)
    +(SELECT count(*) FROM app.timeline_mutation_receipts WHERE organization_id=p_org AND execution_id=v_execution.id)
  INTO v_activity_count;
  SELECT jsonb_build_object(
    'schema_version',1,
    'execution',jsonb_build_object(
      'schema_version',1,'execution_id',v_execution.id,'case_id',v_execution.case_id,
      'case_revision',v_execution.case_revision,'decision_id',v_execution.family_decision_id,
      'decision_receipt_id',v_execution.decision_receipt_id,
      'timeline_plan_id',v_execution.timeline_plan_id,'state',v_execution.state,
      'row_version',v_execution.row_version,'created_at',v_execution.created_at,
      'updated_at',v_execution.updated_at
    ),
    'checkpoints',(
      SELECT COALESCE(jsonb_agg(jsonb_build_object(
        'schema_version',1,'checkpoint_id',c.id,'execution_id',c.execution_id,
        'ordinal',c.ordinal,'milestone_key',c.milestone_key,'due_date',c.due_date,
        'accountable_role',c.accountable_role,'state',c.state,
        'risk_state',CASE WHEN c.state='verified' THEN 'on_track'
          WHEN v_observed_date>c.due_date THEN 'overdue'
          WHEN c.due_date-v_observed_date BETWEEN 0 AND 14 THEN 'due_soon'
          ELSE 'on_track' END,
        'row_version',c.row_version,'created_at',c.created_at,'updated_at',c.updated_at
      ) ORDER BY c.ordinal),'[]'::jsonb)
      FROM app.timeline_checkpoints c
      WHERE c.organization_id=p_org AND c.execution_id=v_execution.id
    ),
    'current_checkpoint',v_current,
    'latest_attestation',(
      SELECT jsonb_build_object(
        'schema_version',1,'attestation_id',a.attestation_id,
        'execution_id',a.execution_id,'checkpoint_id',a.checkpoint_id,
        'reporter_actor_id',a.reporter_actor_id,'reporter_role',a.reporter_role,
        'attestation_kind',a.attestation_kind,'status_code',a.status_code,
        'attestation_code',a.attestation_code,'reason_code',a.reason_code,
        'observed_execution_version',a.observed_execution_version,
        'observed_checkpoint_version',a.observed_checkpoint_version,
        'created_at',a.created_at
      ) FROM app.timeline_checkpoint_attestations a
      WHERE a.organization_id=p_org AND a.execution_id=v_execution.id
      ORDER BY a.created_at DESC,a.attestation_id DESC LIMIT 1
    ),
    'latest_verification',(
      SELECT jsonb_build_object(
        'schema_version',1,'verification_id',v.verification_id,
        'execution_id',v.execution_id,'checkpoint_id',v.checkpoint_id,
        'attestation_id',v.attestation_id,'advisor_actor_id',v.advisor_actor_id,
        'action',v.action,'reason_code',v.reason_code,
        'observed_execution_version',v.observed_execution_version,
        'observed_checkpoint_version',v.observed_checkpoint_version,
        'created_at',v.created_at
      ) FROM app.timeline_checkpoint_verifications v
      WHERE v.organization_id=p_org AND v.execution_id=v_execution.id
      ORDER BY v.created_at DESC,v.verification_id DESC LIMIT 1
    ),
    'reassessment',(
      SELECT jsonb_build_object(
        'schema_version',1,'reassessment_id',r.reassessment_id,
        'execution_id',r.execution_id,'checkpoint_id',r.checkpoint_id,
        'advisor_actor_id',r.advisor_actor_id,'trigger',r.trigger,
        'trigger_reference_id',r.trigger_reference_id,
        'accepted_database_date',r.accepted_database_date,
        'accepted_trigger_projection_sha256',r.accepted_trigger_projection_sha256,
        'handoff_schema_version',r.handoff_schema_version,
        'predecessor_case_id',r.predecessor_case_id,
        'predecessor_case_revision',r.predecessor_case_revision,
        'predecessor_decision_id',r.predecessor_decision_id,
        'predecessor_decision_receipt_id',r.predecessor_decision_receipt_id,
        'predecessor_timeline_plan_id',r.predecessor_timeline_plan_id,
        'predecessor_execution_id',r.predecessor_execution_id,
        'predecessor_checkpoint_id',r.predecessor_checkpoint_id,
        'owner_role',r.owner_role,'successor_status',r.successor_status,
        'created_at',r.created_at
      ) FROM app.timeline_reassessment_requests r
      WHERE r.organization_id=p_org AND r.execution_id=v_execution.id
    ),
    'current_action',v_current_action,
    'observed_date',v_observed_date,'activity',v_activity,
    'activity_total',v_activity_count,
    'activity_truncated',v_activity_count>jsonb_array_length(v_activity)
  ) INTO v_result;
  RETURN v_result;
END; $$;
"""


def upgrade() -> None:
    for statement in _split_statements(UPGRADE_SQL):
        op.execute(statement)
    for statement in _split_statements(AUTHORITY_SQL):
        op.execute(statement)


def downgrade() -> None:
    for table_name in TABLES:
        op.execute(f"LOCK TABLE app.{table_name} IN ACCESS EXCLUSIVE MODE")
        op.execute(f"ALTER TABLE app.{table_name} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE app.{table_name} DISABLE ROW LEVEL SECURITY")
    history_count = sum(
        int(
            op.get_bind().exec_driver_sql(
                f"SELECT count(*) FROM app.{table_name}"
            ).scalar_one()
        )
        for table_name in TABLES
    )
    if history_count:
        raise RuntimeError("refusing downgrade: timeline execution history exists")
    for signature in reversed(FUNCTION_SIGNATURES):
        op.execute(f"DROP FUNCTION {signature}")
    for table_name in reversed(TABLES):
        op.execute(f"DROP TABLE app.{table_name}")
    op.execute("DROP FUNCTION app.reject_timeline_execution_history_mutation()")
    op.execute(
        "ALTER TABLE app.timeline_plans "
        "DROP CONSTRAINT timeline_plans_execution_anchor_unique"
    )
    op.execute(
        "ALTER TABLE app.family_decisions "
        "DROP CONSTRAINT family_decisions_timeline_execution_anchor_unique"
    )


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
