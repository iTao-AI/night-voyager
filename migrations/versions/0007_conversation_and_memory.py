# ruff: noqa: E501
"""Create the governed collaboration and confirmed-fact authority boundary."""

from collections.abc import Sequence

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "collaboration_threads",
    "message_events",
    "memory_candidates",
    "memory_candidate_verifications",
    "confirmed_facts",
    "case_revision_confirmed_fact_refs",
)

DDL_SQL = r"""
CREATE TABLE app.collaboration_threads (
  organization_id uuid NOT NULL, id uuid NOT NULL, case_id uuid NOT NULL,
  created_by_actor_id uuid NOT NULL,
  created_by_role text NOT NULL CHECK (created_by_role='advisor'),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id,id),
  UNIQUE (organization_id,case_id),
  UNIQUE (organization_id,case_id,id),
  FOREIGN KEY (organization_id,case_id) REFERENCES app.student_cases(organization_id,id),
  FOREIGN KEY (organization_id,case_id,created_by_actor_id,created_by_role)
    REFERENCES app.student_case_participants(organization_id,case_id,actor_id,role)
);
CREATE TABLE app.message_events (
  organization_id uuid NOT NULL, id uuid NOT NULL, thread_id uuid NOT NULL,
  case_id uuid NOT NULL,
  sequence_no bigint NOT NULL CHECK (sequence_no BETWEEN 1 AND 1000),
  actor_id uuid NOT NULL,
  actor_role text NOT NULL CHECK (actor_role IN ('advisor','student','parent')),
  body text NOT NULL CHECK (octet_length(body) BETWEEN 1 AND 4096),
  content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
  request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id,id),
  UNIQUE (organization_id,case_id,id),
  UNIQUE (organization_id,thread_id,sequence_no),
  UNIQUE (organization_id,case_id,id,actor_id,actor_role),
  FOREIGN KEY (organization_id,case_id,thread_id)
    REFERENCES app.collaboration_threads(organization_id,case_id,id),
  FOREIGN KEY (organization_id,case_id,actor_id,actor_role)
    REFERENCES app.student_case_participants(organization_id,case_id,actor_id,role)
);
CREATE TABLE app.memory_candidates (
  organization_id uuid NOT NULL, id uuid NOT NULL, case_id uuid NOT NULL,
  case_revision integer NOT NULL CHECK (case_revision>0),
  message_event_id uuid NOT NULL, subject_actor_id uuid NOT NULL,
  subject_role text NOT NULL CHECK (subject_role IN ('student','parent')),
  proposing_actor_id uuid NOT NULL,
  proposing_role text NOT NULL CHECK (proposing_role IN ('student','parent')),
  fact_key text NOT NULL CHECK (fact_key IN (
    'student.intended_field','student.preferred_countries','student.intake',
    'family.risk_tolerance','family.japan_risk_accepted','family.budget'
  )),
  proposed_value jsonb NOT NULL,
  value_sha256 text NOT NULL CHECK (value_sha256 ~ '^[0-9a-f]{64}$'),
  request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
  provenance_kind text NOT NULL DEFAULT 'participant_proposal'
    CHECK (provenance_kind='participant_proposal'),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  expires_at timestamptz NOT NULL,
  PRIMARY KEY (organization_id,id),
  UNIQUE (organization_id,message_event_id),
  UNIQUE (organization_id,case_id,id),
  UNIQUE (organization_id,case_id,id,message_event_id,subject_actor_id,subject_role),
  CHECK (proposing_actor_id=subject_actor_id AND proposing_role=subject_role),
  CHECK ((subject_role='student' AND fact_key LIKE 'student.%') OR
         (subject_role='parent' AND fact_key LIKE 'family.%')),
  CHECK (expires_at=created_at+interval '7 days'),
  FOREIGN KEY (organization_id,case_id,case_revision)
    REFERENCES app.student_case_revisions(organization_id,case_id,revision),
  FOREIGN KEY (organization_id,case_id,message_event_id,proposing_actor_id,proposing_role)
    REFERENCES app.message_events(organization_id,case_id,id,actor_id,actor_role),
  FOREIGN KEY (organization_id,case_id,subject_actor_id,subject_role)
    REFERENCES app.student_case_participants(organization_id,case_id,actor_id,role),
  FOREIGN KEY (organization_id,case_id,proposing_actor_id,proposing_role)
    REFERENCES app.student_case_participants(organization_id,case_id,actor_id,role)
);
CREATE TABLE app.memory_candidate_verifications (
  organization_id uuid NOT NULL, id uuid NOT NULL, candidate_id uuid NOT NULL,
  case_id uuid NOT NULL, advisor_actor_id uuid NOT NULL,
  advisor_role text NOT NULL CHECK (advisor_role='advisor'),
  decision text NOT NULL CHECK (decision IN ('confirm','reject')),
  reason text NOT NULL CHECK (octet_length(reason) BETWEEN 1 AND 512),
  request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
  result_fact_id uuid,
  result_revision integer CHECK (result_revision IS NULL OR result_revision>0),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id,id),
  UNIQUE (organization_id,candidate_id),
  CHECK ((decision='confirm' AND result_fact_id IS NOT NULL AND result_revision IS NOT NULL) OR
         (decision='reject' AND result_fact_id IS NULL AND result_revision IS NULL)),
  FOREIGN KEY (organization_id,case_id,candidate_id)
    REFERENCES app.memory_candidates(organization_id,case_id,id),
  FOREIGN KEY (organization_id,case_id,advisor_actor_id,advisor_role)
    REFERENCES app.student_case_participants(organization_id,case_id,actor_id,role)
);
CREATE TABLE app.confirmed_facts (
  organization_id uuid NOT NULL, id uuid NOT NULL, case_id uuid NOT NULL,
  fact_key text NOT NULL CHECK (fact_key IN (
    'student.intended_field','student.preferred_countries','student.intake',
    'family.risk_tolerance','family.japan_risk_accepted','family.budget'
  )),
  value jsonb NOT NULL,
  value_sha256 text NOT NULL CHECK (value_sha256 ~ '^[0-9a-f]{64}$'),
  source_candidate_id uuid NOT NULL, source_message_event_id uuid NOT NULL,
  subject_actor_id uuid NOT NULL,
  subject_role text NOT NULL CHECK (subject_role IN ('student','parent')),
  confirming_advisor_actor_id uuid NOT NULL,
  confirming_advisor_role text NOT NULL CHECK (confirming_advisor_role='advisor'),
  supersedes_fact_id uuid, fact_version integer NOT NULL CHECK (fact_version>0),
  confirmed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id,id),
  UNIQUE (organization_id,case_id,id),
  UNIQUE (organization_id,case_id,fact_key,id),
  UNIQUE (organization_id,case_id,fact_key,fact_version),
  CHECK ((subject_role='student' AND fact_key LIKE 'student.%') OR
         (subject_role='parent' AND fact_key LIKE 'family.%')),
  FOREIGN KEY (organization_id,case_id,source_candidate_id,source_message_event_id,subject_actor_id,subject_role)
    REFERENCES app.memory_candidates(organization_id,case_id,id,message_event_id,subject_actor_id,subject_role),
  FOREIGN KEY (organization_id,case_id,subject_actor_id,subject_role)
    REFERENCES app.student_case_participants(organization_id,case_id,actor_id,role),
  FOREIGN KEY (organization_id,case_id,confirming_advisor_actor_id,confirming_advisor_role)
    REFERENCES app.student_case_participants(organization_id,case_id,actor_id,role),
  FOREIGN KEY (organization_id,case_id,fact_key,supersedes_fact_id)
    REFERENCES app.confirmed_facts(organization_id,case_id,fact_key,id)
);
CREATE UNIQUE INDEX confirmed_facts_one_successor
  ON app.confirmed_facts(organization_id,case_id,fact_key,supersedes_fact_id)
  WHERE supersedes_fact_id IS NOT NULL;
CREATE TABLE app.case_revision_confirmed_fact_refs (
  organization_id uuid NOT NULL, case_id uuid NOT NULL,
  case_revision integer NOT NULL CHECK (case_revision>0),
  fact_key text NOT NULL CHECK (fact_key IN (
    'student.intended_field','student.preferred_countries','student.intake',
    'family.risk_tolerance','family.japan_risk_accepted','family.budget'
  )),
  confirmed_fact_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id,case_id,case_revision,fact_key),
  FOREIGN KEY (organization_id,case_id,case_revision)
    REFERENCES app.student_case_revisions(organization_id,case_id,revision),
  FOREIGN KEY (organization_id,case_id,fact_key,confirmed_fact_id)
    REFERENCES app.confirmed_facts(organization_id,case_id,fact_key,id)
);

ALTER TABLE app.memory_candidate_verifications
  ADD CONSTRAINT memory_candidate_verifications_result_fact_fk
  FOREIGN KEY (organization_id,case_id,result_fact_id)
  REFERENCES app.confirmed_facts(organization_id,case_id,id)
  DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE app.memory_candidate_verifications
  ADD CONSTRAINT memory_candidate_verifications_result_revision_fk
  FOREIGN KEY (organization_id,case_id,result_revision)
  REFERENCES app.student_case_revisions(organization_id,case_id,revision)
  DEFERRABLE INITIALLY DEFERRED;

CREATE OR REPLACE FUNCTION app.guard_run_transition() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  IF OLD.is_current AND NOT NEW.is_current
     AND (to_jsonb(NEW)-'is_current')=(to_jsonb(OLD)-'is_current')
     AND EXISTS (
       SELECT 1
         FROM app.student_cases selected_case
         JOIN app.memory_candidate_verifications verification
           ON verification.organization_id=selected_case.organization_id
          AND verification.case_id=selected_case.id
          AND verification.decision='confirm'
          AND verification.result_revision=selected_case.current_revision
         JOIN app.case_revision_confirmed_fact_refs fact_ref
           ON fact_ref.organization_id=verification.organization_id
          AND fact_ref.case_id=verification.case_id
          AND fact_ref.case_revision=verification.result_revision
          AND fact_ref.confirmed_fact_id=verification.result_fact_id
        WHERE selected_case.organization_id=OLD.organization_id
          AND selected_case.id=OLD.case_id
          AND selected_case.current_revision=OLD.case_revision+1
     ) THEN
    RETURN NEW;
  END IF;
  IF OLD.state IN ('failed','blocked','review_required') THEN
    IF OLD.is_current AND NOT NEW.is_current AND NEW.state=OLD.state AND NEW.reason_code IS NOT DISTINCT FROM OLD.reason_code AND NEW.output_sha256 IS NOT DISTINCT FROM OLD.output_sha256 AND NEW.organization_id=OLD.organization_id AND NEW.id=OLD.id AND NEW.case_id=OLD.case_id AND NEW.case_revision=OLD.case_revision AND NEW.source_pack_id=OLD.source_pack_id AND NEW.source_pack_version=OLD.source_pack_version AND NEW.policy_version=OLD.policy_version AND NEW.evidence_projection_sha256=OLD.evidence_projection_sha256 THEN RETURN NEW; END IF;
    RAISE EXCEPTION USING ERRCODE='NV005', MESSAGE='terminal planning run is immutable';
  END IF;
  IF NOT ((OLD.state='draft' AND NEW.state IN ('collecting_evidence','failed')) OR (OLD.state='collecting_evidence' AND NEW.state IN ('synthesizing','failed')) OR (OLD.state='synthesizing' AND NEW.state IN ('failed','blocked','review_required'))) THEN
    RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid planning run transition';
  END IF;
  IF NEW.organization_id<>OLD.organization_id OR NEW.id<>OLD.id OR NEW.case_id<>OLD.case_id OR NEW.case_revision<>OLD.case_revision OR NEW.source_pack_id<>OLD.source_pack_id OR NEW.source_pack_version<>OLD.source_pack_version OR NEW.policy_version<>OLD.policy_version OR NEW.evidence_projection_sha256<>OLD.evidence_projection_sha256 THEN
    RAISE EXCEPTION USING ERRCODE='NV005', MESSAGE='planning run inputs are immutable';
  END IF;
  RETURN NEW;
END; $$;

ALTER TABLE app.collaboration_threads ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.collaboration_threads FORCE ROW LEVEL SECURITY;
CREATE POLICY collaboration_threads_tenant_isolation ON app.collaboration_threads
  USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid)
  WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);
ALTER TABLE app.message_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.message_events FORCE ROW LEVEL SECURITY;
CREATE POLICY message_events_tenant_isolation ON app.message_events
  USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid)
  WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);
ALTER TABLE app.memory_candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.memory_candidates FORCE ROW LEVEL SECURITY;
CREATE POLICY memory_candidates_tenant_isolation ON app.memory_candidates
  USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid)
  WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);
ALTER TABLE app.memory_candidate_verifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.memory_candidate_verifications FORCE ROW LEVEL SECURITY;
CREATE POLICY memory_candidate_verifications_tenant_isolation ON app.memory_candidate_verifications
  USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid)
  WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);
ALTER TABLE app.confirmed_facts ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.confirmed_facts FORCE ROW LEVEL SECURITY;
CREATE POLICY confirmed_facts_tenant_isolation ON app.confirmed_facts
  USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid)
  WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);
ALTER TABLE app.case_revision_confirmed_fact_refs ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.case_revision_confirmed_fact_refs FORCE ROW LEVEL SECURITY;
CREATE POLICY case_revision_confirmed_fact_refs_tenant_isolation ON app.case_revision_confirmed_fact_refs
  USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid)
  WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);

CREATE FUNCTION app.reject_collaboration_mutation() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='immutable collaboration authority record';
END; $$;
CREATE TRIGGER collaboration_threads_immutable BEFORE UPDATE OR DELETE ON app.collaboration_threads FOR EACH ROW EXECUTE FUNCTION app.reject_collaboration_mutation();
CREATE TRIGGER message_events_immutable BEFORE UPDATE OR DELETE ON app.message_events FOR EACH ROW EXECUTE FUNCTION app.reject_collaboration_mutation();
CREATE TRIGGER memory_candidates_immutable BEFORE UPDATE OR DELETE ON app.memory_candidates FOR EACH ROW EXECUTE FUNCTION app.reject_collaboration_mutation();
CREATE TRIGGER memory_candidate_verifications_immutable BEFORE UPDATE OR DELETE ON app.memory_candidate_verifications FOR EACH ROW EXECUTE FUNCTION app.reject_collaboration_mutation();
CREATE TRIGGER confirmed_facts_immutable BEFORE UPDATE OR DELETE ON app.confirmed_facts FOR EACH ROW EXECUTE FUNCTION app.reject_collaboration_mutation();
CREATE TRIGGER case_revision_confirmed_fact_refs_immutable BEFORE UPDATE OR DELETE ON app.case_revision_confirmed_fact_refs FOR EACH ROW EXECUTE FUNCTION app.reject_collaboration_mutation();

CREATE FUNCTION app.serialize_agent_task_case_revision() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE selected_case app.student_cases%ROWTYPE;
BEGIN
  SELECT * INTO selected_case FROM app.student_cases selected_case_row
   WHERE selected_case_row.organization_id=NEW.organization_id
     AND selected_case_row.id=NEW.case_id
   FOR SHARE;
  IF NOT FOUND OR selected_case.state<>'planning'
     OR selected_case.current_revision IS DISTINCT FROM NEW.case_revision THEN
    RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='task input is stale';
  END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER agent_tasks_collaboration_case_revision
  BEFORE INSERT ON app.agent_tasks
  FOR EACH ROW EXECUTE FUNCTION app.serialize_agent_task_case_revision();

CREATE FUNCTION app.assert_collaboration_context(p_org uuid,p_actor uuid,p_role text) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  IF p_role NOT IN ('advisor','student','parent') THEN
    RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='actor context mismatch';
  END IF;
  PERFORM app.assert_m3b_context(p_org,p_actor,p_role);
END; $$;

CREATE FUNCTION app.validate_collaboration_message(p_body text) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  IF p_body IS NULL OR octet_length(p_body) NOT BETWEEN 1 AND 4096
     OR p_body ~ '[[:cntrl:]]'
     OR p_body ~* '(api[_-]?key|password|passwd|secret|access[_-]?token|bearer)[[:space:]]*[:=]'
     OR p_body ~ '-----BEGIN [A-Z ]*PRIVATE KEY-----'
     OR p_body ~ '(^|[[:space:]])(/(Users|home|etc|private|var|tmp)/[^[:space:]]+|[A-Za-z]:\\[^[:space:]]+)'
     OR p_body ~ 'file://'
     OR p_body ~* '[a-z][a-z0-9+.-]*://[^[:space:]/]+:[^[:space:]@]+@'
     OR p_body ~ E'(&&|\\|\\||\\$\\(|`)'
     OR p_body ~* '(^|[[:space:]])(sudo|rm|bash|sh|zsh|curl|wget|python)[[:space:]]+' THEN
    RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid collaboration message';
  END IF;
END; $$;

CREATE FUNCTION app.validate_collaboration_fact(p_role text,p_fact_key text,p_value jsonb) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE value_text text; item_count integer; distinct_count integer; sorted_value jsonb;
BEGIN
  IF p_role IS NULL OR p_fact_key IS NULL OR p_value IS NULL THEN
    RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='unsupported collaboration fact';
  END IF;
  IF (p_role='student' AND p_fact_key NOT IN ('student.intended_field','student.preferred_countries','student.intake'))
     OR (p_role='parent' AND p_fact_key NOT IN ('family.risk_tolerance','family.japan_risk_accepted','family.budget'))
     OR p_role NOT IN ('student','parent') THEN
    RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='unsupported collaboration fact';
  END IF;

  IF p_fact_key='student.intended_field' THEN
    IF jsonb_typeof(p_value)<>'string' THEN
      RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='unsafe collaboration fact value';
    END IF;
    value_text := p_value #>> '{}';
    IF octet_length(value_text) NOT BETWEEN 1 AND 160
       OR value_text ~ '[[:cntrl:]]'
       OR value_text ~* '(api[_-]?key|password|passwd|secret|access[_-]?token|bearer)[[:space:]]*[:=]'
       OR value_text ~ '-----BEGIN [A-Z ]*PRIVATE KEY-----'
       OR value_text ~ '/(Users|home|etc|private|var|tmp)/|file://|[A-Za-z]:\\|://'
       OR value_text ~ E'(&&|\\|\\||\\$\\(|`)'
       OR value_text ~* '(^|[[:space:]])(sudo|rm|bash|sh|zsh|curl|wget|python)[[:space:]]+' THEN
      RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='unsafe collaboration fact value';
    END IF;
  ELSIF p_fact_key='student.preferred_countries' THEN
    IF jsonb_typeof(p_value)<>'array' OR jsonb_array_length(p_value) NOT BETWEEN 1 AND 3 THEN
      RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='unsafe collaboration fact value';
    END IF;
    SELECT count(*),count(DISTINCT value),jsonb_agg(to_jsonb(value) ORDER BY value)
      INTO item_count,distinct_count,sorted_value
      FROM jsonb_array_elements_text(p_value) AS value;
    IF item_count<>distinct_count OR p_value<>sorted_value OR EXISTS (
      SELECT 1 FROM jsonb_array_elements_text(p_value) AS country(value)
      WHERE value NOT IN ('australia','japan','malaysia')
    ) THEN
      RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='unsafe collaboration fact value';
    END IF;
  ELSIF p_fact_key='student.intake' THEN
    IF jsonb_typeof(p_value)<>'string' THEN
      RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='unsafe collaboration fact value';
    END IF;
    value_text := p_value #>> '{}';
    IF value_text !~ '^[0-9]{4}-(0[1-9]|1[0-2])$' THEN
      RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='unsafe collaboration fact value';
    END IF;
  ELSIF p_fact_key='family.risk_tolerance' THEN
    IF jsonb_typeof(p_value)<>'string' OR (p_value #>> '{}') NOT IN ('low','medium','high') THEN
      RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='unsafe collaboration fact value';
    END IF;
  ELSIF p_fact_key='family.japan_risk_accepted' THEN
    IF jsonb_typeof(p_value)<>'boolean' THEN
      RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='unsafe collaboration fact value';
    END IF;
  ELSIF p_fact_key='family.budget' THEN
    IF jsonb_typeof(p_value)<>'object'
       OR (SELECT count(*) FROM jsonb_object_keys(p_value))<>7
       OR NOT (p_value ?& ARRAY[
         'schema_version','currency','period','preferred_minor',
         'hard_ceiling_minor','elasticity_bps','refused'
       ])
       OR jsonb_typeof(p_value->'schema_version')<>'number'
       OR p_value->>'schema_version'<>'1'
       OR jsonb_typeof(p_value->'currency')<>'string'
       OR p_value->>'currency'<>'CNY'
       OR jsonb_typeof(p_value->'period')<>'string'
       OR p_value->>'period'<>'program_total'
       OR jsonb_typeof(p_value->'refused')<>'boolean'
       OR jsonb_typeof(p_value->'elasticity_bps')<>'number'
       OR (p_value->>'elasticity_bps') !~ '^[0-9]+$'
       OR (p_value->>'elasticity_bps')::numeric NOT BETWEEN 0 AND 2500 THEN
      RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='unsafe collaboration fact value';
    END IF;
    IF (p_value->>'refused')::boolean THEN
      IF jsonb_typeof(p_value->'preferred_minor')<>'null' OR jsonb_typeof(p_value->'hard_ceiling_minor')<>'null' THEN
        RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='unsafe collaboration fact value';
      END IF;
    ELSIF jsonb_typeof(p_value->'preferred_minor')<>'number'
       OR jsonb_typeof(p_value->'hard_ceiling_minor')<>'number'
       OR (p_value->>'preferred_minor') !~ '^[1-9][0-9]*$'
       OR (p_value->>'hard_ceiling_minor') !~ '^[1-9][0-9]*$'
       OR (p_value->>'preferred_minor')::numeric>(p_value->>'hard_ceiling_minor')::numeric THEN
      RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='unsafe collaboration fact value';
    END IF;
  END IF;
END; $$;
"""

