# ruff: noqa: E501
"""Create the M3A case, Evidence, and deterministic planning boundary."""

from collections.abc import Sequence

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "student_cases",
    "student_case_revisions",
    "source_packs",
    "source_pack_entries",
    "evidence_refs",
    "planning_runs",
    "planning_routes",
    "comparison_dimensions",
    "comparison_dimension_evidence_refs",
    "cost_evidence",
    "ranking_evidence",
)

UPGRADE_SQL = r"""
CREATE TABLE app.student_cases (
  organization_id uuid NOT NULL, id uuid NOT NULL,
  state text NOT NULL DEFAULT 'intake' CHECK (state IN ('intake','planning','advisor_review')),
  current_revision integer CHECK (current_revision > 0),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id, id), FOREIGN KEY (organization_id) REFERENCES app.organizations(id)
);
CREATE TABLE app.student_case_revisions (
  organization_id uuid NOT NULL, case_id uuid NOT NULL, revision integer NOT NULL CHECK (revision > 0),
  schema_version integer NOT NULL CHECK (schema_version = 1),
  student_preferences jsonb NOT NULL, family_preferences jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id, case_id, revision),
  FOREIGN KEY (organization_id, case_id) REFERENCES app.student_cases(organization_id, id)
);
CREATE TABLE app.source_packs (
  organization_id uuid NOT NULL, id uuid NOT NULL, version integer NOT NULL CHECK (version > 0),
  schema_version integer NOT NULL CHECK (schema_version = 1),
  manifest_sha256 text NOT NULL CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id, id, version), FOREIGN KEY (organization_id) REFERENCES app.organizations(id)
);
CREATE TABLE app.source_pack_entries (
  organization_id uuid NOT NULL, source_pack_id uuid NOT NULL, source_pack_version integer NOT NULL,
  id uuid NOT NULL, declared_path text NOT NULL CHECK (declared_path !~ '(^|/)\.\.(/|$)' AND declared_path !~ '^/'),
  sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'), snapshot_date date NOT NULL,
  publisher text NOT NULL, institution text NOT NULL, canonical_url text NOT NULL,
  freshness_days integer NOT NULL CHECK (freshness_days > 0),
  redistribution_class text NOT NULL CHECK (redistribution_class IN ('synthetic_public','link_only')),
  evidence_class text NOT NULL CHECK (evidence_class IN ('synthetic_demo','institutional','government')),
  coverage jsonb NOT NULL, known_gaps jsonb NOT NULL,
  PRIMARY KEY (organization_id, source_pack_id, source_pack_version, id),
  FOREIGN KEY (organization_id, source_pack_id, source_pack_version) REFERENCES app.source_packs(organization_id, id, version)
);
CREATE TABLE app.evidence_refs (
  organization_id uuid NOT NULL, id uuid NOT NULL, source_pack_id uuid NOT NULL,
  source_pack_version integer NOT NULL, source_entry_id uuid NOT NULL, claim text NOT NULL,
  authority text NOT NULL CHECK (authority IN ('untrusted_candidate','accepted_synthetic_demo')),
  source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
  PRIMARY KEY (organization_id, id),
  UNIQUE (organization_id, source_pack_id, source_pack_version, claim),
  FOREIGN KEY (organization_id, source_pack_id, source_pack_version, source_entry_id)
    REFERENCES app.source_pack_entries(organization_id, source_pack_id, source_pack_version, id)
);
CREATE TABLE app.planning_runs (
  organization_id uuid NOT NULL, id uuid NOT NULL, case_id uuid NOT NULL,
  case_revision integer NOT NULL, source_pack_id uuid NOT NULL, source_pack_version integer NOT NULL,
  policy_version text NOT NULL, evidence_projection_sha256 text NOT NULL CHECK (evidence_projection_sha256 ~ '^[0-9a-f]{64}$'),
  state text NOT NULL CHECK (state IN ('draft','collecting_evidence','synthesizing','failed','blocked','review_required')),
  reason_code text, output_sha256 text CHECK (output_sha256 ~ '^[0-9a-f]{64}$'),
  supersedes_run_id uuid, is_current boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id, id),
  FOREIGN KEY (organization_id, case_id, case_revision) REFERENCES app.student_case_revisions(organization_id, case_id, revision),
  FOREIGN KEY (organization_id, source_pack_id, source_pack_version) REFERENCES app.source_packs(organization_id, id, version),
  FOREIGN KEY (organization_id, supersedes_run_id) REFERENCES app.planning_runs(organization_id, id)
);
CREATE UNIQUE INDEX planning_runs_one_current_per_case ON app.planning_runs(organization_id,case_id) WHERE is_current;
CREATE TABLE app.planning_routes (
  organization_id uuid NOT NULL, planning_run_id uuid NOT NULL, id uuid NOT NULL,
  country text NOT NULL CHECK (country IN ('australia','japan','malaysia')),
  outcome text NOT NULL CHECK (outcome IN ('recommended_with_condition','conditional','blocked')),
  reason_code text NOT NULL, PRIMARY KEY (organization_id, planning_run_id, id),
  UNIQUE (organization_id, planning_run_id, country),
  FOREIGN KEY (organization_id, planning_run_id) REFERENCES app.planning_runs(organization_id, id)
);
CREATE TABLE app.comparison_dimensions (
  organization_id uuid NOT NULL, planning_run_id uuid NOT NULL, route_id uuid NOT NULL, id uuid NOT NULL,
  dimension_key text NOT NULL, outcome text NOT NULL CHECK (outcome IN ('supported','conditional','blocked')),
  reason_code text NOT NULL, PRIMARY KEY (organization_id, planning_run_id, route_id, id),
  FOREIGN KEY (organization_id, planning_run_id, route_id) REFERENCES app.planning_routes(organization_id, planning_run_id, id)
);
CREATE TABLE app.comparison_dimension_evidence_refs (
  organization_id uuid NOT NULL, planning_run_id uuid NOT NULL, route_id uuid NOT NULL,
  dimension_id uuid NOT NULL, evidence_ref_id uuid NOT NULL,
  evidence_role text NOT NULL CHECK (evidence_role IN ('program_fit','tuition','living_cost','fx','ranking')),
  PRIMARY KEY (organization_id, planning_run_id, route_id, dimension_id, evidence_ref_id, evidence_role),
  FOREIGN KEY (organization_id, planning_run_id, route_id, dimension_id) REFERENCES app.comparison_dimensions(organization_id, planning_run_id, route_id, id),
  FOREIGN KEY (organization_id, evidence_ref_id) REFERENCES app.evidence_refs(organization_id, id)
);
CREATE TABLE app.cost_evidence (
  organization_id uuid NOT NULL, planning_run_id uuid NOT NULL, id uuid NOT NULL,
  country text NOT NULL, intake text NOT NULL, period text NOT NULL CHECK (period = 'program_total'),
  currency text NOT NULL CHECK (currency = 'AUD'), tuition_minor bigint NOT NULL CHECK (tuition_minor > 0),
  living_minor bigint NOT NULL CHECK (living_minor > 0), fx_rate numeric NOT NULL CHECK (fx_rate > 0),
  fx_source text NOT NULL, fx_date date NOT NULL, tuition_evidence_id uuid NOT NULL,
  living_evidence_id uuid NOT NULL, fx_evidence_id uuid NOT NULL,
  PRIMARY KEY (organization_id, planning_run_id, id),
  FOREIGN KEY (organization_id, planning_run_id) REFERENCES app.planning_runs(organization_id, id),
  FOREIGN KEY (organization_id, tuition_evidence_id) REFERENCES app.evidence_refs(organization_id, id),
  FOREIGN KEY (organization_id, living_evidence_id) REFERENCES app.evidence_refs(organization_id, id),
  FOREIGN KEY (organization_id, fx_evidence_id) REFERENCES app.evidence_refs(organization_id, id)
);
CREATE TABLE app.ranking_evidence (
  organization_id uuid NOT NULL, planning_run_id uuid NOT NULL, id uuid NOT NULL,
  country text NOT NULL, ranking_system text NOT NULL, rank integer NOT NULL CHECK (rank > 0),
  publication_year integer NOT NULL CHECK (publication_year >= 2000), evidence_ref_id uuid NOT NULL,
  PRIMARY KEY (organization_id, planning_run_id, id),
  FOREIGN KEY (organization_id, planning_run_id) REFERENCES app.planning_runs(organization_id, id),
  FOREIGN KEY (organization_id, evidence_ref_id) REFERENCES app.evidence_refs(organization_id, id)
);

ALTER TABLE app.student_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.student_cases FORCE ROW LEVEL SECURITY;
CREATE POLICY student_cases_tenant_isolation ON app.student_cases USING (organization_id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid) WITH CHECK (organization_id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid);
ALTER TABLE app.student_case_revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.student_case_revisions FORCE ROW LEVEL SECURITY;
CREATE POLICY student_case_revisions_tenant_isolation ON app.student_case_revisions USING (organization_id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid) WITH CHECK (organization_id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid);
ALTER TABLE app.source_packs ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.source_packs FORCE ROW LEVEL SECURITY;
CREATE POLICY source_packs_tenant_isolation ON app.source_packs USING (organization_id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid) WITH CHECK (organization_id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid);
ALTER TABLE app.source_pack_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.source_pack_entries FORCE ROW LEVEL SECURITY;
CREATE POLICY source_pack_entries_tenant_isolation ON app.source_pack_entries USING (organization_id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid) WITH CHECK (organization_id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid);
ALTER TABLE app.evidence_refs ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.evidence_refs FORCE ROW LEVEL SECURITY;
CREATE POLICY evidence_refs_tenant_isolation ON app.evidence_refs USING (organization_id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid) WITH CHECK (organization_id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid);
ALTER TABLE app.planning_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.planning_runs FORCE ROW LEVEL SECURITY;
CREATE POLICY planning_runs_tenant_isolation ON app.planning_runs USING (organization_id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid) WITH CHECK (organization_id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid);
ALTER TABLE app.planning_routes ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.planning_routes FORCE ROW LEVEL SECURITY;
CREATE POLICY planning_routes_tenant_isolation ON app.planning_routes USING (organization_id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid) WITH CHECK (organization_id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid);
ALTER TABLE app.comparison_dimensions ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.comparison_dimensions FORCE ROW LEVEL SECURITY;
CREATE POLICY comparison_dimensions_tenant_isolation ON app.comparison_dimensions USING (organization_id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid) WITH CHECK (organization_id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid);
ALTER TABLE app.comparison_dimension_evidence_refs ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.comparison_dimension_evidence_refs FORCE ROW LEVEL SECURITY;
CREATE POLICY comparison_dimension_evidence_refs_tenant_isolation ON app.comparison_dimension_evidence_refs USING (organization_id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid) WITH CHECK (organization_id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid);
ALTER TABLE app.cost_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.cost_evidence FORCE ROW LEVEL SECURITY;
CREATE POLICY cost_evidence_tenant_isolation ON app.cost_evidence USING (organization_id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid) WITH CHECK (organization_id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid);
ALTER TABLE app.ranking_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.ranking_evidence FORCE ROW LEVEL SECURITY;
CREATE POLICY ranking_evidence_tenant_isolation ON app.ranking_evidence USING (organization_id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid) WITH CHECK (organization_id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid);

CREATE FUNCTION app.guard_evidence_provenance() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
DECLARE entry app.source_pack_entries%ROWTYPE;
BEGIN
  SELECT * INTO entry FROM app.source_pack_entries e
  WHERE (e.organization_id,e.source_pack_id,e.source_pack_version,e.id) = (NEW.organization_id,NEW.source_pack_id,NEW.source_pack_version,NEW.source_entry_id);
  IF NOT FOUND OR entry.sha256 <> NEW.source_sha256 OR NOT (entry.coverage ? NEW.claim) THEN
    RAISE EXCEPTION USING ERRCODE = 'NV004', MESSAGE = 'evidence provenance mismatch';
  END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER evidence_refs_provenance_guard BEFORE INSERT OR UPDATE ON app.evidence_refs FOR EACH ROW EXECUTE FUNCTION app.guard_evidence_provenance();

CREATE FUNCTION app.guard_case_current_revision() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  IF NEW.current_revision IS NOT NULL AND NOT EXISTS (SELECT 1 FROM app.student_case_revisions r WHERE r.organization_id=NEW.organization_id AND r.case_id=NEW.id AND r.revision=NEW.current_revision) THEN
    RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='current revision does not exist';
  END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER student_cases_current_revision_guard BEFORE INSERT OR UPDATE OF current_revision ON app.student_cases FOR EACH ROW EXECUTE FUNCTION app.guard_case_current_revision();

CREATE FUNCTION app.guard_case_state_transition() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  IF OLD.state=NEW.state THEN RETURN NEW; END IF;
  IF OLD.state='intake' AND NEW.state='planning' THEN RETURN NEW; END IF;
  IF OLD.state='planning' AND NEW.state='advisor_review' AND EXISTS (
    SELECT 1 FROM app.planning_runs r
    WHERE r.organization_id=NEW.organization_id AND r.case_id=NEW.id
      AND r.case_revision=NEW.current_revision AND r.is_current AND r.state='review_required'
  ) THEN RETURN NEW; END IF;
  RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid case transition';
END; $$;
CREATE TRIGGER student_cases_state_guard BEFORE UPDATE OF state ON app.student_cases FOR EACH ROW EXECUTE FUNCTION app.guard_case_state_transition();

CREATE FUNCTION app.guard_run_transition() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
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
CREATE TRIGGER planning_runs_transition_guard BEFORE UPDATE ON app.planning_runs FOR EACH ROW EXECUTE FUNCTION app.guard_run_transition();

CREATE FUNCTION app.advance_case_on_review_required() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  IF NEW.state='review_required' AND NEW.is_current THEN
    UPDATE app.student_cases SET state='advisor_review'
    WHERE organization_id=NEW.organization_id AND id=NEW.case_id
      AND current_revision=NEW.case_revision AND state='planning';
    IF NOT FOUND THEN
      RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='case handoff input is stale';
    END IF;
  END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER planning_runs_handoff AFTER UPDATE OF state ON app.planning_runs FOR EACH ROW EXECUTE FUNCTION app.advance_case_on_review_required();

CREATE FUNCTION app.guard_nonterminal_child() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
DECLARE run_state text;
BEGIN
  SELECT state INTO run_state FROM app.planning_runs WHERE organization_id=NEW.organization_id AND id=NEW.planning_run_id;
  IF run_state IS NULL OR run_state IN ('failed','blocked','review_required') THEN RAISE EXCEPTION USING ERRCODE='NV005', MESSAGE='terminal planning output is immutable'; END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER planning_routes_terminal_guard BEFORE INSERT OR UPDATE ON app.planning_routes FOR EACH ROW EXECUTE FUNCTION app.guard_nonterminal_child();
CREATE TRIGGER comparison_dimensions_terminal_guard BEFORE INSERT OR UPDATE ON app.comparison_dimensions FOR EACH ROW EXECUTE FUNCTION app.guard_nonterminal_child();
CREATE TRIGGER comparison_links_terminal_guard BEFORE INSERT OR UPDATE ON app.comparison_dimension_evidence_refs FOR EACH ROW EXECUTE FUNCTION app.guard_nonterminal_child();
CREATE TRIGGER cost_evidence_terminal_guard BEFORE INSERT OR UPDATE ON app.cost_evidence FOR EACH ROW EXECUTE FUNCTION app.guard_nonterminal_child();
CREATE TRIGGER ranking_evidence_terminal_guard BEFORE INSERT OR UPDATE ON app.ranking_evidence FOR EACH ROW EXECUTE FUNCTION app.guard_nonterminal_child();

CREATE FUNCTION app.guard_link_provenance() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
DECLARE evidence_claim text;
BEGIN
  SELECT e.claim INTO evidence_claim FROM app.planning_runs r JOIN app.evidence_refs e ON e.organization_id=r.organization_id AND e.id=NEW.evidence_ref_id AND e.source_pack_id=r.source_pack_id AND e.source_pack_version=r.source_pack_version WHERE r.organization_id=NEW.organization_id AND r.id=NEW.planning_run_id;
  IF evidence_claim IS NULL OR NOT ((NEW.evidence_role='program_fit' AND evidence_claim LIKE '%_program_fit') OR (NEW.evidence_role='tuition' AND evidence_claim='australia_tuition') OR (NEW.evidence_role='living_cost' AND evidence_claim='australia_living_cost') OR (NEW.evidence_role='fx' AND evidence_claim='australia_fx') OR (NEW.evidence_role='ranking' AND evidence_claim='australia_ranking')) THEN
    RAISE EXCEPTION USING ERRCODE='NV004', MESSAGE='cross-pack evidence link';
  END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER comparison_links_provenance_guard BEFORE INSERT OR UPDATE ON app.comparison_dimension_evidence_refs FOR EACH ROW EXECUTE FUNCTION app.guard_link_provenance();

CREATE FUNCTION app.guard_cost_provenance() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM app.planning_runs r JOIN app.evidence_refs t ON t.organization_id=r.organization_id AND t.id=NEW.tuition_evidence_id AND t.source_pack_id=r.source_pack_id AND t.source_pack_version=r.source_pack_version AND t.claim='australia_tuition' JOIN app.evidence_refs l ON l.organization_id=r.organization_id AND l.id=NEW.living_evidence_id AND l.source_pack_id=r.source_pack_id AND l.source_pack_version=r.source_pack_version AND l.claim='australia_living_cost' JOIN app.evidence_refs f ON f.organization_id=r.organization_id AND f.id=NEW.fx_evidence_id AND f.source_pack_id=r.source_pack_id AND f.source_pack_version=r.source_pack_version AND f.claim='australia_fx' WHERE r.organization_id=NEW.organization_id AND r.id=NEW.planning_run_id) THEN
    RAISE EXCEPTION USING ERRCODE='NV004', MESSAGE='cost evidence provenance mismatch';
  END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER cost_evidence_provenance_guard BEFORE INSERT OR UPDATE ON app.cost_evidence FOR EACH ROW EXECUTE FUNCTION app.guard_cost_provenance();

CREATE FUNCTION app.guard_ranking_provenance() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM app.planning_runs r JOIN app.evidence_refs e ON e.organization_id=r.organization_id AND e.id=NEW.evidence_ref_id AND e.source_pack_id=r.source_pack_id AND e.source_pack_version=r.source_pack_version AND e.claim='australia_ranking' WHERE r.organization_id=NEW.organization_id AND r.id=NEW.planning_run_id) THEN
    RAISE EXCEPTION USING ERRCODE='NV004', MESSAGE='ranking evidence provenance mismatch';
  END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER ranking_evidence_provenance_guard BEFORE INSERT OR UPDATE ON app.ranking_evidence FOR EACH ROW EXECUTE FUNCTION app.guard_ranking_provenance();

CREATE FUNCTION app.assert_context(p_org uuid) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN
 IF NULLIF(current_setting('night_voyager.organization_id', true),'')::uuid IS DISTINCT FROM p_org THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='tenant context mismatch'; END IF;
END; $$;

CREATE FUNCTION app.publish_case_revision(p_org uuid,p_case uuid,p_expected integer,p_revision integer,p_student jsonb,p_family jsonb) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE actual integer;
BEGIN
 PERFORM app.assert_context(p_org);
 INSERT INTO app.student_cases(organization_id,id) VALUES(p_org,p_case) ON CONFLICT DO NOTHING;
 SELECT current_revision INTO actual FROM app.student_cases WHERE organization_id=p_org AND id=p_case FOR UPDATE;
 IF actual IS DISTINCT FROM p_expected OR p_revision <> COALESCE(p_expected,0)+1 THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='stale case revision'; END IF;
 INSERT INTO app.student_case_revisions(organization_id,case_id,revision,schema_version,student_preferences,family_preferences) VALUES(p_org,p_case,p_revision,1,p_student,p_family);
 UPDATE app.student_cases SET current_revision=p_revision WHERE organization_id=p_org AND id=p_case;
END; $$;

CREATE FUNCTION app.transition_case(p_org uuid,p_case uuid,p_expected text,p_target text) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN
 PERFORM app.assert_context(p_org);
 IF NOT (p_expected='intake' AND p_target='planning') THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid case transition'; END IF;
 UPDATE app.student_cases SET state=p_target WHERE organization_id=p_org AND id=p_case AND state=p_expected;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='stale case state'; END IF;
END; $$;

CREATE FUNCTION app.persist_source_pack(p_org uuid,p_pack uuid,p_version integer,p_manifest_sha text,p_entries jsonb) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE item jsonb;
BEGIN
 PERFORM app.assert_context(p_org);
 INSERT INTO app.source_packs(organization_id,id,version,schema_version,manifest_sha256) VALUES(p_org,p_pack,p_version,1,p_manifest_sha);
 FOR item IN SELECT * FROM jsonb_array_elements(p_entries) LOOP
  INSERT INTO app.source_pack_entries VALUES(p_org,p_pack,p_version,(item->>'entry_id')::uuid,item->>'path',item->>'sha256',(item->>'snapshot_date')::date,item->>'publisher',item->>'institution',item->>'canonical_url',(item->>'freshness_days')::integer,item->>'redistribution_class',item->>'evidence_class',item->'coverage',item->'known_gaps');
 END LOOP;
END; $$;

CREATE FUNCTION app.persist_evidence_ref(p_org uuid,p_id uuid,p_pack uuid,p_version integer,p_entry uuid,p_claim text,p_authority text,p_hash text) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN
 PERFORM app.assert_context(p_org);
 INSERT INTO app.evidence_refs VALUES(p_org,p_id,p_pack,p_version,p_entry,p_claim,p_authority,p_hash);
END; $$;

CREATE FUNCTION app.persist_planning_result(p_org uuid,p_run uuid,p_case uuid,p_revision integer,p_pack uuid,p_version integer,p_policy text,p_evidence_hash text,p_state text,p_reason text,p_output_hash text,p_supersedes uuid,p_output jsonb) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
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

REVOKE ALL ON FUNCTION app.assert_context(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.publish_case_revision(uuid,uuid,integer,integer,jsonb,jsonb) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.transition_case(uuid,uuid,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.persist_source_pack(uuid,uuid,integer,text,jsonb) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.persist_evidence_ref(uuid,uuid,uuid,integer,uuid,text,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.persist_planning_result(uuid,uuid,uuid,integer,uuid,integer,text,text,text,text,text,uuid,jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.publish_case_revision(uuid,uuid,integer,integer,jsonb,jsonb) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.transition_case(uuid,uuid,text,text) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.persist_source_pack(uuid,uuid,integer,text,jsonb) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.persist_evidence_ref(uuid,uuid,uuid,integer,uuid,text,text,text) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.persist_planning_result(uuid,uuid,uuid,integer,uuid,integer,text,text,text,text,text,uuid,jsonb) TO night_voyager_api;
GRANT SELECT ON app.student_cases,app.student_case_revisions,app.source_packs,app.source_pack_entries,app.evidence_refs,app.planning_runs,app.planning_routes,app.comparison_dimensions,app.comparison_dimension_evidence_refs,app.cost_evidence,app.ranking_evidence TO night_voyager_api,night_voyager_worker;
"""


