# ruff: noqa: E501
"""Create the M3B advisor and family decision authority boundary."""

from collections.abc import Sequence

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "student_case_participants",
    "advisor_reviews",
    "evidence_risk_acceptances",
    "decision_briefs",
    "family_decisions",
    "timeline_plans",
    "audit_events",
    "idempotency_records",
)

UPGRADE_SQL = r"""
ALTER TABLE app.student_cases DROP CONSTRAINT student_cases_state_check;
ALTER TABLE app.student_cases ADD CONSTRAINT student_cases_state_check CHECK (state IN ('intake','planning','advisor_review','family_review','decided','plan_ready'));

CREATE TABLE app.student_case_participants (
  organization_id uuid NOT NULL, case_id uuid NOT NULL, actor_id uuid NOT NULL,
  role text NOT NULL CHECK (role IN ('advisor','student','parent')),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id,case_id,actor_id,role),
  FOREIGN KEY (organization_id,case_id) REFERENCES app.student_cases(organization_id,id),
  FOREIGN KEY (organization_id,actor_id,role) REFERENCES app.memberships(organization_id,actor_id,role)
);
CREATE INDEX student_case_participants_actor_idx ON app.student_case_participants(organization_id,actor_id,case_id);
CREATE TABLE app.advisor_reviews (
  organization_id uuid NOT NULL, id uuid NOT NULL, case_id uuid NOT NULL,
  case_revision integer NOT NULL, planning_run_id uuid NOT NULL,
  review_version integer NOT NULL CHECK (review_version > 0), advisor_actor_id uuid NOT NULL,
  action text NOT NULL CHECK (action IN ('approve_for_consultation','reject','request_revision')),
  eligible_route_ids jsonb NOT NULL DEFAULT '[]', risk_acceptances jsonb NOT NULL DEFAULT '[]',
  reviewer_notes text, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id,id),
  UNIQUE (organization_id,planning_run_id,review_version),
  FOREIGN KEY (organization_id,case_id) REFERENCES app.student_cases(organization_id,id),
  FOREIGN KEY (organization_id,planning_run_id) REFERENCES app.planning_runs(organization_id,id),
  FOREIGN KEY (organization_id,advisor_actor_id) REFERENCES app.actors(organization_id,id)
);
CREATE TABLE app.evidence_risk_acceptances (
  organization_id uuid NOT NULL, id uuid NOT NULL, advisor_review_id uuid NOT NULL,
  evidence_ref_id uuid NOT NULL, risk_kind text NOT NULL CHECK (risk_kind IN ('optional','stale','unverified')),
  reason text NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id,id),
  UNIQUE (organization_id,advisor_review_id,evidence_ref_id,risk_kind),
  FOREIGN KEY (organization_id,advisor_review_id) REFERENCES app.advisor_reviews(organization_id,id),
  FOREIGN KEY (organization_id,evidence_ref_id) REFERENCES app.evidence_refs(organization_id,id)
);
CREATE TABLE app.decision_briefs (
  organization_id uuid NOT NULL, id uuid NOT NULL, case_id uuid NOT NULL,
  case_revision integer NOT NULL, planning_run_id uuid NOT NULL, advisor_review_id uuid NOT NULL,
  brief_version integer NOT NULL CHECK (brief_version > 0), policy_version text NOT NULL,
  source_pack_id uuid NOT NULL, source_pack_version integer NOT NULL,
  evidence_projection_sha256 text NOT NULL CHECK (length(evidence_projection_sha256)=64),
  output_sha256 text NOT NULL CHECK (length(output_sha256)=64), source_snapshot_date date NOT NULL,
  family_safe_projection jsonb NOT NULL, is_current boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id,id),
  FOREIGN KEY (organization_id,case_id) REFERENCES app.student_cases(organization_id,id),
  FOREIGN KEY (organization_id,planning_run_id) REFERENCES app.planning_runs(organization_id,id),
  FOREIGN KEY (organization_id,advisor_review_id) REFERENCES app.advisor_reviews(organization_id,id),
  FOREIGN KEY (organization_id,source_pack_id,source_pack_version) REFERENCES app.source_packs(organization_id,id,version)
);
CREATE UNIQUE INDEX decision_briefs_one_current ON app.decision_briefs(organization_id,case_id) WHERE is_current;
CREATE TABLE app.family_decisions (
  organization_id uuid NOT NULL, id uuid NOT NULL, receipt_id uuid NOT NULL,
  case_id uuid NOT NULL, decision_brief_id uuid NOT NULL, brief_version integer NOT NULL,
  selected_route_id uuid NOT NULL, accepted_budget_min_minor bigint NOT NULL CHECK (accepted_budget_min_minor > 0),
  accepted_budget_max_minor bigint NOT NULL CHECK (accepted_budget_max_minor >= accepted_budget_min_minor),
  currency text NOT NULL CHECK (currency='CNY'), accepted_trade_offs jsonb NOT NULL,
  decision_made_by_actor_id uuid NOT NULL, recorded_by_actor_id uuid NOT NULL,
  source text NOT NULL CHECK (source IN ('direct','family_consultation')),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id,id), UNIQUE (organization_id,receipt_id),
  FOREIGN KEY (organization_id,case_id) REFERENCES app.student_cases(organization_id,id),
  FOREIGN KEY (organization_id,decision_brief_id) REFERENCES app.decision_briefs(organization_id,id),
  FOREIGN KEY (organization_id,planning_run_id,selected_route_id) REFERENCES app.planning_routes(organization_id,planning_run_id,id),
  planning_run_id uuid NOT NULL
);
CREATE UNIQUE INDEX family_decisions_one_per_brief ON app.family_decisions(organization_id,decision_brief_id);
CREATE TABLE app.timeline_plans (
  organization_id uuid NOT NULL, id uuid NOT NULL, family_decision_id uuid NOT NULL,
  schema_version integer NOT NULL CHECK (schema_version=1), country text NOT NULL,
  intake text NOT NULL, milestones jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id,id), UNIQUE (organization_id,family_decision_id),
  FOREIGN KEY (organization_id,family_decision_id) REFERENCES app.family_decisions(organization_id,id)
);
CREATE TABLE app.audit_events (
  organization_id uuid NOT NULL, id uuid NOT NULL, case_id uuid NOT NULL,
  actor_id uuid NOT NULL, event_type text NOT NULL, subject_id uuid NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id,id),
  FOREIGN KEY (organization_id,case_id) REFERENCES app.student_cases(organization_id,id),
  FOREIGN KEY (organization_id,actor_id) REFERENCES app.actors(organization_id,id)
);
CREATE INDEX audit_events_case_idx ON app.audit_events(organization_id,case_id,created_at);
CREATE TABLE app.idempotency_records (
  organization_id uuid NOT NULL, actor_id uuid NOT NULL, operation text NOT NULL,
  key_sha256 text NOT NULL CHECK (length(key_sha256)=64), request_sha256 text NOT NULL CHECK (length(request_sha256)=64),
  response_kind text NOT NULL, response_id uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id,actor_id,operation,key_sha256),
  FOREIGN KEY (organization_id,actor_id) REFERENCES app.actors(organization_id,id)
);

ALTER TABLE app.student_case_participants ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.student_case_participants FORCE ROW LEVEL SECURITY;
CREATE POLICY student_case_participants_tenant_isolation ON app.student_case_participants USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid) WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);
ALTER TABLE app.advisor_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.advisor_reviews FORCE ROW LEVEL SECURITY;
CREATE POLICY advisor_reviews_tenant_isolation ON app.advisor_reviews USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid) WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);
ALTER TABLE app.evidence_risk_acceptances ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.evidence_risk_acceptances FORCE ROW LEVEL SECURITY;
CREATE POLICY evidence_risk_acceptances_tenant_isolation ON app.evidence_risk_acceptances USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid) WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);
ALTER TABLE app.decision_briefs ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.decision_briefs FORCE ROW LEVEL SECURITY;
CREATE POLICY decision_briefs_tenant_isolation ON app.decision_briefs USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid) WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);
ALTER TABLE app.family_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.family_decisions FORCE ROW LEVEL SECURITY;
CREATE POLICY family_decisions_tenant_isolation ON app.family_decisions USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid) WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);
ALTER TABLE app.timeline_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.timeline_plans FORCE ROW LEVEL SECURITY;
CREATE POLICY timeline_plans_tenant_isolation ON app.timeline_plans USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid) WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);
ALTER TABLE app.audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.audit_events FORCE ROW LEVEL SECURITY;
CREATE POLICY audit_events_tenant_isolation ON app.audit_events USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid) WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);
ALTER TABLE app.idempotency_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.idempotency_records FORCE ROW LEVEL SECURITY;
CREATE POLICY idempotency_records_tenant_isolation ON app.idempotency_records USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid) WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);

CREATE OR REPLACE FUNCTION app.guard_case_state_transition() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
 IF OLD.state=NEW.state THEN RETURN NEW; END IF;
 IF OLD.state='intake' AND NEW.state='planning' THEN RETURN NEW; END IF;
 IF OLD.state='planning' AND NEW.state='advisor_review' AND EXISTS (SELECT 1 FROM app.planning_runs r WHERE r.organization_id=NEW.organization_id AND r.case_id=NEW.id AND r.case_revision=NEW.current_revision AND r.is_current AND r.state='review_required') THEN RETURN NEW; END IF;
 IF OLD.state='advisor_review' AND NEW.state='family_review' AND EXISTS (SELECT 1 FROM app.decision_briefs b WHERE b.organization_id=NEW.organization_id AND b.case_id=NEW.id AND b.case_revision=NEW.current_revision AND b.is_current) THEN RETURN NEW; END IF;
 IF OLD.state='advisor_review' AND NEW.state='planning' AND EXISTS (SELECT 1 FROM app.advisor_reviews a JOIN app.planning_runs r ON r.organization_id=a.organization_id AND r.id=a.planning_run_id WHERE a.organization_id=NEW.organization_id AND a.case_id=NEW.id AND a.case_revision=NEW.current_revision AND a.action IN ('reject','request_revision') AND r.is_current) THEN RETURN NEW; END IF;
 IF OLD.state='family_review' AND NEW.state='decided' AND EXISTS (SELECT 1 FROM app.family_decisions d WHERE d.organization_id=NEW.organization_id AND d.case_id=NEW.id) THEN RETURN NEW; END IF;
 IF OLD.state='decided' AND NEW.state='plan_ready' AND EXISTS (SELECT 1 FROM app.family_decisions d JOIN app.timeline_plans t ON t.organization_id=d.organization_id AND t.family_decision_id=d.id WHERE d.organization_id=NEW.organization_id AND d.case_id=NEW.id) THEN RETURN NEW; END IF;
 RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid case transition';
END; $$;

CREATE FUNCTION app.reject_m3b_mutation() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$ BEGIN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='immutable authority record'; END; $$;
CREATE FUNCTION app.guard_decision_brief_mutation() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
 IF OLD.is_current AND NOT NEW.is_current AND NEW.organization_id=OLD.organization_id AND NEW.id=OLD.id AND NEW.case_id=OLD.case_id AND NEW.case_revision=OLD.case_revision AND NEW.planning_run_id=OLD.planning_run_id AND NEW.advisor_review_id=OLD.advisor_review_id AND NEW.brief_version=OLD.brief_version AND NEW.policy_version=OLD.policy_version AND NEW.source_pack_id=OLD.source_pack_id AND NEW.source_pack_version=OLD.source_pack_version AND NEW.evidence_projection_sha256=OLD.evidence_projection_sha256 AND NEW.output_sha256=OLD.output_sha256 AND NEW.source_snapshot_date=OLD.source_snapshot_date AND NEW.family_safe_projection=OLD.family_safe_projection THEN RETURN NEW; END IF;
 RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='immutable decision brief';
END; $$;
CREATE TRIGGER advisor_reviews_immutable BEFORE UPDATE OR DELETE ON app.advisor_reviews FOR EACH ROW EXECUTE FUNCTION app.reject_m3b_mutation();
CREATE TRIGGER evidence_risk_acceptances_immutable BEFORE UPDATE OR DELETE ON app.evidence_risk_acceptances FOR EACH ROW EXECUTE FUNCTION app.reject_m3b_mutation();
CREATE TRIGGER decision_briefs_immutable BEFORE UPDATE ON app.decision_briefs FOR EACH ROW EXECUTE FUNCTION app.guard_decision_brief_mutation();
CREATE TRIGGER decision_briefs_delete_guard BEFORE DELETE ON app.decision_briefs FOR EACH ROW EXECUTE FUNCTION app.reject_m3b_mutation();
CREATE TRIGGER family_decisions_immutable BEFORE UPDATE OR DELETE ON app.family_decisions FOR EACH ROW EXECUTE FUNCTION app.reject_m3b_mutation();
CREATE TRIGGER timeline_plans_immutable BEFORE UPDATE OR DELETE ON app.timeline_plans FOR EACH ROW EXECUTE FUNCTION app.reject_m3b_mutation();
CREATE TRIGGER audit_events_immutable BEFORE UPDATE OR DELETE ON app.audit_events FOR EACH ROW EXECUTE FUNCTION app.reject_m3b_mutation();
CREATE TRIGGER idempotency_records_immutable BEFORE UPDATE OR DELETE ON app.idempotency_records FOR EACH ROW EXECUTE FUNCTION app.reject_m3b_mutation();

CREATE FUNCTION app.assert_m3b_context(p_org uuid,p_actor uuid,p_role text) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN
 IF NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid IS DISTINCT FROM p_org OR NULLIF(current_setting('night_voyager.actor_id',true),'')::uuid IS DISTINCT FROM p_actor OR NULLIF(current_setting('night_voyager.role',true),'') IS DISTINCT FROM p_role THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='actor context mismatch'; END IF;
END; $$;
CREATE FUNCTION auth.resolve_demo_session_with_csrf(p_session_digest bytea,p_csrf_digest bytea) RETURNS TABLE(organization_id uuid,actor_id uuid,role text,session_id uuid) LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
 SELECT s.organization_id,s.actor_id,s.role,s.id FROM auth.demo_sessions s WHERE s.session_digest=p_session_digest AND s.csrf_digest=p_csrf_digest AND s.revoked_at IS NULL AND s.expires_at>clock_timestamp()
$$;
CREATE FUNCTION app.seed_case_participants(p_org uuid,p_case uuid,p_advisor uuid,p_student uuid,p_parent uuid) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN
 INSERT INTO app.student_case_participants(organization_id,case_id,actor_id,role) VALUES(p_org,p_case,p_advisor,'advisor'),(p_org,p_case,p_student,'student'),(p_org,p_case,p_parent,'parent') ON CONFLICT DO NOTHING;
END; $$;
CREATE FUNCTION app.review_planning_run(p_org uuid,p_actor uuid,p_case uuid,p_run uuid,p_expected_revision integer,p_action text,p_review uuid,p_eligible jsonb,p_risks jsonb,p_notes text,p_brief uuid,p_projection jsonb,p_source_date date,p_key_hash text,p_request_hash text) RETURNS TABLE(review_id uuid,brief_id uuid,case_state text,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE prior app.idempotency_records%ROWTYPE; selected app.planning_runs%ROWTYPE; version integer; risk jsonb; canonical_projection jsonb; canonical_source_date date; pinned_intake text;
BEGIN
 PERFORM app.assert_m3b_context(p_org,p_actor,'advisor');
 SELECT * INTO prior FROM app.idempotency_records WHERE organization_id=p_org AND actor_id=p_actor AND operation='advisor_review' AND key_sha256=p_key_hash;
 IF FOUND THEN IF prior.request_sha256<>p_request_hash THEN RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='idempotency request mismatch'; END IF; RETURN QUERY SELECT prior.response_id,(SELECT id FROM app.decision_briefs WHERE organization_id=p_org AND advisor_review_id=prior.response_id),(SELECT state FROM app.student_cases WHERE organization_id=p_org AND id=p_case),true; RETURN; END IF;
 IF NOT EXISTS (SELECT 1 FROM app.student_case_participants WHERE organization_id=p_org AND case_id=p_case AND actor_id=p_actor AND role='advisor') THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='participant not assigned'; END IF;
 SELECT * INTO selected FROM app.planning_runs WHERE organization_id=p_org AND id=p_run AND case_id=p_case AND case_revision=p_expected_revision AND state='review_required' AND is_current FOR SHARE;
 IF NOT FOUND OR NOT EXISTS (SELECT 1 FROM app.student_cases WHERE organization_id=p_org AND id=p_case AND current_revision=p_expected_revision AND state='advisor_review') THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='review target is stale'; END IF;
 IF p_action NOT IN ('approve_for_consultation','reject','request_revision') THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid review action'; END IF;
 IF p_action<>'approve_for_consultation' AND (jsonb_array_length(p_eligible)<>0 OR jsonb_array_length(p_risks)<>0 OR p_brief IS NOT NULL) THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='non-approval review cannot grant eligibility or accept risk'; END IF;
 IF jsonb_array_length(p_eligible)<>(SELECT count(DISTINCT value) FROM jsonb_array_elements_text(p_eligible)) THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='eligible routes must be unique'; END IF;
 IF jsonb_array_length(p_risks)<>(SELECT count(*) FROM (SELECT DISTINCT risk->>'evidence_id',risk->>'kind' FROM jsonb_array_elements(p_risks) risk) unique_risks) THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='risk acceptances must be unique'; END IF;
 SELECT max(e.snapshot_date) INTO canonical_source_date FROM app.source_pack_entries e WHERE e.organization_id=p_org AND e.source_pack_id=selected.source_pack_id AND e.source_pack_version=selected.source_pack_version;
 SELECT r.student_preferences->>'intake' INTO pinned_intake FROM app.student_case_revisions r WHERE r.organization_id=p_org AND r.case_id=p_case AND r.revision=p_expected_revision;
 IF canonical_source_date IS NULL OR pinned_intake IS NULL THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='review target lacks pinned source facts'; END IF;
 SELECT jsonb_build_object('schema_version',1,'routes',COALESCE(jsonb_agg(jsonb_build_object('route_id',r.id,'country',r.country,'outcome',r.outcome,'reason_code',r.reason_code) ORDER BY r.country),'[]'::jsonb),'eligible_route_ids',p_eligible,'accepted_evidence_risks',p_risks,'intake',pinned_intake,'synthetic_proof',true) INTO canonical_projection FROM app.planning_routes r WHERE r.organization_id=p_org AND r.planning_run_id=p_run;
 SELECT COALESCE(max(review_version),0)+1 INTO version FROM app.advisor_reviews WHERE organization_id=p_org AND planning_run_id=p_run;
 INSERT INTO app.advisor_reviews VALUES(p_org,p_review,p_case,p_expected_revision,p_run,version,p_actor,p_action,p_eligible,p_risks,p_notes,clock_timestamp());
 FOR risk IN SELECT * FROM jsonb_array_elements(p_risks) LOOP
  IF COALESCE(risk->>'kind','') NOT IN ('optional','stale','unverified') OR NULLIF(btrim(risk->>'reason'),'') IS NULL THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='risk acceptance is not an explicit evidence risk'; END IF;
  IF NOT EXISTS (SELECT 1 FROM app.evidence_refs e WHERE e.organization_id=p_org AND e.id=(risk->>'evidence_id')::uuid AND e.source_pack_id=selected.source_pack_id AND e.source_pack_version=selected.source_pack_version) THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='risk acceptance does not belong to reviewed run'; END IF;
  INSERT INTO app.evidence_risk_acceptances VALUES(p_org,gen_random_uuid(),p_review,(risk->>'evidence_id')::uuid,risk->>'kind',risk->>'reason',clock_timestamp());
 END LOOP;
 IF p_action='approve_for_consultation' THEN
  IF p_source_date IS DISTINCT FROM canonical_source_date OR p_projection IS DISTINCT FROM canonical_projection THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='brief projection or source snapshot mismatch'; END IF;
  IF p_brief IS NULL OR jsonb_array_length(p_eligible)=0 OR EXISTS (SELECT 1 FROM jsonb_array_elements_text(p_eligible) e WHERE NOT EXISTS (SELECT 1 FROM app.planning_routes r WHERE r.organization_id=p_org AND r.planning_run_id=p_run AND r.id=e::uuid AND r.country='australia' AND r.outcome='recommended_with_condition')) THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='eligible routes violate reviewed run or timeline contract'; END IF;
  INSERT INTO app.decision_briefs VALUES(p_org,p_brief,p_case,p_expected_revision,p_run,p_review,1,selected.policy_version,selected.source_pack_id,selected.source_pack_version,selected.evidence_projection_sha256,selected.output_sha256,canonical_source_date,canonical_projection,true,clock_timestamp());
  UPDATE app.student_cases SET state='family_review' WHERE organization_id=p_org AND id=p_case AND state='advisor_review';
 ELSE
  UPDATE app.student_cases SET state='planning' WHERE organization_id=p_org AND id=p_case AND state='advisor_review';
 END IF;
 INSERT INTO app.audit_events VALUES(p_org,gen_random_uuid(),p_case,p_actor,'advisor_review',p_review,jsonb_build_object('action',p_action),clock_timestamp());
 INSERT INTO app.idempotency_records VALUES(p_org,p_actor,'advisor_review',p_key_hash,p_request_hash,'advisor_review',p_review,clock_timestamp());
 RETURN QUERY SELECT p_review,p_brief,(SELECT state FROM app.student_cases WHERE organization_id=p_org AND id=p_case),false;
END; $$;
CREATE FUNCTION app.decide_family_brief(p_org uuid,p_actor uuid,p_role text,p_brief uuid,p_expected_version integer,p_decision uuid,p_receipt uuid,p_route uuid,p_min bigint,p_max bigint,p_currency text,p_tradeoffs jsonb,p_made_by uuid,p_source text,p_timeline uuid,p_milestones jsonb,p_key_hash text,p_request_hash text) RETURNS TABLE(decision_id uuid,receipt_id uuid,timeline_id uuid,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE prior app.idempotency_records%ROWTYPE; selected app.decision_briefs%ROWTYPE; route_country text; route_outcome text; cost_cny bigint; case_budget jsonb; review_eligible jsonb; pinned_intake text; intake_year integer; canonical_milestones jsonb;
BEGIN
 PERFORM app.assert_m3b_context(p_org,p_actor,p_role);
 SELECT * INTO prior FROM app.idempotency_records WHERE organization_id=p_org AND actor_id=p_actor AND operation='family_decision' AND key_sha256=p_key_hash;
 IF FOUND THEN IF prior.request_sha256<>p_request_hash THEN RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='idempotency request mismatch'; END IF; RETURN QUERY SELECT prior.response_id,(SELECT d.receipt_id FROM app.family_decisions d WHERE d.organization_id=p_org AND d.id=prior.response_id),(SELECT t.id FROM app.timeline_plans t WHERE t.organization_id=p_org AND t.family_decision_id=prior.response_id),true; RETURN; END IF;
 SELECT * INTO selected FROM app.decision_briefs WHERE organization_id=p_org AND id=p_brief AND brief_version=p_expected_version AND is_current FOR UPDATE;
 IF NOT FOUND OR NOT EXISTS (SELECT 1 FROM app.student_cases WHERE organization_id=p_org AND id=selected.case_id AND current_revision=selected.case_revision AND state='family_review') THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='decision brief is stale'; END IF;
 IF p_role IN ('student','parent') THEN IF p_actor<>p_made_by OR p_source<>'direct' THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='direct decision actor mismatch'; END IF;
 ELSIF p_role='advisor' THEN IF p_source<>'family_consultation' OR NOT EXISTS (SELECT 1 FROM app.student_case_participants WHERE organization_id=p_org AND case_id=selected.case_id AND actor_id=p_made_by AND role IN ('student','parent')) THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='consultation decision maker mismatch'; END IF;
 ELSE RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='role cannot decide'; END IF;
 IF NOT EXISTS (SELECT 1 FROM app.student_case_participants WHERE organization_id=p_org AND case_id=selected.case_id AND actor_id=p_actor AND role=p_role) THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='participant not assigned'; END IF;
 SELECT a.eligible_route_ids INTO review_eligible FROM app.advisor_reviews a WHERE a.organization_id=p_org AND a.id=selected.advisor_review_id AND a.action='approve_for_consultation';
 SELECT country,outcome INTO route_country,route_outcome FROM app.planning_routes WHERE organization_id=p_org AND planning_run_id=selected.planning_run_id AND id=p_route;
 IF route_outcome IS NULL OR route_country<>'australia' OR route_outcome<>'recommended_with_condition' OR NOT (review_eligible ? p_route::text) THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='route is not eligible for deterministic timeline'; END IF;
 IF p_currency<>'CNY' OR p_min<=0 OR p_max<p_min THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid budget range'; END IF;
 IF route_country='australia' THEN
  IF NOT (p_tradeoffs ? 'budget_elasticity') THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='budget elasticity trade-off required'; END IF;
  SELECT round((tuition_minor+living_minor)*fx_rate)::bigint INTO cost_cny FROM app.cost_evidence WHERE organization_id=p_org AND planning_run_id=selected.planning_run_id AND country='australia';
  SELECT family_preferences->'budget' INTO case_budget FROM app.student_case_revisions WHERE organization_id=p_org AND case_id=selected.case_id AND revision=selected.case_revision;
  IF cost_cny NOT BETWEEN p_min AND p_max OR p_max>(case_budget->>'hard_ceiling_minor')::bigint THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='budget range conflicts with pinned facts'; END IF;
 END IF;
 SELECT r.student_preferences->>'intake' INTO pinned_intake FROM app.student_case_revisions r WHERE r.organization_id=p_org AND r.case_id=selected.case_id AND r.revision=selected.case_revision;
 IF pinned_intake !~ '^[0-9]{4}-02$' THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='unsupported pinned intake timeline'; END IF;
 intake_year := split_part(pinned_intake,'-',1)::integer;
 canonical_milestones := jsonb_build_array(jsonb_build_object('key','documents','due_date',make_date(intake_year-1,9,1)),jsonb_build_object('key','application','due_date',make_date(intake_year-1,10,15)),jsonb_build_object('key','visa','due_date',make_date(intake_year-1,12,15)),jsonb_build_object('key','arrival','due_date',make_date(intake_year,1,20)));
 IF p_milestones IS DISTINCT FROM canonical_milestones THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='timeline does not match deterministic pinned facts'; END IF;
 INSERT INTO app.family_decisions VALUES(p_org,p_decision,p_receipt,selected.case_id,p_brief,p_expected_version,p_route,p_min,p_max,p_currency,p_tradeoffs,p_made_by,p_actor,p_source,clock_timestamp(),selected.planning_run_id);
 UPDATE app.student_cases SET state='decided' WHERE organization_id=p_org AND id=selected.case_id AND state='family_review';
 INSERT INTO app.timeline_plans VALUES(p_org,p_timeline,p_decision,1,route_country,pinned_intake,canonical_milestones,clock_timestamp());
 UPDATE app.student_cases SET state='plan_ready' WHERE organization_id=p_org AND id=selected.case_id AND state='decided';
 INSERT INTO app.audit_events VALUES(p_org,gen_random_uuid(),selected.case_id,p_actor,'family_decision',p_decision,jsonb_build_object('receipt_id',p_receipt),clock_timestamp());
 INSERT INTO app.audit_events VALUES(p_org,gen_random_uuid(),selected.case_id,p_actor,'timeline_plan',p_timeline,'{}',clock_timestamp());
 UPDATE app.decision_briefs SET is_current=false WHERE organization_id=p_org AND id=p_brief;
 INSERT INTO app.idempotency_records VALUES(p_org,p_actor,'family_decision',p_key_hash,p_request_hash,'family_decision',p_decision,clock_timestamp());
 RETURN QUERY SELECT p_decision,p_receipt,p_timeline,false;
END; $$;

REVOKE ALL ON FUNCTION app.assert_m3b_context(uuid,uuid,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION auth.resolve_demo_session_with_csrf(bytea,bytea) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.seed_case_participants(uuid,uuid,uuid,uuid,uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.review_planning_run(uuid,uuid,uuid,uuid,integer,text,uuid,jsonb,jsonb,text,uuid,jsonb,date,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.decide_family_brief(uuid,uuid,text,uuid,integer,uuid,uuid,uuid,bigint,bigint,text,jsonb,uuid,text,uuid,jsonb,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.seed_case_participants(uuid,uuid,uuid,uuid,uuid) TO night_voyager_migrator;
GRANT EXECUTE ON FUNCTION auth.resolve_demo_session_with_csrf(bytea,bytea) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.review_planning_run(uuid,uuid,uuid,uuid,integer,text,uuid,jsonb,jsonb,text,uuid,jsonb,date,text,text) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.decide_family_brief(uuid,uuid,text,uuid,integer,uuid,uuid,uuid,bigint,bigint,text,jsonb,uuid,text,uuid,jsonb,text,text) TO night_voyager_api;
GRANT SELECT ON app.student_case_participants,app.advisor_reviews,app.evidence_risk_acceptances,app.decision_briefs,app.family_decisions,app.timeline_plans,app.audit_events TO night_voyager_api;
"""