PLANNING_PERSISTENCE_LOCK_SQL = r"""
CREATE OR REPLACE FUNCTION app.persist_planning_result(p_org uuid,p_run uuid,p_case uuid,p_revision integer,p_pack uuid,p_version integer,p_policy text,p_evidence_hash text,p_state text,p_reason text,p_output_hash text,p_supersedes uuid,p_output jsonb) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE item jsonb; dimension jsonb; evidence_use jsonb; cost_item jsonb; ranking_item jsonb; route_index integer := 0; dimension_index integer := 0; cost_index integer := 0; ranking_index integer := 0; route_uuid uuid; dimension_uuid uuid; selected_case app.student_cases%ROWTYPE;
BEGIN
 PERFORM app.assert_context(p_org);
 IF p_state NOT IN ('failed','blocked','review_required') THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='result must be terminal'; END IF;
 SELECT * INTO selected_case FROM app.student_cases selected_case_row WHERE selected_case_row.organization_id=p_org AND selected_case_row.id=p_case FOR UPDATE;
 IF NOT FOUND OR selected_case.current_revision IS DISTINCT FROM p_revision OR selected_case.state IS DISTINCT FROM 'planning' THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='case revision or state is stale'; END IF;
 IF p_supersedes IS NOT NULL THEN UPDATE app.planning_runs SET is_current=false WHERE organization_id=p_org AND id=p_supersedes AND is_current=true; IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='superseded run is stale'; END IF; END IF;
 INSERT INTO app.planning_runs(organization_id,id,case_id,case_revision,source_pack_id,source_pack_version,policy_version,evidence_projection_sha256,state,reason_code,output_sha256,supersedes_run_id,is_current) VALUES(p_org,p_run,p_case,p_revision,p_pack,p_version,p_policy,p_evidence_hash,'synthesizing',NULL,NULL,p_supersedes,true);
 FOR item IN SELECT * FROM jsonb_array_elements(p_output->'routes') LOOP
  route_index := route_index + 1;
  route_uuid := ('71000000-0000-0000-0000-'||lpad(route_index::text,12,'0'))::uuid;
  INSERT INTO app.planning_routes VALUES(p_org,p_run,route_uuid,item->>'country',item->>'outcome',item->>'reason_code');
  FOR dimension IN SELECT * FROM jsonb_array_elements(item->'dimensions') LOOP
   dimension_index := dimension_index + 1;
   dimension_uuid := ('72000000-0000-0000-0000-'||lpad(dimension_index::text,12,'0'))::uuid;
   INSERT INTO app.comparison_dimensions VALUES(p_org,p_run,route_uuid,dimension_uuid,dimension->>'dimension_key',dimension->>'outcome',dimension->>'reason_code');
   FOR evidence_use IN SELECT * FROM jsonb_array_elements(dimension->'evidence_uses') LOOP
    INSERT INTO app.comparison_dimension_evidence_refs VALUES(p_org,p_run,route_uuid,dimension_uuid,(evidence_use->>'evidence_id')::uuid,evidence_use->>'role');
   END LOOP;
  END LOOP;
 END LOOP;
 FOR cost_item IN SELECT * FROM jsonb_array_elements(p_output->'costs') LOOP
  cost_index := cost_index + 1;
  INSERT INTO app.cost_evidence VALUES(p_org,p_run,('73000000-0000-0000-0000-'||lpad(cost_index::text,12,'0'))::uuid,cost_item->>'country',cost_item->>'intake',cost_item->>'period',cost_item->>'currency',(cost_item->>'tuition_minor')::bigint,(cost_item->>'living_minor')::bigint,(cost_item->>'fx_rate')::numeric,cost_item->>'fx_source',(cost_item->>'fx_date')::date,(cost_item->>'tuition_evidence_id')::uuid,(cost_item->>'living_evidence_id')::uuid,(cost_item->>'fx_evidence_id')::uuid);
 END LOOP;
 FOR ranking_item IN SELECT * FROM jsonb_array_elements(p_output->'rankings') LOOP
  ranking_index := ranking_index + 1;
  INSERT INTO app.ranking_evidence VALUES(p_org,p_run,('74000000-0000-0000-0000-'||lpad(ranking_index::text,12,'0'))::uuid,ranking_item->>'country',ranking_item->>'ranking_system',(ranking_item->>'rank')::integer,(ranking_item->>'publication_year')::integer,(ranking_item->>'evidence_id')::uuid);
 END LOOP;
 UPDATE app.planning_runs SET state=p_state,reason_code=p_reason,output_sha256=p_output_hash WHERE organization_id=p_org AND id=p_run;
END; $$;
"""

