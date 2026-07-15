# ruff: noqa: E501
"""Create the governed DRA candidate ledger and atomic promotion authority."""

from collections.abc import Sequence

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("dra_research_candidates", "external_evidence_verifications")

UPGRADE_SQL = r"""
ALTER TABLE app.evidence_refs DROP CONSTRAINT evidence_refs_authority_check;
ALTER TABLE app.evidence_refs ADD CONSTRAINT evidence_refs_authority_check CHECK (authority IN ('untrusted_candidate','accepted_synthetic_demo','externally_verified'));

CREATE TABLE app.dra_research_candidates (
  organization_id uuid NOT NULL,
  id uuid NOT NULL,
  case_id uuid NOT NULL,
  case_revision integer NOT NULL CHECK (case_revision > 0),
  producer_release text NOT NULL CHECK (producer_release = 'v0.1.3'),
  producer_commit text NOT NULL CHECK (producer_commit = '87b2a8e335385eb865086f7a69fe2b190567cfa2'),
  contract_schema text NOT NULL CHECK (contract_schema = 'dra.downstream-consumer.v1'),
  fixture_sha256 text NOT NULL CHECK (fixture_sha256 = 'cc602576115ff9b41b0f07fa5f6ee88db15424760a78ab4611675e62e19a8157'),
  profile_id text NOT NULL CHECK (profile_id = 'generic'),
  request_identity_sha256 text NOT NULL CHECK (request_identity_sha256 ~ '^[0-9a-f]{64}$'),
  run_id text NOT NULL CHECK (length(run_id) BETWEEN 1 AND 200),
  artifact_id text NOT NULL CHECK (artifact_id = 'research-report.md'),
  artifact_kind text NOT NULL CHECK (artifact_kind = 'research_report_markdown'),
  artifact_media_type text NOT NULL CHECK (artifact_media_type = 'text/markdown'),
  artifact_byte_length integer NOT NULL CHECK (artifact_byte_length BETWEEN 1 AND 1048576),
  artifact_sha256 text NOT NULL CHECK (artifact_sha256 ~ '^[0-9a-f]{64}$'),
  ordered_evidence jsonb NOT NULL CHECK (jsonb_typeof(ordered_evidence) = 'array' AND jsonb_array_length(ordered_evidence) > 0),
  import_request_sha256 text NOT NULL CHECK (import_request_sha256 ~ '^[0-9a-f]{64}$'),
  created_by_actor_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id,id),
  FOREIGN KEY (organization_id,case_id,case_revision) REFERENCES app.student_case_revisions(organization_id,case_id,revision),
  FOREIGN KEY (organization_id,created_by_actor_id) REFERENCES app.actors(organization_id,id)
);

CREATE TABLE app.external_evidence_verifications (
  organization_id uuid NOT NULL,
  id uuid NOT NULL,
  candidate_id uuid NOT NULL,
  case_id uuid NOT NULL,
  case_revision integer NOT NULL CHECK (case_revision > 0),
  actor_id uuid NOT NULL,
  dra_evidence_id text NOT NULL CHECK (length(dra_evidence_id) BETWEEN 1 AND 200),
  decision text NOT NULL CHECK (decision IN ('approve','reject')),
  reason text NOT NULL CHECK (length(btrim(reason)) BETWEEN 1 AND 2000),
  claim text NOT NULL DEFAULT 'australia_program_fit' CHECK (claim = 'australia_program_fit'),
  evidence_role text NOT NULL DEFAULT 'program_fit' CHECK (evidence_role = 'program_fit'),
  authority text NOT NULL DEFAULT 'externally_verified' CHECK (authority = 'externally_verified'),
  source_url text,
  publisher text,
  institution text,
  snapshot_date date,
  freshness_days integer CHECK (freshness_days IS NULL OR freshness_days > 0),
  redistribution_class text CHECK (redistribution_class IS NULL OR redistribution_class = 'link_only'),
  evidence_class text CHECK (evidence_class IS NULL OR evidence_class IN ('institutional','government')),
  declared_path text CHECK (declared_path IS NULL OR (declared_path !~ '(^|/)\.\.(/|$)' AND declared_path !~ '^/')),
  source_byte_length integer CHECK (source_byte_length IS NULL OR source_byte_length > 0),
  source_sha256 text CHECK (source_sha256 IS NULL OR source_sha256 ~ '^[0-9a-f]{64}$'),
  known_gaps jsonb,
  baseline_source_pack_id uuid NOT NULL,
  baseline_source_pack_version integer NOT NULL CHECK (baseline_source_pack_version > 0),
  baseline_manifest_sha256 text NOT NULL CHECK (baseline_manifest_sha256 ~ '^[0-9a-f]{64}$'),
  baseline_raw_manifest_sha256 text NOT NULL CHECK (baseline_raw_manifest_sha256 ~ '^[0-9a-f]{64}$'),
  promoted_source_pack_version integer,
  promoted_source_entry_id uuid,
  promoted_evidence_id uuid,
  decision_request_sha256 text NOT NULL CHECK (decision_request_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id,id),
  UNIQUE (organization_id, candidate_id),
  FOREIGN KEY (organization_id,candidate_id) REFERENCES app.dra_research_candidates(organization_id,id),
  FOREIGN KEY (organization_id,case_id,case_revision) REFERENCES app.student_case_revisions(organization_id,case_id,revision),
  FOREIGN KEY (organization_id,actor_id) REFERENCES app.actors(organization_id,id),
  FOREIGN KEY (organization_id,baseline_source_pack_id,baseline_source_pack_version) REFERENCES app.source_packs(organization_id,id,version),
  FOREIGN KEY (organization_id,baseline_source_pack_id,promoted_source_pack_version,promoted_source_entry_id) REFERENCES app.source_pack_entries(organization_id,source_pack_id,source_pack_version,id),
  FOREIGN KEY (organization_id,promoted_evidence_id) REFERENCES app.evidence_refs(organization_id,id),
  CHECK (
    (decision = 'approve' AND source_url IS NOT NULL AND publisher IS NOT NULL AND institution IS NOT NULL
      AND snapshot_date IS NOT NULL AND freshness_days IS NOT NULL AND redistribution_class IS NOT NULL
      AND evidence_class IS NOT NULL AND declared_path IS NOT NULL AND source_byte_length IS NOT NULL
      AND source_sha256 IS NOT NULL AND known_gaps IS NOT NULL
      AND promoted_source_pack_version IS NOT NULL AND promoted_source_entry_id IS NOT NULL
      AND promoted_evidence_id IS NOT NULL)
    OR
    (decision = 'reject' AND source_url IS NULL AND publisher IS NULL AND institution IS NULL
      AND snapshot_date IS NULL AND freshness_days IS NULL AND redistribution_class IS NULL
      AND evidence_class IS NULL AND declared_path IS NULL AND source_byte_length IS NULL
      AND source_sha256 IS NULL AND known_gaps IS NULL
      AND promoted_source_pack_version IS NULL AND promoted_source_entry_id IS NULL
      AND promoted_evidence_id IS NULL)
  )
);
CREATE UNIQUE INDEX external_evidence_one_approved_claim_per_revision ON app.external_evidence_verifications(organization_id,case_id,case_revision,claim) WHERE decision='approve';

ALTER TABLE app.dra_research_candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.dra_research_candidates FORCE ROW LEVEL SECURITY;
CREATE POLICY dra_research_candidates_tenant_isolation ON app.dra_research_candidates USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid) WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);
ALTER TABLE app.external_evidence_verifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.external_evidence_verifications FORCE ROW LEVEL SECURITY;
CREATE POLICY external_evidence_verifications_tenant_isolation ON app.external_evidence_verifications USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid) WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);

CREATE FUNCTION app.reject_dra_authority_mutation() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='DRA candidate and verification rows are immutable';
END; $$;
CREATE TRIGGER dra_research_candidates_immutable BEFORE UPDATE OR DELETE ON app.dra_research_candidates FOR EACH ROW EXECUTE FUNCTION app.reject_dra_authority_mutation();
CREATE TRIGGER external_evidence_verifications_immutable BEFORE UPDATE OR DELETE ON app.external_evidence_verifications FOR EACH ROW EXECUTE FUNCTION app.reject_dra_authority_mutation();

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

CREATE FUNCTION app.verify_and_promote_dra_candidate(
  p_org uuid,p_actor uuid,p_case uuid,p_candidate uuid,p_revision integer,p_dra_evidence_id text,
  p_decision text,p_reason text,
  p_source_url text,p_publisher text,p_institution text,p_snapshot_date date,p_freshness_days integer,
  p_redistribution_class text,p_evidence_class text,p_declared_path text,p_source_byte_length integer,p_source_sha256 text,p_known_gaps jsonb,
  p_baseline_source_pack_id uuid,p_baseline_source_pack_version integer,p_baseline_manifest_sha256 text,p_baseline_raw_manifest_sha256 text,
  p_verification uuid,p_external_source_entry uuid,p_external_evidence uuid,p_copied_evidence_ids jsonb,
  p_request_sha256 text,p_key_sha256 text
) RETURNS TABLE(verification_id uuid,terminal_decision text,promoted_source_pack_version integer,promoted_source_entry_id uuid,promoted_evidence_id uuid,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE prior app.idempotency_records%ROWTYPE; candidate app.dra_research_candidates%ROWTYPE; selected_evidence jsonb; next_version integer; existing app.external_evidence_verifications%ROWTYPE;
BEGIN
  PERFORM app.assert_m3b_context(p_org,p_actor,'advisor');
  PERFORM pg_advisory_xact_lock(hashtextextended(p_org::text||':'||p_case::text||':'||p_revision::text||':'||'australia_program_fit',0));
  SELECT * INTO prior FROM app.idempotency_records WHERE organization_id=p_org AND actor_id=p_actor AND operation='dra_candidate_verify' AND key_sha256=p_key_sha256;
  IF FOUND THEN
    IF prior.request_sha256<>p_request_sha256 THEN RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='idempotency request mismatch'; END IF;
    SELECT * INTO existing FROM app.external_evidence_verifications WHERE organization_id=p_org AND id=prior.response_id;
    RETURN QUERY SELECT existing.id,existing.decision,existing.promoted_source_pack_version,existing.promoted_source_entry_id,existing.promoted_evidence_id,true;
    RETURN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM app.student_case_participants WHERE organization_id=p_org AND case_id=p_case AND actor_id=p_actor AND role='advisor') THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='candidate unavailable'; END IF;
  SELECT * INTO candidate FROM app.dra_research_candidates WHERE organization_id=p_org AND id=p_candidate AND case_id=p_case AND case_revision=p_revision FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='candidate unavailable'; END IF;
  PERFORM 1 FROM app.student_cases WHERE organization_id=p_org AND id=p_case AND current_revision=p_revision AND state='planning' FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='candidate case is stale'; END IF;
  IF EXISTS (SELECT 1 FROM app.external_evidence_verifications WHERE organization_id=p_org AND candidate_id=p_candidate) THEN RAISE EXCEPTION USING ERRCODE='NV012', MESSAGE='candidate already terminal'; END IF;
  SELECT value INTO selected_evidence FROM jsonb_array_elements(candidate.ordered_evidence) item(value) WHERE value->>'evidence_id'=p_dra_evidence_id;
  IF selected_evidence IS NULL OR selected_evidence->>'citation_status'<>'cited' OR selected_evidence->>'source_url' IS NULL OR selected_evidence->>'source_identity' IS DISTINCT FROM selected_evidence->>'source_url' THEN RAISE EXCEPTION USING ERRCODE='NV011', MESSAGE='candidate evidence contract mismatch'; END IF;
  IF p_decision NOT IN ('approve','reject') OR NULLIF(btrim(p_reason),'') IS NULL OR length(p_reason)>2000 OR p_request_sha256 !~ '^[0-9a-f]{64}$' OR p_key_sha256 !~ '^[0-9a-f]{64}$' OR p_baseline_source_pack_id<>'50000000-0000-0000-0000-000000000001'::uuid OR p_baseline_source_pack_version<>1 OR p_baseline_manifest_sha256<>'84350ea5705d9681d3e6550e1bd06e3340a9fcf0e7e7bbed4478ed3403405f28' OR p_baseline_raw_manifest_sha256<>'5d455d2c409c322e093f3a116387f3cef0fb7ea0f7357fec5e76e9da5b3a2a25' THEN RAISE EXCEPTION USING ERRCODE='NV011', MESSAGE='verification contract mismatch'; END IF;
  IF p_decision='reject' THEN
    IF p_source_url IS NOT NULL OR p_source_sha256 IS NOT NULL OR p_external_source_entry IS NOT NULL OR p_external_evidence IS NOT NULL OR p_copied_evidence_ids IS NOT NULL THEN RAISE EXCEPTION USING ERRCODE='NV011', MESSAGE='reject cannot attest or promote'; END IF;
    INSERT INTO app.external_evidence_verifications(organization_id,id,candidate_id,case_id,case_revision,actor_id,dra_evidence_id,decision,reason,baseline_source_pack_id,baseline_source_pack_version,baseline_manifest_sha256,baseline_raw_manifest_sha256,decision_request_sha256) VALUES(p_org,p_verification,p_candidate,p_case,p_revision,p_actor,p_dra_evidence_id,'reject',p_reason,p_baseline_source_pack_id,p_baseline_source_pack_version,p_baseline_manifest_sha256,p_baseline_raw_manifest_sha256,p_request_sha256);
    INSERT INTO app.idempotency_records VALUES(p_org,p_actor,'dra_candidate_verify',p_key_sha256,p_request_sha256,'dra_verification',p_verification,clock_timestamp());
    RETURN QUERY SELECT p_verification,'reject'::text,NULL::integer,NULL::uuid,NULL::uuid,false;
    RETURN;
  END IF;
  IF p_source_url IS DISTINCT FROM selected_evidence->>'source_url' OR p_source_url !~ '^https://' OR NULLIF(btrim(p_publisher),'') IS NULL OR NULLIF(btrim(p_institution),'') IS NULL OR p_snapshot_date IS NULL OR p_freshness_days<=0 OR p_redistribution_class<>'link_only' OR p_evidence_class NOT IN ('institutional','government') OR NULLIF(btrim(p_declared_path),'') IS NULL OR p_declared_path ~ '(^|/)\.\.(/|$)' OR p_declared_path ~ '^/' OR p_source_byte_length<=0 OR p_source_sha256 !~ '^[0-9a-f]{64}$' OR jsonb_typeof(p_known_gaps)<>'array' OR NOT (p_known_gaps ? 'applicant_eligibility') OR NOT (p_known_gaps ? 'intake_availability') OR p_external_source_entry IS NULL OR p_external_evidence IS NULL OR jsonb_typeof(p_copied_evidence_ids)<>'array' THEN RAISE EXCEPTION USING ERRCODE='NV011', MESSAGE='source attestation contract mismatch'; END IF;
  PERFORM 1 FROM app.source_packs WHERE organization_id=p_org AND id=p_baseline_source_pack_id AND version=p_baseline_source_pack_version AND manifest_sha256=p_baseline_manifest_sha256 FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV011', MESSAGE='baseline source pack mismatch'; END IF;
  IF jsonb_array_length(p_copied_evidence_ids)<>5 OR (SELECT count(DISTINCT value->>'claim') FROM jsonb_array_elements(p_copied_evidence_ids) item(value))<>5 OR (SELECT count(DISTINCT value->>'evidence_id') FROM jsonb_array_elements(p_copied_evidence_ids) item(value) WHERE (value->>'evidence_id') ~ '^[0-9a-f-]{36}$')<>5 OR EXISTS (SELECT 1 FROM jsonb_array_elements(p_copied_evidence_ids) item(value) WHERE value->>'claim' NOT IN ('australia_tuition','australia_living_cost','australia_fx','japan_program_fit','australia_ranking')) THEN RAISE EXCEPTION USING ERRCODE='NV011', MESSAGE='baseline evidence identity mismatch'; END IF;
  SELECT COALESCE(max(version),0)+1 INTO next_version FROM app.source_packs WHERE organization_id=p_org AND id=p_baseline_source_pack_id;
  INSERT INTO app.source_packs(organization_id,id,version,schema_version,manifest_sha256) VALUES(p_org,p_baseline_source_pack_id,next_version,1,encode(sha256(convert_to(p_baseline_manifest_sha256||':'||p_source_sha256||':'||next_version::text,'UTF8')),'hex'));
  INSERT INTO app.source_pack_entries(organization_id,source_pack_id,source_pack_version,id,declared_path,sha256,snapshot_date,publisher,institution,canonical_url,freshness_days,redistribution_class,evidence_class,coverage,known_gaps) SELECT organization_id,source_pack_id,next_version,id,declared_path,sha256,snapshot_date,publisher,institution,canonical_url,freshness_days,redistribution_class,evidence_class,coverage-'australia_program_fit',known_gaps FROM app.source_pack_entries WHERE organization_id=p_org AND source_pack_id=p_baseline_source_pack_id AND source_pack_version=p_baseline_source_pack_version;
  INSERT INTO app.evidence_refs(organization_id,id,source_pack_id,source_pack_version,source_entry_id,claim,authority,source_sha256) SELECT p_org,(item->>'evidence_id')::uuid,p_baseline_source_pack_id,next_version,e.source_entry_id,e.claim,'accepted_synthetic_demo',e.source_sha256 FROM jsonb_array_elements(p_copied_evidence_ids) item JOIN app.evidence_refs e ON e.organization_id=p_org AND e.source_pack_id=p_baseline_source_pack_id AND e.source_pack_version=p_baseline_source_pack_version AND e.claim=item->>'claim' WHERE e.claim<>'australia_program_fit';
  INSERT INTO app.source_pack_entries(organization_id,source_pack_id,source_pack_version,id,declared_path,sha256,snapshot_date,publisher,institution,canonical_url,freshness_days,redistribution_class,evidence_class,coverage,known_gaps) VALUES(p_org,p_baseline_source_pack_id,next_version,p_external_source_entry,p_declared_path,p_source_sha256,p_snapshot_date,p_publisher,p_institution,p_source_url,p_freshness_days,'link_only',p_evidence_class,'["australia_program_fit"]'::jsonb,p_known_gaps);
  INSERT INTO app.evidence_refs(organization_id,id,source_pack_id,source_pack_version,source_entry_id,claim,authority,source_sha256) VALUES(p_org,p_external_evidence,p_baseline_source_pack_id,next_version,p_external_source_entry,'australia_program_fit','externally_verified',p_source_sha256);
  INSERT INTO app.external_evidence_verifications(organization_id,id,candidate_id,case_id,case_revision,actor_id,dra_evidence_id,decision,reason,source_url,publisher,institution,snapshot_date,freshness_days,redistribution_class,evidence_class,declared_path,source_byte_length,source_sha256,known_gaps,baseline_source_pack_id,baseline_source_pack_version,baseline_manifest_sha256,baseline_raw_manifest_sha256,promoted_source_pack_version,promoted_source_entry_id,promoted_evidence_id,decision_request_sha256) VALUES(p_org,p_verification,p_candidate,p_case,p_revision,p_actor,p_dra_evidence_id,'approve',p_reason,p_source_url,p_publisher,p_institution,p_snapshot_date,p_freshness_days,p_redistribution_class,p_evidence_class,p_declared_path,p_source_byte_length,p_source_sha256,p_known_gaps,p_baseline_source_pack_id,p_baseline_source_pack_version,p_baseline_manifest_sha256,p_baseline_raw_manifest_sha256,next_version,p_external_source_entry,p_external_evidence,p_request_sha256);
  INSERT INTO app.idempotency_records VALUES(p_org,p_actor,'dra_candidate_verify',p_key_sha256,p_request_sha256,'dra_verification',p_verification,clock_timestamp());
  RETURN QUERY SELECT p_verification,'approve'::text,next_version,p_external_source_entry,p_external_evidence,false;
EXCEPTION WHEN unique_violation THEN
  RAISE EXCEPTION USING ERRCODE='NV012', MESSAGE='concurrent or already-terminal promotion conflict';
END; $$;

REVOKE ALL ON TABLE app.dra_research_candidates FROM PUBLIC;
REVOKE ALL ON TABLE app.external_evidence_verifications FROM PUBLIC;
REVOKE ALL ON FUNCTION app.reject_dra_authority_mutation() FROM PUBLIC;
REVOKE ALL ON FUNCTION app.import_dra_research_candidate(uuid,uuid,uuid,uuid,integer,text,text,text,text,text,text,text,text,text,text,integer,text,jsonb,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.verify_and_promote_dra_candidate(uuid,uuid,uuid,uuid,integer,text,text,text,text,text,text,date,integer,text,text,text,integer,text,jsonb,uuid,integer,text,text,uuid,uuid,uuid,jsonb,text,text) FROM PUBLIC;
GRANT SELECT ON app.dra_research_candidates,app.external_evidence_verifications TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.import_dra_research_candidate(uuid,uuid,uuid,uuid,integer,text,text,text,text,text,text,text,text,text,text,integer,text,jsonb,text,text) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.verify_and_promote_dra_candidate(uuid,uuid,uuid,uuid,integer,text,text,text,text,text,text,date,integer,text,text,text,integer,text,jsonb,uuid,integer,text,text,uuid,uuid,uuid,jsonb,text,text) TO night_voyager_api;
"""