def upgrade() -> None:
    for statement in _split_statements(UPGRADE_SQL):
        op.execute(statement)


def downgrade() -> None:
    op.execute("ALTER TABLE app.student_cases NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE app.student_cases DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE app.student_cases DISABLE TRIGGER student_cases_state_guard")
    op.execute("UPDATE app.student_cases SET state='advisor_review' WHERE state IN ('family_review','decided','plan_ready')")
    op.execute("ALTER TABLE app.student_cases ENABLE TRIGGER student_cases_state_guard")
    op.execute("ALTER TABLE app.student_cases ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE app.student_cases FORCE ROW LEVEL SECURITY")
    op.execute("DROP FUNCTION IF EXISTS auth.resolve_demo_session_with_csrf(bytea,bytea)")
    op.execute("DROP FUNCTION IF EXISTS app.decide_family_brief(uuid,uuid,text,uuid,integer,uuid,uuid,uuid,bigint,bigint,text,jsonb,uuid,text,uuid,jsonb,text,text)")
    op.execute("DROP FUNCTION IF EXISTS app.review_planning_run(uuid,uuid,uuid,uuid,integer,text,uuid,jsonb,jsonb,text,uuid,jsonb,date,text,text)")
    op.execute("DROP FUNCTION IF EXISTS app.seed_case_participants(uuid,uuid,uuid,uuid,uuid)")
    op.execute("DROP FUNCTION IF EXISTS app.assert_m3b_context(uuid,uuid,text)")
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE app.{table}")
    op.execute("DROP FUNCTION IF EXISTS app.reject_m3b_mutation()")
    op.execute("DROP FUNCTION IF EXISTS app.guard_decision_brief_mutation()")
    op.execute("ALTER TABLE app.student_cases DROP CONSTRAINT student_cases_state_check")
    op.execute("ALTER TABLE app.student_cases ADD CONSTRAINT student_cases_state_check CHECK (state IN ('intake','planning','advisor_review'))")
    op.execute("""CREATE OR REPLACE FUNCTION app.guard_case_state_transition() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$ BEGIN IF OLD.state=NEW.state THEN RETURN NEW; END IF; IF OLD.state='intake' AND NEW.state='planning' THEN RETURN NEW; END IF; IF OLD.state='planning' AND NEW.state='advisor_review' AND EXISTS (SELECT 1 FROM app.planning_runs r WHERE r.organization_id=NEW.organization_id AND r.case_id=NEW.id AND r.case_revision=NEW.current_revision AND r.is_current AND r.state='review_required') THEN RETURN NEW; END IF; RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid case transition'; END; $$""")


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