MUTATION_SQL = r"""
CREATE FUNCTION app.create_collaboration_thread(p_org uuid,p_actor uuid,p_role text,p_case uuid,p_thread uuid,p_request_sha256 text,p_key_sha256 text) RETURNS TABLE(schema_version integer,thread_id uuid,case_id uuid,created_by_actor_id uuid,created_at timestamptz,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE prior app.idempotency_records%ROWTYPE; selected app.collaboration_threads%ROWTYPE; selected_case app.student_cases%ROWTYPE;
BEGIN
  IF p_org IS NULL OR p_actor IS NULL OR p_role IS NULL OR p_case IS NULL
     OR p_thread IS NULL OR p_request_sha256 IS NULL OR p_key_sha256 IS NULL
     OR p_role<>'advisor' OR p_request_sha256 !~ '^[0-9a-f]{64}$'
     OR p_key_sha256 !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid collaboration thread contract';
  END IF;
  PERFORM app.assert_collaboration_context(p_org,p_actor,p_role);
  PERFORM pg_advisory_xact_lock(hashtextextended(p_org::text||':'||p_actor::text||':collaboration_thread_create:'||p_key_sha256,0));
  SELECT * INTO prior FROM app.idempotency_records ledger
   WHERE ledger.organization_id=p_org AND ledger.actor_id=p_actor
     AND ledger.operation='collaboration_thread_create' AND ledger.key_sha256=p_key_sha256;
  IF FOUND THEN
    IF prior.request_sha256<>p_request_sha256 OR prior.response_kind<>'collaboration_thread' THEN
      RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='idempotency request mismatch';
    END IF;
    SELECT * INTO selected FROM app.collaboration_threads thread
     WHERE thread.organization_id=p_org AND thread.id=prior.response_id;
    IF NOT FOUND THEN RAISE EXCEPTION USING MESSAGE='idempotency response unavailable'; END IF;
    RETURN QUERY SELECT 1,selected.id,selected.case_id,selected.created_by_actor_id,selected.created_at,true;
    RETURN;
  END IF;

  SELECT * INTO selected_case FROM app.student_cases selected_case_row
   WHERE selected_case_row.organization_id=p_org AND selected_case_row.id=p_case FOR UPDATE;
  IF NOT FOUND OR NOT EXISTS (
    SELECT 1 FROM app.student_case_participants participant
     WHERE participant.organization_id=p_org AND participant.case_id=p_case
       AND participant.actor_id=p_actor AND participant.role='advisor'
  ) THEN
    RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='collaboration resource unavailable';
  END IF;
  SELECT * INTO selected FROM app.collaboration_threads thread
   WHERE thread.organization_id=p_org AND thread.case_id=p_case;
  IF NOT FOUND THEN
    INSERT INTO app.collaboration_threads(
      organization_id,id,case_id,created_by_actor_id,created_by_role
    ) VALUES(p_org,p_thread,p_case,p_actor,'advisor')
    RETURNING * INTO selected;
  END IF;
  INSERT INTO app.idempotency_records
    VALUES(p_org,p_actor,'collaboration_thread_create',p_key_sha256,p_request_sha256,'collaboration_thread',selected.id,clock_timestamp());
  RETURN QUERY SELECT 1,selected.id,selected.case_id,selected.created_by_actor_id,selected.created_at,false;
END; $$;

CREATE FUNCTION app.append_collaboration_message(p_org uuid,p_actor uuid,p_role text,p_thread uuid,p_message uuid,p_body text,p_content_sha256 text,p_request_sha256 text,p_key_sha256 text) RETURNS TABLE(schema_version integer,message_event_id uuid,thread_id uuid,case_id uuid,sequence_no bigint,actor_id uuid,actor_role text,body text,content_sha256 text,created_at timestamptz,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE prior app.idempotency_records%ROWTYPE; selected app.message_events%ROWTYPE; selected_thread app.collaboration_threads%ROWTYPE; next_sequence bigint;
BEGIN
  IF p_org IS NULL OR p_actor IS NULL OR p_role IS NULL OR p_thread IS NULL
     OR p_message IS NULL OR p_body IS NULL OR p_content_sha256 IS NULL
     OR p_request_sha256 IS NULL OR p_key_sha256 IS NULL
     OR p_content_sha256 !~ '^[0-9a-f]{64}$'
     OR p_request_sha256 !~ '^[0-9a-f]{64}$'
     OR p_key_sha256 !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid collaboration message contract';
  END IF;
  PERFORM app.assert_collaboration_context(p_org,p_actor,p_role);
  PERFORM app.validate_collaboration_message(p_body);
  PERFORM pg_advisory_xact_lock(hashtextextended(p_org::text||':'||p_actor::text||':collaboration_message_append:'||p_key_sha256,0));
  SELECT * INTO prior FROM app.idempotency_records ledger
   WHERE ledger.organization_id=p_org AND ledger.actor_id=p_actor
     AND ledger.operation='collaboration_message_append' AND ledger.key_sha256=p_key_sha256;
  IF FOUND THEN
    IF prior.request_sha256<>p_request_sha256 OR prior.response_kind<>'collaboration_message' THEN
      RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='idempotency request mismatch';
    END IF;
    SELECT * INTO selected FROM app.message_events event
     WHERE event.organization_id=p_org AND event.id=prior.response_id;
    IF NOT FOUND THEN RAISE EXCEPTION USING MESSAGE='idempotency response unavailable'; END IF;
    RETURN QUERY SELECT 1,selected.id,selected.thread_id,selected.case_id,selected.sequence_no,selected.actor_id,selected.actor_role,selected.body,selected.content_sha256,selected.created_at,true;
    RETURN;
  END IF;

  SELECT * INTO selected_thread FROM app.collaboration_threads thread
   WHERE thread.organization_id=p_org AND thread.id=p_thread FOR UPDATE;
  IF NOT FOUND OR NOT EXISTS (
    SELECT 1 FROM app.student_case_participants participant
     WHERE participant.organization_id=p_org AND participant.case_id=selected_thread.case_id
       AND participant.actor_id=p_actor AND participant.role=p_role
  ) THEN
    RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='collaboration resource unavailable';
  END IF;
  IF (SELECT count(*) FROM app.message_events event
       WHERE event.organization_id=p_org AND event.thread_id=p_thread)>=1000 THEN
    RAISE EXCEPTION USING ERRCODE='NV012', MESSAGE='collaboration thread event limit reached';
  END IF;
  SELECT COALESCE(max(event.sequence_no),0)+1 INTO next_sequence
    FROM app.message_events event
   WHERE event.organization_id=p_org AND event.thread_id=p_thread;
  INSERT INTO app.message_events(
    organization_id,id,thread_id,case_id,sequence_no,actor_id,actor_role,
    body,content_sha256,request_sha256
  ) VALUES(
    p_org,p_message,p_thread,selected_thread.case_id,next_sequence,p_actor,p_role,
    p_body,p_content_sha256,p_request_sha256
  ) RETURNING * INTO selected;
  INSERT INTO app.idempotency_records
    VALUES(p_org,p_actor,'collaboration_message_append',p_key_sha256,p_request_sha256,'collaboration_message',selected.id,clock_timestamp());
  RETURN QUERY SELECT 1,selected.id,selected.thread_id,selected.case_id,selected.sequence_no,selected.actor_id,selected.actor_role,selected.body,selected.content_sha256,selected.created_at,false;
END; $$;

CREATE FUNCTION app.propose_memory_candidate(p_org uuid,p_actor uuid,p_role text,p_message uuid,p_candidate uuid,p_case_revision integer,p_fact_key text,p_value jsonb,p_value_sha256 text,p_request_sha256 text,p_key_sha256 text) RETURNS TABLE(schema_version integer,fact_key text,value jsonb,state text,created_at timestamptz,expires_at timestamptz,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE prior app.idempotency_records%ROWTYPE; source_identity app.message_events%ROWTYPE; source_event app.message_events%ROWTYPE; selected_case app.student_cases%ROWTYPE; selected app.memory_candidates%ROWTYPE; terminal_decision text; projected_state text; created timestamptz;
BEGIN
  IF p_org IS NULL OR p_actor IS NULL OR p_role IS NULL OR p_message IS NULL
     OR p_candidate IS NULL OR p_case_revision IS NULL OR p_fact_key IS NULL
     OR p_value IS NULL OR p_value_sha256 IS NULL OR p_request_sha256 IS NULL
     OR p_key_sha256 IS NULL OR p_case_revision<=0
     OR p_value_sha256 !~ '^[0-9a-f]{64}$'
     OR p_request_sha256 !~ '^[0-9a-f]{64}$'
     OR p_key_sha256 !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid memory candidate contract';
  END IF;
  PERFORM app.assert_collaboration_context(p_org,p_actor,p_role);
  PERFORM app.validate_collaboration_fact(p_role,p_fact_key,p_value);
  PERFORM pg_advisory_xact_lock(hashtextextended(p_org::text||':'||p_actor::text||':memory_candidate_propose:'||p_key_sha256,0));
  SELECT * INTO prior FROM app.idempotency_records ledger
   WHERE ledger.organization_id=p_org AND ledger.actor_id=p_actor
     AND ledger.operation='memory_candidate_propose' AND ledger.key_sha256=p_key_sha256;
  IF FOUND THEN
    IF prior.request_sha256<>p_request_sha256 OR prior.response_kind<>'memory_candidate' THEN
      RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='idempotency request mismatch';
    END IF;
    SELECT * INTO selected FROM app.memory_candidates candidate
     WHERE candidate.organization_id=p_org AND candidate.id=prior.response_id;
    IF NOT FOUND THEN RAISE EXCEPTION USING MESSAGE='idempotency response unavailable'; END IF;
    SELECT verification.decision INTO terminal_decision
      FROM app.memory_candidate_verifications verification
     WHERE verification.organization_id=p_org AND verification.candidate_id=selected.id;
    SELECT * INTO selected_case FROM app.student_cases selected_case_row
     WHERE selected_case_row.organization_id=p_org AND selected_case_row.id=selected.case_id;
    projected_state := CASE
      WHEN terminal_decision='confirm' THEN 'confirmed'
      WHEN terminal_decision='reject' THEN 'rejected'
      WHEN selected.case_revision<>selected_case.current_revision THEN 'stale'
      WHEN selected.expires_at<=clock_timestamp() THEN 'expired'
      ELSE 'pending' END;
    RETURN QUERY SELECT 1,selected.fact_key,selected.proposed_value,projected_state,selected.created_at,selected.expires_at,true;
    RETURN;
  END IF;

  SELECT * INTO source_identity FROM app.message_events source_identity_row
   WHERE source_identity_row.organization_id=p_org AND source_identity_row.id=p_message;
  IF NOT FOUND OR source_identity.actor_id<>p_actor OR source_identity.actor_role<>p_role OR p_role NOT IN ('student','parent') THEN
    RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='collaboration resource unavailable';
  END IF;
  SELECT * INTO selected_case FROM app.student_cases selected_case_row
   WHERE selected_case_row.organization_id=p_org
     AND selected_case_row.id=source_identity.case_id FOR SHARE;
  IF NOT FOUND OR selected_case.current_revision IS DISTINCT FROM p_case_revision THEN
    RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='Case revision is stale';
  END IF;
  SELECT * INTO source_event FROM app.message_events source_event_row
   WHERE source_event_row.organization_id=p_org
     AND source_event_row.case_id=source_identity.case_id AND source_event_row.id=p_message
   FOR UPDATE;
  IF NOT FOUND OR source_event.actor_id<>p_actor OR source_event.actor_role<>p_role OR NOT EXISTS (
    SELECT 1 FROM app.student_case_participants participant
     WHERE participant.organization_id=p_org AND participant.case_id=source_event.case_id
       AND participant.actor_id=p_actor AND participant.role=p_role
  ) THEN
    RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='collaboration resource unavailable';
  END IF;
  SELECT * INTO selected FROM app.memory_candidates candidate
   WHERE candidate.organization_id=p_org AND candidate.message_event_id=p_message;
  IF FOUND THEN
    IF selected.case_revision<>p_case_revision OR selected.fact_key<>p_fact_key
       OR selected.value_sha256<>p_value_sha256
       OR selected.request_sha256 IS DISTINCT FROM p_request_sha256
       OR selected.proposing_actor_id<>p_actor
       OR selected.proposing_role<>p_role THEN
      RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='source message proposal mismatch';
    END IF;
  ELSE
    created := clock_timestamp();
    INSERT INTO app.memory_candidates(
      organization_id,id,case_id,case_revision,message_event_id,
      subject_actor_id,subject_role,proposing_actor_id,proposing_role,
      fact_key,proposed_value,value_sha256,request_sha256,created_at,expires_at
    ) VALUES(
      p_org,p_candidate,source_event.case_id,p_case_revision,p_message,
      p_actor,p_role,p_actor,p_role,p_fact_key,p_value,p_value_sha256,p_request_sha256,
      created,created+interval '7 days'
    ) RETURNING * INTO selected;
  END IF;
  SELECT verification.decision INTO terminal_decision
    FROM app.memory_candidate_verifications verification
   WHERE verification.organization_id=p_org AND verification.candidate_id=selected.id;
  projected_state := CASE
    WHEN terminal_decision='confirm' THEN 'confirmed'
    WHEN terminal_decision='reject' THEN 'rejected'
    WHEN selected.case_revision<>selected_case.current_revision THEN 'stale'
    WHEN selected.expires_at<=clock_timestamp() THEN 'expired'
    ELSE 'pending' END;
  INSERT INTO app.idempotency_records
    VALUES(p_org,p_actor,'memory_candidate_propose',p_key_sha256,p_request_sha256,'memory_candidate',selected.id,clock_timestamp());
  RETURN QUERY SELECT 1,selected.fact_key,selected.proposed_value,projected_state,selected.created_at,selected.expires_at,false;
END; $$;

CREATE FUNCTION app.verify_memory_candidate(p_org uuid,p_actor uuid,p_candidate uuid,p_expected_revision integer,p_decision text,p_reason text,p_verification uuid,p_fact uuid,p_request_sha256 text,p_key_sha256 text) RETURNS TABLE(verification_id uuid,candidate_id uuid,decision text,result_fact_id uuid,result_revision integer,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE prior app.idempotency_records%ROWTYPE; selected_case app.student_cases%ROWTYPE; candidate app.memory_candidates%ROWTYPE; existing app.memory_candidate_verifications%ROWTYPE; prior_fact app.confirmed_facts%ROWTYPE; current_run app.planning_runs%ROWTYPE; current_revision app.student_case_revisions%ROWTYPE; resolved_case uuid; current_run_count integer; next_revision integer; next_fact_version integer; next_student jsonb; next_family jsonb;
BEGIN
  IF p_org IS NULL OR p_actor IS NULL OR p_candidate IS NULL
     OR p_expected_revision IS NULL OR p_decision IS NULL OR p_reason IS NULL
     OR p_verification IS NULL OR p_request_sha256 IS NULL OR p_key_sha256 IS NULL
     OR p_expected_revision<=0 OR p_decision NOT IN ('confirm','reject')
     OR octet_length(p_reason) NOT BETWEEN 1 AND 512 OR p_reason ~ '[[:cntrl:]]'
     OR p_reason ~* '(api[_-]?key|password|passwd|secret|access[_-]?token|bearer)[[:space:]]*[:=]'
     OR p_reason ~ '-----BEGIN [A-Z ]*PRIVATE KEY-----'
     OR p_reason ~ '/(Users|home|etc|private|var|tmp)/|file://|[A-Za-z]:\\|://'
     OR p_reason ~ E'(&&|\\|\\||\\$\\(|`)'
     OR p_reason ~* '(^|[[:space:]])(sudo|rm|bash|sh|zsh|curl|wget|python)[[:space:]]+'
     OR p_request_sha256 !~ '^[0-9a-f]{64}$' OR p_key_sha256 !~ '^[0-9a-f]{64}$'
     OR (p_decision='confirm' AND p_fact IS NULL)
     OR (p_decision='reject' AND p_fact IS NOT NULL) THEN
    RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid memory candidate verification contract';
  END IF;
  PERFORM app.assert_collaboration_context(p_org,p_actor,'advisor');
  PERFORM pg_advisory_xact_lock(hashtextextended(p_org::text||':'||p_actor::text||':memory_candidate_verify:'||p_key_sha256,0));
  SELECT * INTO prior FROM app.idempotency_records ledger
   WHERE ledger.organization_id=p_org AND ledger.actor_id=p_actor
     AND ledger.operation='memory_candidate_verify' AND ledger.key_sha256=p_key_sha256;
  IF FOUND THEN
    IF prior.request_sha256<>p_request_sha256 OR prior.response_kind<>'memory_candidate_verification' THEN
      RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='idempotency request mismatch';
    END IF;
    SELECT * INTO existing FROM app.memory_candidate_verifications verification
     WHERE verification.organization_id=p_org AND verification.id=prior.response_id;
    IF NOT FOUND THEN RAISE EXCEPTION USING MESSAGE='idempotency response unavailable'; END IF;
    RETURN QUERY SELECT existing.id,existing.candidate_id,existing.decision,existing.result_fact_id,existing.result_revision,true;
    RETURN;
  END IF;

  SELECT candidate_row.case_id INTO resolved_case FROM app.memory_candidates candidate_row
   WHERE candidate_row.organization_id=p_org AND candidate_row.id=p_candidate;
  IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='collaboration resource unavailable'; END IF;
  SELECT * INTO selected_case FROM app.student_cases selected_case_row
   WHERE selected_case_row.organization_id=p_org AND selected_case_row.id=resolved_case FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='collaboration resource unavailable'; END IF;
  SELECT * INTO candidate FROM app.memory_candidates candidate_row
   WHERE candidate_row.organization_id=p_org AND candidate_row.case_id=resolved_case
     AND candidate_row.id=p_candidate FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='collaboration resource unavailable'; END IF;
  SELECT * INTO prior_fact FROM app.confirmed_facts AS fact
   WHERE fact.organization_id=p_org AND fact.case_id=resolved_case
     AND fact.fact_key=candidate.fact_key
     AND NOT EXISTS (
       SELECT 1 FROM app.confirmed_facts AS successor
        WHERE successor.organization_id=fact.organization_id
          AND successor.case_id=fact.case_id
          AND successor.fact_key=fact.fact_key
          AND successor.supersedes_fact_id=fact.id
     ) FOR UPDATE;
  SELECT count(*) INTO current_run_count FROM app.planning_runs planning_run
   WHERE planning_run.organization_id=p_org AND planning_run.case_id=resolved_case
     AND planning_run.is_current;
  IF current_run_count>1 THEN
    RAISE EXCEPTION USING MESSAGE='multiple current planning runs';
  END IF;
  SELECT * INTO current_run FROM app.planning_runs planning_run
   WHERE planning_run.organization_id=p_org AND planning_run.case_id=resolved_case
     AND planning_run.is_current FOR UPDATE;
  IF NOT EXISTS (
    SELECT 1 FROM app.student_case_participants participant
     WHERE participant.organization_id=p_org AND participant.case_id=resolved_case
       AND participant.actor_id=p_actor AND participant.role='advisor'
  ) THEN
    RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='collaboration resource unavailable';
  END IF;
  SELECT * INTO existing FROM app.memory_candidate_verifications verification
   WHERE verification.organization_id=p_org AND verification.candidate_id=p_candidate;
  IF FOUND THEN RAISE EXCEPTION USING ERRCODE='NV012', MESSAGE='memory candidate is terminal'; END IF;
  IF candidate.case_revision<>p_expected_revision OR selected_case.current_revision IS DISTINCT FROM p_expected_revision THEN
    RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='memory candidate is stale';
  END IF;
  IF candidate.expires_at<=clock_timestamp() THEN
    RAISE EXCEPTION USING ERRCODE='NV013', MESSAGE='memory candidate is expired';
  END IF;
  IF selected_case.state NOT IN ('intake','planning') THEN
    RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='Case state is stale';
  END IF;
  PERFORM app.validate_collaboration_fact(candidate.subject_role,candidate.fact_key,candidate.proposed_value);

  IF p_decision='reject' THEN
    INSERT INTO app.memory_candidate_verifications(
      organization_id,id,candidate_id,case_id,advisor_actor_id,advisor_role,
      decision,reason,request_sha256,result_fact_id,result_revision
    ) VALUES(p_org,p_verification,p_candidate,resolved_case,p_actor,'advisor','reject',p_reason,p_request_sha256,NULL,NULL);
    INSERT INTO app.audit_events
      VALUES(p_org,gen_random_uuid(),resolved_case,p_actor,'memory_candidate_rejected',p_verification,jsonb_build_object('candidate_id',p_candidate),clock_timestamp());
    INSERT INTO app.idempotency_records
      VALUES(p_org,p_actor,'memory_candidate_verify',p_key_sha256,p_request_sha256,'memory_candidate_verification',p_verification,clock_timestamp());
    RETURN QUERY SELECT p_verification,p_candidate,'reject'::text,NULL::uuid,NULL::integer,false;
    RETURN;
  END IF;

  IF EXISTS (
    SELECT 1 FROM app.agent_tasks task
     WHERE task.organization_id=p_org AND task.case_id=resolved_case
       AND task.state IN ('queued','leased','running','waiting_review')
  ) THEN
    RAISE EXCEPTION USING ERRCODE='NV014', MESSAGE='active task blocks revision publication';
  END IF;
  IF selected_case.state='planning' AND current_run.id IS NULL THEN
    RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='current planning run is unavailable';
  END IF;

  SELECT * INTO current_revision FROM app.student_case_revisions revision_row
   WHERE revision_row.organization_id=p_org AND revision_row.case_id=resolved_case
     AND revision_row.revision=p_expected_revision;
  IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='Case revision is unavailable'; END IF;
  IF jsonb_typeof(current_revision.student_preferences)<>'object'
     OR jsonb_typeof(current_revision.family_preferences)<>'object'
     OR (SELECT count(*) FROM jsonb_object_keys(current_revision.student_preferences))<>4
     OR (SELECT count(*) FROM jsonb_object_keys(current_revision.family_preferences))<>4
     OR jsonb_typeof(current_revision.student_preferences->'schema_version')<>'number'
     OR jsonb_typeof(current_revision.family_preferences->'schema_version')<>'number'
     OR current_revision.student_preferences->>'schema_version' IS DISTINCT FROM '1'
     OR current_revision.family_preferences->>'schema_version' IS DISTINCT FROM '1' THEN
    RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='unsafe Case revision projection';
  END IF;
  PERFORM app.validate_collaboration_fact(
    'student','student.intended_field',
    current_revision.student_preferences->'intended_field'
  );
  PERFORM app.validate_collaboration_fact(
    'student','student.preferred_countries',
    current_revision.student_preferences->'preferred_countries'
  );
  PERFORM app.validate_collaboration_fact(
    'student','student.intake',current_revision.student_preferences->'intake'
  );
  PERFORM app.validate_collaboration_fact(
    'parent','family.risk_tolerance',
    current_revision.family_preferences->'risk_tolerance'
  );
  PERFORM app.validate_collaboration_fact(
    'parent','family.japan_risk_accepted',
    current_revision.family_preferences->'japan_risk_accepted'
  );
  PERFORM app.validate_collaboration_fact(
    'parent','family.budget',current_revision.family_preferences->'budget'
  );
  next_revision := p_expected_revision+1;
  next_fact_version := COALESCE(prior_fact.fact_version,0)+1;
  next_student := current_revision.student_preferences;
  next_family := current_revision.family_preferences;
  IF candidate.fact_key='student.intended_field' THEN
    next_student := jsonb_set(next_student,'{intended_field}',candidate.proposed_value,true);
  ELSIF candidate.fact_key='student.preferred_countries' THEN
    next_student := jsonb_set(next_student,'{preferred_countries}',candidate.proposed_value,true);
  ELSIF candidate.fact_key='student.intake' THEN
    next_student := jsonb_set(next_student,'{intake}',candidate.proposed_value,true);
  ELSIF candidate.fact_key='family.risk_tolerance' THEN
    next_family := jsonb_set(next_family,'{risk_tolerance}',candidate.proposed_value,true);
  ELSIF candidate.fact_key='family.japan_risk_accepted' THEN
    next_family := jsonb_set(next_family,'{japan_risk_accepted}',candidate.proposed_value,true);
  ELSIF candidate.fact_key='family.budget' THEN
    next_family := jsonb_set(next_family,'{budget}',candidate.proposed_value,true);
  END IF;

  INSERT INTO app.memory_candidate_verifications(
    organization_id,id,candidate_id,case_id,advisor_actor_id,advisor_role,
    decision,reason,request_sha256,result_fact_id,result_revision
  ) VALUES(p_org,p_verification,p_candidate,resolved_case,p_actor,'advisor','confirm',p_reason,p_request_sha256,p_fact,next_revision);
  INSERT INTO app.confirmed_facts(
    organization_id,id,case_id,fact_key,value,value_sha256,source_candidate_id,
    source_message_event_id,subject_actor_id,subject_role,
    confirming_advisor_actor_id,confirming_advisor_role,supersedes_fact_id,fact_version
  ) VALUES(
    p_org,p_fact,resolved_case,candidate.fact_key,candidate.proposed_value,candidate.value_sha256,p_candidate,
    candidate.message_event_id,candidate.subject_actor_id,candidate.subject_role,
    p_actor,'advisor',prior_fact.id,next_fact_version
  );
  INSERT INTO app.student_case_revisions(
    organization_id,case_id,revision,schema_version,student_preferences,family_preferences
  ) VALUES(p_org,resolved_case,next_revision,1,next_student,next_family);
  INSERT INTO app.case_revision_confirmed_fact_refs(
    organization_id,case_id,case_revision,fact_key,confirmed_fact_id
  )
  SELECT p_org,resolved_case,next_revision,fact.fact_key,fact.id
    FROM app.confirmed_facts fact
   WHERE fact.organization_id=p_org AND fact.case_id=resolved_case
     AND fact.fact_key<>candidate.fact_key
     AND NOT EXISTS (
       SELECT 1 FROM app.confirmed_facts successor
        WHERE successor.organization_id=fact.organization_id
          AND successor.case_id=fact.case_id
          AND successor.fact_key=fact.fact_key
          AND successor.supersedes_fact_id=fact.id
     );
  INSERT INTO app.case_revision_confirmed_fact_refs(
    organization_id,case_id,case_revision,fact_key,confirmed_fact_id
  ) VALUES(p_org,resolved_case,next_revision,candidate.fact_key,p_fact);
  UPDATE app.student_cases selected_case_row SET current_revision=next_revision
   WHERE selected_case_row.organization_id=p_org AND selected_case_row.id=resolved_case
     AND selected_case_row.current_revision=p_expected_revision;
  IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='Case revision compare-and-swap failed'; END IF;
  IF current_run.id IS NOT NULL THEN
    UPDATE app.planning_runs planning_run SET is_current=false
     WHERE planning_run.organization_id=p_org AND planning_run.id=current_run.id
       AND planning_run.is_current;
    IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='PlanningRun currentness changed'; END IF;
  END IF;
  INSERT INTO app.audit_events
    VALUES(p_org,gen_random_uuid(),resolved_case,p_actor,'memory_candidate_confirmed',p_verification,jsonb_build_object('fact_id',p_fact,'revision',next_revision),clock_timestamp());
  INSERT INTO app.idempotency_records
    VALUES(p_org,p_actor,'memory_candidate_verify',p_key_sha256,p_request_sha256,'memory_candidate_verification',p_verification,clock_timestamp());
  RETURN QUERY SELECT p_verification,p_candidate,'confirm'::text,p_fact,next_revision,false;
END; $$;
"""