def upgrade() -> None:
    for statement in _split_statements(UPGRADE_SQL):
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS app.persist_planning_result(uuid,uuid,uuid,integer,uuid,integer,text,text,text,text,text,uuid,jsonb)")
    op.execute("DROP FUNCTION IF EXISTS app.persist_evidence_ref(uuid,uuid,uuid,integer,uuid,text,text,text)")
    op.execute("DROP FUNCTION IF EXISTS app.persist_source_pack(uuid,uuid,integer,text,jsonb)")
    op.execute("DROP FUNCTION IF EXISTS app.transition_case(uuid,uuid,text,text)")
    op.execute("DROP FUNCTION IF EXISTS app.publish_case_revision(uuid,uuid,integer,integer,jsonb,jsonb)")
    op.execute("DROP FUNCTION IF EXISTS app.assert_context(uuid)")
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE app.{table}")
    op.execute("DROP FUNCTION IF EXISTS app.guard_link_provenance()")
    op.execute("DROP FUNCTION IF EXISTS app.guard_cost_provenance()")
    op.execute("DROP FUNCTION IF EXISTS app.guard_ranking_provenance()")
    op.execute("DROP FUNCTION IF EXISTS app.guard_nonterminal_child()")
    op.execute("DROP FUNCTION IF EXISTS app.advance_case_on_review_required()")
    op.execute("DROP FUNCTION IF EXISTS app.guard_run_transition()")
    op.execute("DROP FUNCTION IF EXISTS app.guard_evidence_provenance()")
    op.execute("DROP FUNCTION IF EXISTS app.guard_case_current_revision()")
    op.execute("DROP FUNCTION IF EXISTS app.guard_case_state_transition()")


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