def upgrade() -> None:
    for statement in _split_statements(UPGRADE_SQL):
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP FUNCTION app.verify_and_promote_dra_candidate(uuid,uuid,uuid,uuid,integer,text,text,text,text,text,text,date,integer,text,text,text,integer,text,jsonb,uuid,integer,text,text,uuid,uuid,uuid,jsonb,text,text)")
    op.execute("DROP FUNCTION app.import_dra_research_candidate(uuid,uuid,uuid,uuid,integer,text,text,text,text,text,text,text,text,text,text,integer,text,jsonb,text,text)")
    op.execute("ALTER TABLE app.external_evidence_verifications NO FORCE ROW LEVEL SECURITY")
    op.execute("CREATE TEMP TABLE dra_promoted_packs ON COMMIT DROP AS SELECT organization_id,baseline_source_pack_id AS source_pack_id,promoted_source_pack_version AS source_pack_version FROM app.external_evidence_verifications WHERE promoted_source_pack_version IS NOT NULL")
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE app.{table}")
    op.execute("ALTER TABLE app.evidence_refs NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE app.source_pack_entries NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE app.source_packs NO FORCE ROW LEVEL SECURITY")
    op.execute("DELETE FROM app.evidence_refs e USING dra_promoted_packs p WHERE e.organization_id=p.organization_id AND e.source_pack_id=p.source_pack_id AND e.source_pack_version=p.source_pack_version")
    op.execute("DELETE FROM app.source_pack_entries e USING dra_promoted_packs p WHERE e.organization_id=p.organization_id AND e.source_pack_id=p.source_pack_id AND e.source_pack_version=p.source_pack_version")
    op.execute("DELETE FROM app.source_packs s USING dra_promoted_packs p WHERE s.organization_id=p.organization_id AND s.id=p.source_pack_id AND s.version=p.source_pack_version")
    op.execute("ALTER TABLE app.evidence_refs FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE app.source_pack_entries FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE app.source_packs FORCE ROW LEVEL SECURITY")
    op.execute("DROP FUNCTION app.reject_dra_authority_mutation()")
    op.execute("ALTER TABLE app.evidence_refs DROP CONSTRAINT evidence_refs_authority_check")
    op.execute("ALTER TABLE app.evidence_refs ADD CONSTRAINT evidence_refs_authority_check CHECK (authority IN ('untrusted_candidate','accepted_synthetic_demo'))")


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