READ_SQL = r"""
CREATE FUNCTION app.read_collaboration_thread(p_org uuid,p_actor uuid,p_role text,p_case uuid) RETURNS TABLE(schema_version integer,thread_id uuid,case_id uuid,created_by_actor_id uuid,created_at timestamptz) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  IF p_org IS NULL OR p_actor IS NULL OR p_role IS NULL OR p_case IS NULL THEN
    RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid collaboration thread read';
  END IF;
  PERFORM app.assert_collaboration_context(p_org,p_actor,p_role);
  IF NOT EXISTS (
    SELECT 1 FROM app.student_case_participants participant
     WHERE participant.organization_id=p_org AND participant.case_id=p_case
       AND participant.actor_id=p_actor AND participant.role=p_role
  ) THEN
    RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='collaboration resource unavailable';
  END IF;
  RETURN QUERY
  SELECT 1,thread.id,thread.case_id,thread.created_by_actor_id,thread.created_at
    FROM app.collaboration_threads thread
   WHERE thread.organization_id=p_org AND thread.case_id=p_case;
END; $$;

CREATE FUNCTION app.read_collaboration_messages(p_org uuid,p_actor uuid,p_role text,p_thread uuid,p_after_sequence bigint,p_limit integer) RETURNS TABLE(schema_version integer,message_event_id uuid,thread_id uuid,case_id uuid,sequence_no bigint,actor_id uuid,actor_role text,body text,content_sha256 text,created_at timestamptz) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE selected_thread app.collaboration_threads%ROWTYPE;
BEGIN
  IF p_org IS NULL OR p_actor IS NULL OR p_role IS NULL OR p_thread IS NULL
     OR p_after_sequence IS NULL OR p_limit IS NULL
     OR p_after_sequence<0 OR p_limit NOT BETWEEN 1 AND 100 THEN
    RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid collaboration page';
  END IF;
  PERFORM app.assert_collaboration_context(p_org,p_actor,p_role);
  SELECT * INTO selected_thread FROM app.collaboration_threads thread
   WHERE thread.organization_id=p_org AND thread.id=p_thread;
  IF NOT FOUND OR NOT EXISTS (
    SELECT 1 FROM app.student_case_participants participant
     WHERE participant.organization_id=p_org AND participant.case_id=selected_thread.case_id
       AND participant.actor_id=p_actor AND participant.role=p_role
  ) THEN
    RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='collaboration resource unavailable';
  END IF;
  RETURN QUERY
  SELECT 1,event.id,event.thread_id,event.case_id,event.sequence_no,event.actor_id,
         event.actor_role,event.body,event.content_sha256,event.created_at
    FROM app.message_events event
   WHERE event.organization_id=p_org AND event.thread_id=p_thread
     AND event.sequence_no>p_after_sequence
   ORDER BY event.sequence_no
   LIMIT p_limit;
END; $$;

CREATE FUNCTION app.read_memory_candidates(p_org uuid,p_actor uuid,p_role text,p_case uuid,p_limit integer) RETURNS TABLE(projection jsonb) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  IF p_org IS NULL OR p_actor IS NULL OR p_role IS NULL OR p_case IS NULL
     OR p_limit IS NULL THEN
    RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid memory candidate page';
  END IF;
  PERFORM app.assert_collaboration_context(p_org,p_actor,p_role);
  IF p_limit NOT BETWEEN 1 AND 100 OR NOT EXISTS (
    SELECT 1 FROM app.student_case_participants participant
     WHERE participant.organization_id=p_org AND participant.case_id=p_case
       AND participant.actor_id=p_actor AND participant.role=p_role
  ) THEN
    IF p_limit NOT BETWEEN 1 AND 100 THEN
      RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid memory candidate page';
    END IF;
    RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='collaboration resource unavailable';
  END IF;
  IF p_role='advisor' THEN
    RETURN QUERY
    SELECT jsonb_build_object(
      'schema_version',1,
      'fact_key',candidate.fact_key,
      'value',candidate.proposed_value,
      'state',CASE
        WHEN verification.decision='confirm' THEN 'confirmed'
        WHEN verification.decision='reject' THEN 'rejected'
        WHEN candidate.case_revision<>selected_case.current_revision THEN 'stale'
        WHEN candidate.expires_at<=clock_timestamp() THEN 'expired'
        ELSE 'pending' END,
      'created_at',candidate.created_at,
      'expires_at',candidate.expires_at,
      'candidate_id',candidate.id,
      'message_event_id',candidate.message_event_id,
      'source_message_sequence_no',message.sequence_no,
      'subject_actor_id',candidate.subject_actor_id,
      'subject_role',candidate.subject_role,
      'case_revision',candidate.case_revision,
      'verification_id',verification.id,
      'decision',verification.decision,
      'reason',verification.reason,
      'request_sha256',candidate.request_sha256,
      'value_sha256',candidate.value_sha256
    )
      FROM app.memory_candidates candidate
      JOIN app.student_cases selected_case
        ON selected_case.organization_id=candidate.organization_id
       AND selected_case.id=candidate.case_id
      JOIN app.message_events message
        ON message.organization_id=candidate.organization_id
       AND message.id=candidate.message_event_id
      LEFT JOIN app.memory_candidate_verifications verification
        ON verification.organization_id=candidate.organization_id
       AND verification.candidate_id=candidate.id
     WHERE candidate.organization_id=p_org AND candidate.case_id=p_case
     ORDER BY candidate.created_at DESC,candidate.id
     LIMIT p_limit;
  ELSE
    RETURN QUERY
    SELECT jsonb_build_object(
      'schema_version',1,
      'fact_key',candidate.fact_key,
      'value',candidate.proposed_value,
      'state',CASE
        WHEN verification.decision='confirm' THEN 'confirmed'
        WHEN verification.decision='reject' THEN 'rejected'
        WHEN candidate.case_revision<>selected_case.current_revision THEN 'stale'
        WHEN candidate.expires_at<=clock_timestamp() THEN 'expired'
        ELSE 'pending' END,
      'created_at',candidate.created_at,
      'expires_at',candidate.expires_at
    )
      FROM app.memory_candidates candidate
      JOIN app.student_cases selected_case
        ON selected_case.organization_id=candidate.organization_id
       AND selected_case.id=candidate.case_id
      LEFT JOIN app.memory_candidate_verifications verification
        ON verification.organization_id=candidate.organization_id
       AND verification.candidate_id=candidate.id
     WHERE candidate.organization_id=p_org AND candidate.case_id=p_case
       AND candidate.subject_actor_id=p_actor AND candidate.subject_role=p_role
     ORDER BY candidate.created_at DESC,candidate.id
     LIMIT p_limit;
  END IF;
END; $$;

CREATE FUNCTION app.read_confirmed_facts(p_org uuid,p_actor uuid,p_role text,p_case uuid,p_limit integer) RETURNS TABLE(projection jsonb) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  IF p_org IS NULL OR p_actor IS NULL OR p_role IS NULL OR p_case IS NULL
     OR p_limit IS NULL THEN
    RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid confirmed fact page';
  END IF;
  PERFORM app.assert_collaboration_context(p_org,p_actor,p_role);
  IF p_limit NOT BETWEEN 1 AND 100 OR NOT EXISTS (
    SELECT 1 FROM app.student_case_participants participant
     WHERE participant.organization_id=p_org AND participant.case_id=p_case
       AND participant.actor_id=p_actor AND participant.role=p_role
  ) THEN
    IF p_limit NOT BETWEEN 1 AND 100 THEN
      RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid confirmed fact page';
    END IF;
    RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='collaboration resource unavailable';
  END IF;
  IF p_role='advisor' THEN
    RETURN QUERY
    SELECT jsonb_build_object(
      'schema_version',1,
      'fact_key',fact.fact_key,
      'value',fact.value,
      'fact_version',fact.fact_version,
      'confirmed_at',fact.confirmed_at,
      'subject_role',fact.subject_role,
      'confirming_advisor_role',fact.confirming_advisor_role,
      'confirmed_fact_id',fact.id,
      'candidate_id',fact.source_candidate_id,
      'verification_id',verification.id,
      'source_message_event_id',fact.source_message_event_id,
      'source_message_sequence_no',message.sequence_no,
      'source_message_sha256_prefix',left(message.content_sha256,12),
      'confirming_advisor_actor_id',fact.confirming_advisor_actor_id,
      'reason',verification.reason,
      'supersedes_fact_id',fact.supersedes_fact_id
    )
      FROM app.confirmed_facts fact
      JOIN app.memory_candidate_verifications verification
        ON verification.organization_id=fact.organization_id
       AND verification.result_fact_id=fact.id
      JOIN app.message_events message
        ON message.organization_id=fact.organization_id
       AND message.id=fact.source_message_event_id
     WHERE fact.organization_id=p_org AND fact.case_id=p_case
     ORDER BY fact.fact_key,fact.fact_version DESC
     LIMIT p_limit;
  ELSE
    RETURN QUERY
    SELECT jsonb_build_object(
      'schema_version',1,
      'fact_key',fact.fact_key,
      'value',fact.value,
      'fact_version',fact.fact_version,
      'confirmed_at',fact.confirmed_at,
      'subject_role',fact.subject_role,
      'confirming_advisor_role',fact.confirming_advisor_role
    )
      FROM app.confirmed_facts fact
     WHERE fact.organization_id=p_org AND fact.case_id=p_case
       AND NOT EXISTS (
         SELECT 1 FROM app.confirmed_facts successor
          WHERE successor.organization_id=fact.organization_id
            AND successor.case_id=fact.case_id
            AND successor.fact_key=fact.fact_key
            AND successor.supersedes_fact_id=fact.id
       )
     ORDER BY fact.fact_key
     LIMIT p_limit;
  END IF;
END; $$;

CREATE FUNCTION app.seed_demo_collaboration(p_org uuid,p_case uuid,p_thread uuid,p_advisor uuid,p_subject uuid,p_message uuid,p_candidate uuid,p_task uuid,p_fixture_kind text) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE existing app.collaboration_threads%ROWTYPE; existing_message app.message_events%ROWTYPE; existing_candidate app.memory_candidates%ROWTYPE; existing_task app.agent_tasks%ROWTYPE; existing_event app.agent_task_events%ROWTYPE; subject_role text; seeded_at timestamptz; source_pack app.source_packs%ROWTYPE; fixture_body text; fixture_fact_key text; fixture_value jsonb; message_content_sha text; message_request_sha text; candidate_value_sha text; candidate_request_sha text;
BEGIN
  IF p_org IS NULL OR p_case IS NULL OR p_thread IS NULL OR p_advisor IS NULL
     OR p_fixture_kind IS NULL
     OR p_fixture_kind NOT IN ('primary','active_task','stale','expired')
     OR (p_fixture_kind='primary' AND (p_subject IS NOT NULL OR p_message IS NOT NULL OR p_candidate IS NOT NULL OR p_task IS NOT NULL))
     OR (p_fixture_kind='active_task' AND (p_subject IS NOT NULL OR p_message IS NOT NULL OR p_candidate IS NOT NULL OR p_task IS NULL))
     OR (p_fixture_kind IN ('stale','expired') AND (p_subject IS NULL OR p_message IS NULL OR p_candidate IS NULL OR p_task IS NOT NULL)) THEN
    RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid demo collaboration seed';
  END IF;
  PERFORM set_config('night_voyager.organization_id',p_org::text,true);
  IF NOT EXISTS (
    SELECT 1 FROM app.student_case_participants participant
     WHERE participant.organization_id=p_org AND participant.case_id=p_case
       AND participant.actor_id=p_advisor AND participant.role='advisor'
  ) THEN
    RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='demo collaboration participants are unavailable';
  END IF;
  INSERT INTO app.collaboration_threads(
    organization_id,id,case_id,created_by_actor_id,created_by_role,created_at
  ) VALUES(p_org,p_thread,p_case,p_advisor,'advisor',timestamptz '2026-01-01 00:00:00+00')
  ON CONFLICT (organization_id,case_id) DO NOTHING;
  SELECT * INTO existing FROM app.collaboration_threads thread
   WHERE thread.organization_id=p_org AND thread.case_id=p_case;
  IF NOT FOUND OR existing.id IS DISTINCT FROM p_thread
     OR existing.case_id IS DISTINCT FROM p_case
     OR existing.created_by_actor_id IS DISTINCT FROM p_advisor
     OR existing.created_by_role IS DISTINCT FROM 'advisor'
     OR existing.created_at IS DISTINCT FROM timestamptz '2026-01-01 00:00:00+00' THEN
    RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='demo collaboration seed mismatch';
  END IF;

  IF p_fixture_kind='active_task' THEN
    SELECT * INTO source_pack FROM app.source_packs pack
     WHERE pack.organization_id=p_org ORDER BY pack.id,pack.version LIMIT 1;
    IF NOT FOUND OR source_pack.id IS NULL THEN
      RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='demo collaboration source pack is unavailable';
    END IF;
    INSERT INTO app.agent_tasks(
      organization_id,id,case_id,operation,case_revision,source_pack_id,
      source_pack_version,policy_version,request_sha256,created_by_actor_id,
      row_version,state,attempt_count,lease_generation,created_at,updated_at
    ) VALUES(
      p_org,p_task,p_case,'generate_planning_run_v1',1,source_pack.id,
      source_pack.version,'m3a-policy-v1',repeat('e',64),p_advisor,
      1,'waiting_review',0,0,timestamptz '2026-01-01 00:00:00+00',
      timestamptz '2026-01-01 00:00:00+00'
    ) ON CONFLICT DO NOTHING;
    SELECT * INTO existing_task FROM app.agent_tasks task
     WHERE task.organization_id=p_org AND task.case_id=p_case
       AND task.operation='generate_planning_run_v1'
       AND task.case_revision=1 AND task.source_pack_id=source_pack.id
       AND task.source_pack_version=source_pack.version
       AND task.policy_version='m3a-policy-v1'
       AND task.state IN ('queued','leased','running','waiting_review','succeeded');
    IF NOT FOUND OR existing_task.id IS DISTINCT FROM p_task
       OR existing_task.case_id IS DISTINCT FROM p_case
       OR existing_task.operation IS DISTINCT FROM 'generate_planning_run_v1'
       OR existing_task.case_revision IS DISTINCT FROM 1
       OR existing_task.source_pack_id IS DISTINCT FROM source_pack.id
       OR existing_task.source_pack_version IS DISTINCT FROM source_pack.version
       OR existing_task.policy_version IS DISTINCT FROM 'm3a-policy-v1'
       OR existing_task.request_sha256 IS DISTINCT FROM repeat('e',64)
       OR existing_task.created_by_actor_id IS DISTINCT FROM p_advisor
       OR existing_task.row_version IS DISTINCT FROM 1
       OR existing_task.state IS DISTINCT FROM 'waiting_review'
       OR existing_task.attempt_count IS DISTINCT FROM 0
       OR existing_task.lease_generation IS DISTINCT FROM 0
       OR existing_task.result_planning_run_id IS NOT NULL
       OR existing_task.created_at IS DISTINCT FROM timestamptz '2026-01-01 00:00:00+00'
       OR existing_task.updated_at IS DISTINCT FROM timestamptz '2026-01-01 00:00:00+00' THEN
      RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='demo collaboration active task mismatch';
    END IF;
    INSERT INTO app.agent_task_events(
      organization_id,task_id,event_sequence,event_code,public_status,
      public_code,attempt_no,result_planning_run_id,created_at
    ) VALUES(
      p_org,p_task,1,'waiting_review','needs_advisor_review',
      'review_required',0,NULL,timestamptz '2026-01-01 00:00:00+00'
    ) ON CONFLICT DO NOTHING;
    SELECT * INTO existing_event FROM app.agent_task_events event
     WHERE event.organization_id=p_org AND event.task_id=p_task
       AND event.event_sequence=1;
    IF NOT FOUND OR existing_event.event_code IS DISTINCT FROM 'waiting_review'
       OR existing_event.public_status IS DISTINCT FROM 'needs_advisor_review'
       OR existing_event.public_code IS DISTINCT FROM 'review_required'
       OR existing_event.attempt_no IS DISTINCT FROM 0
       OR existing_event.result_planning_run_id IS NOT NULL
       OR existing_event.created_at IS DISTINCT FROM timestamptz '2026-01-01 00:00:00+00' THEN
      RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='demo collaboration active task event mismatch';
    END IF;
  END IF;

  IF p_fixture_kind IN ('stale','expired') THEN
    SELECT participant.role INTO subject_role
      FROM app.student_case_participants participant
     WHERE participant.organization_id=p_org AND participant.case_id=p_case
       AND participant.actor_id=p_subject AND participant.role IN ('student','parent');
    IF subject_role IS NULL THEN
      RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='demo collaboration subject is unavailable';
    END IF;
    seeded_at := timestamptz '2000-01-01 00:00:00+00';
    fixture_body := 'Synthetic family preference fixture.';
    fixture_fact_key := CASE subject_role WHEN 'student' THEN 'student.intended_field' ELSE 'family.risk_tolerance' END;
    fixture_value := CASE subject_role WHEN 'student' THEN to_jsonb('engineering'::text) ELSE to_jsonb('high'::text) END;
    message_content_sha := encode(sha256(convert_to(fixture_body,'UTF8')),'hex');
    message_request_sha := encode(sha256(convert_to(format(
      '{"body":%s,"thread_id":"%s"}',to_jsonb(fixture_body)::text,p_thread::text
    ),'UTF8')),'hex');
    candidate_value_sha := encode(sha256(convert_to(fixture_value::text,'UTF8')),'hex');
    candidate_request_sha := encode(sha256(convert_to(format(
      '{"case_revision":1,"message_event_id":"%s","proposal":{"fact_key":"%s","schema_version":1,"value":%s}}',
      p_message::text,fixture_fact_key,fixture_value::text
    ),'UTF8')),'hex');
    INSERT INTO app.message_events(
      organization_id,id,thread_id,case_id,sequence_no,actor_id,actor_role,
      body,content_sha256,request_sha256,created_at
    ) VALUES(
      p_org,p_message,p_thread,p_case,1,p_subject,subject_role,
      fixture_body,message_content_sha,message_request_sha,seeded_at
    ) ON CONFLICT DO NOTHING;
    SELECT * INTO existing_message FROM app.message_events event
     WHERE event.organization_id=p_org AND event.thread_id=p_thread
       AND event.sequence_no=1;
    IF NOT FOUND OR existing_message.id IS DISTINCT FROM p_message
       OR existing_message.thread_id IS DISTINCT FROM p_thread
       OR existing_message.case_id IS DISTINCT FROM p_case
       OR existing_message.sequence_no IS DISTINCT FROM 1
       OR existing_message.actor_id IS DISTINCT FROM p_subject
       OR existing_message.actor_role IS DISTINCT FROM subject_role
       OR existing_message.body IS DISTINCT FROM fixture_body
       OR existing_message.content_sha256 IS DISTINCT FROM message_content_sha
       OR existing_message.request_sha256 IS DISTINCT FROM message_request_sha
       OR existing_message.created_at IS DISTINCT FROM seeded_at THEN
      RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='demo collaboration message mismatch';
    END IF;
    INSERT INTO app.memory_candidates(
      organization_id,id,case_id,case_revision,message_event_id,
      subject_actor_id,subject_role,proposing_actor_id,proposing_role,
      fact_key,proposed_value,value_sha256,request_sha256,created_at,expires_at
    ) VALUES(
      p_org,p_candidate,p_case,1,p_message,p_subject,subject_role,p_subject,subject_role,
      fixture_fact_key,fixture_value,candidate_value_sha,candidate_request_sha,
      seeded_at,seeded_at+interval '7 days'
    ) ON CONFLICT DO NOTHING;
    SELECT * INTO existing_candidate FROM app.memory_candidates candidate
     WHERE candidate.organization_id=p_org AND candidate.message_event_id=p_message;
    IF NOT FOUND OR existing_candidate.id IS DISTINCT FROM p_candidate
       OR existing_candidate.case_id IS DISTINCT FROM p_case
       OR existing_candidate.case_revision IS DISTINCT FROM 1
       OR existing_candidate.message_event_id IS DISTINCT FROM p_message
       OR existing_candidate.subject_actor_id IS DISTINCT FROM p_subject
       OR existing_candidate.subject_role IS DISTINCT FROM subject_role
       OR existing_candidate.proposing_actor_id IS DISTINCT FROM p_subject
       OR existing_candidate.proposing_role IS DISTINCT FROM subject_role
       OR existing_candidate.fact_key IS DISTINCT FROM fixture_fact_key
       OR existing_candidate.proposed_value IS DISTINCT FROM fixture_value
       OR existing_candidate.value_sha256 IS DISTINCT FROM candidate_value_sha
       OR existing_candidate.request_sha256 IS DISTINCT FROM candidate_request_sha
       OR existing_candidate.provenance_kind IS DISTINCT FROM 'participant_proposal'
       OR existing_candidate.created_at IS DISTINCT FROM seeded_at
       OR existing_candidate.expires_at IS DISTINCT FROM seeded_at+interval '7 days' THEN
      RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='demo collaboration candidate mismatch';
    END IF;
  END IF;
END; $$;
"""

PRIVILEGE_SQL = r"""
REVOKE ALL ON TABLE app.collaboration_threads FROM PUBLIC;
REVOKE ALL ON TABLE app.collaboration_threads FROM night_voyager_api;
REVOKE ALL ON TABLE app.collaboration_threads FROM night_voyager_worker;
REVOKE ALL ON TABLE app.message_events FROM PUBLIC;
REVOKE ALL ON TABLE app.message_events FROM night_voyager_api;
REVOKE ALL ON TABLE app.message_events FROM night_voyager_worker;
REVOKE ALL ON TABLE app.memory_candidates FROM PUBLIC;
REVOKE ALL ON TABLE app.memory_candidates FROM night_voyager_api;
REVOKE ALL ON TABLE app.memory_candidates FROM night_voyager_worker;
REVOKE ALL ON TABLE app.memory_candidate_verifications FROM PUBLIC;
REVOKE ALL ON TABLE app.memory_candidate_verifications FROM night_voyager_api;
REVOKE ALL ON TABLE app.memory_candidate_verifications FROM night_voyager_worker;
REVOKE ALL ON TABLE app.confirmed_facts FROM PUBLIC;
REVOKE ALL ON TABLE app.confirmed_facts FROM night_voyager_api;
REVOKE ALL ON TABLE app.confirmed_facts FROM night_voyager_worker;
REVOKE ALL ON TABLE app.case_revision_confirmed_fact_refs FROM PUBLIC;
REVOKE ALL ON TABLE app.case_revision_confirmed_fact_refs FROM night_voyager_api;
REVOKE ALL ON TABLE app.case_revision_confirmed_fact_refs FROM night_voyager_worker;

REVOKE ALL ON FUNCTION app.reject_collaboration_mutation() FROM PUBLIC;
REVOKE ALL ON FUNCTION app.reject_collaboration_mutation() FROM night_voyager_api;
REVOKE ALL ON FUNCTION app.reject_collaboration_mutation() FROM night_voyager_worker;
REVOKE ALL ON FUNCTION app.serialize_agent_task_case_revision() FROM PUBLIC;
REVOKE ALL ON FUNCTION app.serialize_agent_task_case_revision() FROM night_voyager_api;
REVOKE ALL ON FUNCTION app.serialize_agent_task_case_revision() FROM night_voyager_worker;
REVOKE ALL ON FUNCTION app.assert_collaboration_context(uuid,uuid,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.assert_collaboration_context(uuid,uuid,text) FROM night_voyager_api;
REVOKE ALL ON FUNCTION app.assert_collaboration_context(uuid,uuid,text) FROM night_voyager_worker;
REVOKE ALL ON FUNCTION app.validate_collaboration_message(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.validate_collaboration_message(text) FROM night_voyager_api;
REVOKE ALL ON FUNCTION app.validate_collaboration_message(text) FROM night_voyager_worker;
REVOKE ALL ON FUNCTION app.validate_collaboration_fact(text,text,jsonb) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.validate_collaboration_fact(text,text,jsonb) FROM night_voyager_api;
REVOKE ALL ON FUNCTION app.validate_collaboration_fact(text,text,jsonb) FROM night_voyager_worker;

REVOKE ALL ON FUNCTION app.create_collaboration_thread(uuid,uuid,text,uuid,uuid,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.create_collaboration_thread(uuid,uuid,text,uuid,uuid,text,text) FROM night_voyager_api;
REVOKE ALL ON FUNCTION app.create_collaboration_thread(uuid,uuid,text,uuid,uuid,text,text) FROM night_voyager_worker;
REVOKE ALL ON FUNCTION app.append_collaboration_message(uuid,uuid,text,uuid,uuid,text,text,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.append_collaboration_message(uuid,uuid,text,uuid,uuid,text,text,text,text) FROM night_voyager_api;
REVOKE ALL ON FUNCTION app.append_collaboration_message(uuid,uuid,text,uuid,uuid,text,text,text,text) FROM night_voyager_worker;
REVOKE ALL ON FUNCTION app.propose_memory_candidate(uuid,uuid,text,uuid,uuid,integer,text,jsonb,text,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.propose_memory_candidate(uuid,uuid,text,uuid,uuid,integer,text,jsonb,text,text,text) FROM night_voyager_api;
REVOKE ALL ON FUNCTION app.propose_memory_candidate(uuid,uuid,text,uuid,uuid,integer,text,jsonb,text,text,text) FROM night_voyager_worker;
REVOKE ALL ON FUNCTION app.verify_memory_candidate(uuid,uuid,uuid,integer,text,text,uuid,uuid,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.verify_memory_candidate(uuid,uuid,uuid,integer,text,text,uuid,uuid,text,text) FROM night_voyager_api;
REVOKE ALL ON FUNCTION app.verify_memory_candidate(uuid,uuid,uuid,integer,text,text,uuid,uuid,text,text) FROM night_voyager_worker;
REVOKE ALL ON FUNCTION app.read_collaboration_thread(uuid,uuid,text,uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.read_collaboration_thread(uuid,uuid,text,uuid) FROM night_voyager_api;
REVOKE ALL ON FUNCTION app.read_collaboration_thread(uuid,uuid,text,uuid) FROM night_voyager_worker;
REVOKE ALL ON FUNCTION app.read_collaboration_messages(uuid,uuid,text,uuid,bigint,integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.read_collaboration_messages(uuid,uuid,text,uuid,bigint,integer) FROM night_voyager_api;
REVOKE ALL ON FUNCTION app.read_collaboration_messages(uuid,uuid,text,uuid,bigint,integer) FROM night_voyager_worker;
REVOKE ALL ON FUNCTION app.read_memory_candidates(uuid,uuid,text,uuid,integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.read_memory_candidates(uuid,uuid,text,uuid,integer) FROM night_voyager_api;
REVOKE ALL ON FUNCTION app.read_memory_candidates(uuid,uuid,text,uuid,integer) FROM night_voyager_worker;
REVOKE ALL ON FUNCTION app.read_confirmed_facts(uuid,uuid,text,uuid,integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.read_confirmed_facts(uuid,uuid,text,uuid,integer) FROM night_voyager_api;
REVOKE ALL ON FUNCTION app.read_confirmed_facts(uuid,uuid,text,uuid,integer) FROM night_voyager_worker;
REVOKE ALL ON FUNCTION app.seed_demo_collaboration(uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.seed_demo_collaboration(uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,text) FROM night_voyager_api;
REVOKE ALL ON FUNCTION app.seed_demo_collaboration(uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,text) FROM night_voyager_worker;

GRANT EXECUTE ON FUNCTION app.create_collaboration_thread(uuid,uuid,text,uuid,uuid,text,text) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.append_collaboration_message(uuid,uuid,text,uuid,uuid,text,text,text,text) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.propose_memory_candidate(uuid,uuid,text,uuid,uuid,integer,text,jsonb,text,text,text) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.verify_memory_candidate(uuid,uuid,uuid,integer,text,text,uuid,uuid,text,text) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.read_collaboration_thread(uuid,uuid,text,uuid) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.read_collaboration_messages(uuid,uuid,text,uuid,bigint,integer) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.read_memory_candidates(uuid,uuid,text,uuid,integer) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.read_confirmed_facts(uuid,uuid,text,uuid,integer) TO night_voyager_api;

REVOKE EXECUTE ON FUNCTION app.publish_case_revision(uuid,uuid,integer,integer,jsonb,jsonb) FROM night_voyager_api;
"""

LEGACY_PLANNING_PERSISTENCE_SQL = r"""
CREATE OR REPLACE FUNCTION app.persist_planning_result(p_org uuid,p_run uuid,p_case uuid,p_revision integer,p_pack uuid,p_version integer,p_policy text,p_evidence_hash text,p_state text,p_reason text,p_output_hash text,p_supersedes uuid,p_output jsonb) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE item jsonb; dimension jsonb; evidence_use jsonb; cost_item jsonb; ranking_item jsonb; route_index integer := 0; dimension_index integer := 0; cost_index integer := 0; ranking_index integer := 0; route_uuid uuid; dimension_uuid uuid;
BEGIN
 PERFORM app.assert_context(p_org);
 IF p_state NOT IN ('failed','blocked','review_required') THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='result must be terminal'; END IF;
 IF NOT EXISTS (SELECT 1 FROM app.student_cases WHERE organization_id=p_org AND id=p_case AND current_revision=p_revision AND state='planning') THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='case revision or state is stale'; END IF;
 IF p_supersedes IS NOT NULL THEN UPDATE app.planning_runs SET is_current=false WHERE organization_id=p_org AND id=p_supersedes AND is_current=true; IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='superseded run is stale'; END IF; END IF;
 INSERT INTO app.planning_runs(organization_id,id,case_id,case_revision,source_pack_id,source_pack_version,policy_version,evidence_projection_sha256,state,reason_code,output_sha256,supersedes_run_id,is_current) VALUES(p_org,p_run,p_case,p_revision,p_pack,p_version,p_policy,p_evidence_hash,'synthesizing',NULL,NULL,p_supersedes,true);
 FOR item IN SELECT * FROM jsonb_array_elements(p_output->'routes') LOOP
  route_index := route_index + 1;
  route_uuid := ('71000000-0000-0000-0000-'||lpad(route_index::text,12,'0'))::uuid;
  INSERT INTO app.planning_routes VALUES(p_org,p_run,route_uuid,item->>'country',item->>'outcome',item->>'reason_code');
  FOR dimension IN SELECT * FROM jsonb_array_elements(item->'dimensions') LOOP
   dimension_index := dimension_index + 1;
   dimension_uuid := ('72000000-0000-0000-0000-'||lpad(dimension_index::text,12,'0'))::uuid;
   INSERT INTO app.comparison_dimensions VALUES(p_org,p_run,route_uuid,dimension_uuid,dimension->>'dimension_key',dimension->>'outcome',dimension->>'reason_code');
   FOR evidence_use IN SELECT * FROM jsonb_array_elements(dimension->'evidence_uses') LOOP
    INSERT INTO app.comparison_dimension_evidence_refs VALUES(p_org,p_run,route_uuid,dimension_uuid,(evidence_use->>'evidence_id')::uuid,evidence_use->>'role');
   END LOOP;
  END LOOP;
 END LOOP;
 FOR cost_item IN SELECT * FROM jsonb_array_elements(p_output->'costs') LOOP
  cost_index := cost_index + 1;
  INSERT INTO app.cost_evidence VALUES(p_org,p_run,('73000000-0000-0000-0000-'||lpad(cost_index::text,12,'0'))::uuid,cost_item->>'country',cost_item->>'intake',cost_item->>'period',cost_item->>'currency',(cost_item->>'tuition_minor')::bigint,(cost_item->>'living_minor')::bigint,(cost_item->>'fx_rate')::numeric,cost_item->>'fx_source',(cost_item->>'fx_date')::date,(cost_item->>'tuition_evidence_id')::uuid,(cost_item->>'living_evidence_id')::uuid,(cost_item->>'fx_evidence_id')::uuid);
 END LOOP;
 FOR ranking_item IN SELECT * FROM jsonb_array_elements(p_output->'rankings') LOOP
  ranking_index := ranking_index + 1;
  INSERT INTO app.ranking_evidence VALUES(p_org,p_run,('74000000-0000-0000-0000-'||lpad(ranking_index::text,12,'0'))::uuid,ranking_item->>'country',ranking_item->>'ranking_system',(ranking_item->>'rank')::integer,(ranking_item->>'publication_year')::integer,(ranking_item->>'evidence_id')::uuid);
 END LOOP;
 UPDATE app.planning_runs SET state=p_state,reason_code=p_reason,output_sha256=p_output_hash WHERE organization_id=p_org AND id=p_run;
END; $$;
"""

LEGACY_RUN_GUARD_SQL = r"""
CREATE OR REPLACE FUNCTION app.guard_run_transition() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  IF OLD.state IN ('failed','blocked','review_required') THEN
    IF OLD.is_current AND NOT NEW.is_current AND NEW.state=OLD.state AND NEW.reason_code IS NOT DISTINCT FROM OLD.reason_code AND NEW.output_sha256 IS NOT DISTINCT FROM OLD.output_sha256 AND NEW.organization_id=OLD.organization_id AND NEW.id=OLD.id AND NEW.case_id=OLD.case_id AND NEW.case_revision=OLD.case_revision AND NEW.source_pack_id=OLD.source_pack_id AND NEW.source_pack_version=OLD.source_pack_version AND NEW.policy_version=OLD.policy_version AND NEW.evidence_projection_sha256=OLD.evidence_projection_sha256 THEN RETURN NEW; END IF;
    RAISE EXCEPTION USING ERRCODE='NV005', MESSAGE='terminal planning run is immutable';
  END IF;
  IF NOT ((OLD.state='draft' AND NEW.state IN ('collecting_evidence','failed')) OR (OLD.state='collecting_evidence' AND NEW.state IN ('synthesizing','failed')) OR (OLD.state='synthesizing' AND NEW.state IN ('failed','blocked','review_required'))) THEN
    RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid planning run transition';
  END IF;
  IF NEW.organization_id<>OLD.organization_id OR NEW.id<>OLD.id OR NEW.case_id<>OLD.case_id OR NEW.case_revision<>OLD.case_revision OR NEW.source_pack_id<>OLD.source_pack_id OR NEW.source_pack_version<>OLD.source_pack_version OR NEW.policy_version<>OLD.policy_version OR NEW.evidence_projection_sha256<>OLD.evidence_projection_sha256 THEN
    RAISE EXCEPTION USING ERRCODE='NV005', MESSAGE='planning run inputs are immutable';
  END IF;
  RETURN NEW;
END; $$;
"""


def _execute(sql: str) -> None:
    op.get_bind().exec_driver_sql(sql.strip())


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


def _execute_statements(sql: str) -> None:
    for statement in _split_statements(sql):
        _execute(statement)


def upgrade() -> None:
    _execute_statements(DDL_SQL)
    _execute_statements(PLANNING_PERSISTENCE_LOCK_SQL)
    _execute_statements(MUTATION_SQL)
    _execute_statements(READ_SQL)
    _execute_statements(PRIVILEGE_SQL)


def downgrade() -> None:
    guarded_tables = (
        "collaboration_threads",
        "message_events",
        "memory_candidates",
        "memory_candidate_verifications",
        "confirmed_facts",
        "case_revision_confirmed_fact_refs",
    )
    for table in (*guarded_tables, "audit_events", "idempotency_records"):
        op.execute(f"ALTER TABLE app.{table} NO FORCE ROW LEVEL SECURITY")

    downgrade_guard_sql = r"""
    DO $$
    BEGIN
      IF EXISTS (SELECT 1 FROM app.collaboration_threads)
         OR EXISTS (SELECT 1 FROM app.message_events)
         OR EXISTS (SELECT 1 FROM app.memory_candidates)
         OR EXISTS (SELECT 1 FROM app.memory_candidate_verifications)
         OR EXISTS (SELECT 1 FROM app.confirmed_facts)
         OR EXISTS (SELECT 1 FROM app.case_revision_confirmed_fact_refs)
         OR EXISTS (
           SELECT 1 FROM app.idempotency_records
            WHERE operation IN (
              'collaboration_thread_create','collaboration_message_append',
              'memory_candidate_propose','memory_candidate_verify'
            )
         )
         OR EXISTS (
           SELECT 1 FROM app.audit_events
            WHERE event_type IN ('memory_candidate_confirmed','memory_candidate_rejected')
         ) THEN
        RAISE EXCEPTION USING
          MESSAGE='refusing downgrade: collaboration authority history exists';
      END IF;
    END; $$;
    """
    _execute_statements(downgrade_guard_sql)

    op.execute("ALTER TABLE app.audit_events FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE app.idempotency_records FORCE ROW LEVEL SECURITY")

    _execute_statements(LEGACY_RUN_GUARD_SQL)
    _execute_statements(LEGACY_PLANNING_PERSISTENCE_SQL)
    op.execute("DROP TRIGGER agent_tasks_collaboration_case_revision ON app.agent_tasks")
    op.execute("DROP FUNCTION app.serialize_agent_task_case_revision()")
    op.execute(
        "DROP FUNCTION app.seed_demo_collaboration(uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,text)"
    )
    op.execute("DROP FUNCTION app.read_confirmed_facts(uuid,uuid,text,uuid,integer)")
    op.execute("DROP FUNCTION app.read_memory_candidates(uuid,uuid,text,uuid,integer)")
    op.execute("DROP FUNCTION app.read_collaboration_messages(uuid,uuid,text,uuid,bigint,integer)")
    op.execute("DROP FUNCTION app.read_collaboration_thread(uuid,uuid,text,uuid)")
    op.execute(
        "DROP FUNCTION app.verify_memory_candidate(uuid,uuid,uuid,integer,text,text,uuid,uuid,text,text)"
    )
    op.execute(
        "DROP FUNCTION app.propose_memory_candidate(uuid,uuid,text,uuid,uuid,integer,text,jsonb,text,text,text)"
    )
    op.execute(
        "DROP FUNCTION app.append_collaboration_message(uuid,uuid,text,uuid,uuid,text,text,text,text)"
    )
    op.execute("DROP FUNCTION app.create_collaboration_thread(uuid,uuid,text,uuid,uuid,text,text)")
    op.execute("DROP FUNCTION app.validate_collaboration_fact(text,text,jsonb)")
    op.execute("DROP FUNCTION app.validate_collaboration_message(text)")
    op.execute("DROP FUNCTION app.assert_collaboration_context(uuid,uuid,text)")

    drop_order = (
        "case_revision_confirmed_fact_refs",
        "memory_candidate_verifications",
        "confirmed_facts",
        "memory_candidates",
        "message_events",
        "collaboration_threads",
    )
    for table in drop_order:
        op.execute(f"DROP TABLE app.{table}")
    op.execute("DROP FUNCTION app.reject_collaboration_mutation()")
    op.execute(
        "GRANT EXECUTE ON FUNCTION app.publish_case_revision(uuid,uuid,integer,integer,jsonb,jsonb) TO night_voyager_api"
    )
