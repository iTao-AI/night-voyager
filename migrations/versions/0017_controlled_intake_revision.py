# ruff: noqa: E501
"""Add controlled intake revision and exact independent synthetic source authority."""

from __future__ import annotations

from importlib import import_module

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None
_BASE = import_module("migrations.versions.0012_versioned_planning_revision")
_RECOVERY = import_module("migrations.versions.0016_guarded_terminal_task_recovery")

SOURCE_SQL = r"""
CREATE FUNCTION app.assert_controlled_intake_source(p_org uuid,p_pack uuid,p_version integer,p_intake text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  PERFORM app.assert_context(p_org);
  IF p_pack IS DISTINCT FROM '50000000-0000-0000-0000-000000000017'::uuid
     OR p_version IS DISTINCT FROM 1 OR p_intake IS DISTINCT FROM '2028-02'
     OR NOT EXISTS(SELECT 1 FROM app.source_packs WHERE organization_id=p_org AND id=p_pack AND version=p_version AND schema_version=1 AND manifest_sha256='832aab1715564dee0e3a4530a181ccd4581bb7e5199144cb34dc55b20077add1')
     OR (SELECT COALESCE(jsonb_agg(jsonb_build_object(
       'entry_id',id,'path',declared_path,'sha256',sha256,'snapshot_date',snapshot_date,
       'publisher',publisher,'institution',institution,'canonical_url',canonical_url,
       'freshness_days',freshness_days,'redistribution_class',redistribution_class,
       'evidence_class',evidence_class,'coverage',coverage,'known_gaps',known_gaps) ORDER BY id),'[]'::jsonb)
       FROM app.source_pack_entries WHERE organization_id=p_org AND source_pack_id=p_pack AND source_pack_version=p_version) IS DISTINCT FROM '[
  {
    "entry_id": "51000000-0000-0000-0000-000000001701",
    "path": "sources/australia.txt",
    "sha256": "b2ce10322347c2e68b0e342f9cc25f48fd844e72580238caef1c3b998921b647",
    "snapshot_date": "2026-07-01",
    "publisher": "Synthetic Demo Publisher",
    "institution": "Synthetic Australia Institution",
    "canonical_url": "https://example.invalid/intake-delay-v1/australia",
    "freshness_days": 365,
    "redistribution_class": "synthetic_public",
    "evidence_class": "synthetic_demo",
    "coverage": [
      "australia_program_fit",
      "australia_tuition",
      "australia_living_cost",
      "australia_fx",
      "australia_ranking"
    ],
    "known_gaps": []
  },
  {
    "entry_id": "51000000-0000-0000-0000-000000001702",
    "path": "sources/japan.txt",
    "sha256": "72c030094a536ec85421c5121a4b51998f7711cda6f5aac402a04b3bf0377c60",
    "snapshot_date": "2026-07-01",
    "publisher": "Synthetic Demo Publisher",
    "institution": "Synthetic Japan Institution",
    "canonical_url": "https://example.invalid/intake-delay-v1/japan",
    "freshness_days": 365,
    "redistribution_class": "synthetic_public",
    "evidence_class": "synthetic_demo",
    "coverage": [
      "japan_program_fit"
    ],
    "known_gaps": [
      "high_risk_alternative"
    ]
  },
  {
    "entry_id": "51000000-0000-0000-0000-000000001703",
    "path": "sources/malaysia.txt",
    "sha256": "e0bdb667e402c8a034c608f574ab1747866c22fe89f3ed32f766a6d20287ac6b",
    "snapshot_date": "2026-07-01",
    "publisher": "Synthetic Demo Publisher",
    "institution": "Synthetic Malaysia Institution",
    "canonical_url": "https://example.invalid/intake-delay-v1/malaysia",
    "freshness_days": 365,
    "redistribution_class": "synthetic_public",
    "evidence_class": "synthetic_demo",
    "coverage": [
      "malaysia_context"
    ],
    "known_gaps": [
      "direct_program_fit"
    ]
  }
]'::jsonb
     OR (SELECT COALESCE(jsonb_agg(jsonb_build_object(
       'evidence_id',id,'claim',claim,'source_pack_id',source_pack_id,'source_pack_version',source_pack_version,
       'source_entry_id',source_entry_id,'source_sha256',source_sha256,'authority',authority) ORDER BY id),'[]'::jsonb)
       FROM app.evidence_refs WHERE organization_id=p_org AND source_pack_id=p_pack AND source_pack_version=p_version) IS DISTINCT FROM '[
  {
    "evidence_id": "60000000-0000-0000-0000-000000001701",
    "claim": "australia_program_fit",
    "source_pack_id": "50000000-0000-0000-0000-000000000017",
    "source_pack_version": 1,
    "source_entry_id": "51000000-0000-0000-0000-000000001701",
    "source_sha256": "b2ce10322347c2e68b0e342f9cc25f48fd844e72580238caef1c3b998921b647",
    "authority": "accepted_synthetic_demo"
  },
  {
    "evidence_id": "60000000-0000-0000-0000-000000001702",
    "claim": "australia_tuition",
    "source_pack_id": "50000000-0000-0000-0000-000000000017",
    "source_pack_version": 1,
    "source_entry_id": "51000000-0000-0000-0000-000000001701",
    "source_sha256": "b2ce10322347c2e68b0e342f9cc25f48fd844e72580238caef1c3b998921b647",
    "authority": "accepted_synthetic_demo"
  },
  {
    "evidence_id": "60000000-0000-0000-0000-000000001703",
    "claim": "australia_living_cost",
    "source_pack_id": "50000000-0000-0000-0000-000000000017",
    "source_pack_version": 1,
    "source_entry_id": "51000000-0000-0000-0000-000000001701",
    "source_sha256": "b2ce10322347c2e68b0e342f9cc25f48fd844e72580238caef1c3b998921b647",
    "authority": "accepted_synthetic_demo"
  },
  {
    "evidence_id": "60000000-0000-0000-0000-000000001704",
    "claim": "australia_fx",
    "source_pack_id": "50000000-0000-0000-0000-000000000017",
    "source_pack_version": 1,
    "source_entry_id": "51000000-0000-0000-0000-000000001701",
    "source_sha256": "b2ce10322347c2e68b0e342f9cc25f48fd844e72580238caef1c3b998921b647",
    "authority": "accepted_synthetic_demo"
  },
  {
    "evidence_id": "60000000-0000-0000-0000-000000001705",
    "claim": "japan_program_fit",
    "source_pack_id": "50000000-0000-0000-0000-000000000017",
    "source_pack_version": 1,
    "source_entry_id": "51000000-0000-0000-0000-000000001702",
    "source_sha256": "72c030094a536ec85421c5121a4b51998f7711cda6f5aac402a04b3bf0377c60",
    "authority": "accepted_synthetic_demo"
  },
  {
    "evidence_id": "60000000-0000-0000-0000-000000001706",
    "claim": "australia_ranking",
    "source_pack_id": "50000000-0000-0000-0000-000000000017",
    "source_pack_version": 1,
    "source_entry_id": "51000000-0000-0000-0000-000000001701",
    "source_sha256": "b2ce10322347c2e68b0e342f9cc25f48fd844e72580238caef1c3b998921b647",
    "authority": "accepted_synthetic_demo"
  }
]'::jsonb
  THEN RAISE EXCEPTION USING ERRCODE='NV027', MESSAGE='intake evidence unavailable'; END IF;
END; $$;
"""

VALIDATE_SQL = r"""
CREATE OR REPLACE FUNCTION app.validate_collaboration_fact(p_role text,p_fact_key text,p_value jsonb) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
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
    IF value_text !~ '^[0-9]{4}-(0[1-9]|1[0-2])$' OR left(value_text,4)='0000' THEN
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

CONFIRM_SQL = r"""
CREATE OR REPLACE FUNCTION app.verify_memory_candidate(p_org uuid,p_actor uuid,p_candidate uuid,p_expected_revision integer,p_decision text,p_reason text,p_verification uuid,p_fact uuid,p_request_sha256 text,p_key_sha256 text) RETURNS TABLE(verification_id uuid,candidate_id uuid,decision text,result_fact_id uuid,result_revision integer,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE prior app.idempotency_records%ROWTYPE; selected_case app.student_cases%ROWTYPE; candidate app.memory_candidates%ROWTYPE; existing app.memory_candidate_verifications%ROWTYPE; prior_fact app.confirmed_facts%ROWTYPE; current_run app.planning_runs%ROWTYPE; request_review app.advisor_reviews%ROWTYPE; current_revision app.student_case_revisions%ROWTYPE; resolved_case uuid; current_run_count integer; next_revision integer; next_fact_version integer; next_student jsonb; next_family jsonb;
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

  SELECT * INTO request_review FROM app.advisor_reviews review_row
   WHERE review_row.organization_id=p_org AND review_row.case_id=resolved_case
     AND review_row.case_revision=p_expected_revision
     AND review_row.planning_run_id=current_run.id
     AND review_row.action='request_revision' FOR SHARE;
  IF EXISTS (
    SELECT 1 FROM app.agent_tasks task
     WHERE task.organization_id=p_org AND task.case_id=resolved_case
       AND task.state IN ('queued','leased','running','waiting_review')
       AND NOT (
         task.state='waiting_review'
         AND (
           (task.case_revision=p_expected_revision
            AND task.result_planning_run_id=current_run.id
            AND request_review.id IS NOT NULL)
           OR (task.case_revision<p_expected_revision AND EXISTS (
             SELECT 1 FROM app.planning_runs retired
             JOIN app.student_case_revisions successor
               ON successor.organization_id=retired.organization_id
              AND successor.case_id=retired.case_id
              AND successor.revision=retired.case_revision+1
              AND successor.superseded_planning_run_id=retired.id
             JOIN app.advisor_reviews frozen_review
               ON frozen_review.organization_id=successor.organization_id
              AND frozen_review.id=successor.revision_requested_by_review_id
              AND frozen_review.case_id=retired.case_id
              AND frozen_review.case_revision=retired.case_revision
              AND frozen_review.planning_run_id=retired.id
              AND frozen_review.action='request_revision'
             WHERE retired.organization_id=task.organization_id
               AND retired.id=task.result_planning_run_id
               AND retired.case_id=task.case_id
               AND retired.case_revision=task.case_revision
               AND retired.state='review_required' AND NOT retired.is_current
               AND successor.revision<=p_expected_revision
           ))
         )
       )
  ) THEN
    RAISE EXCEPTION USING ERRCODE='NV014', MESSAGE='active task blocks revision publication';
  END IF;
  IF selected_case.state='planning' AND current_run.id IS NULL THEN
    RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='current planning run is unavailable';
  END IF;
  IF current_run.id IS NOT NULL THEN
    SELECT * INTO request_review FROM app.advisor_reviews review_row
     WHERE review_row.organization_id=p_org AND review_row.case_id=resolved_case
       AND review_row.case_revision=p_expected_revision
       AND review_row.planning_run_id=current_run.id
       AND review_row.action='request_revision' FOR SHARE;
    IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='request revision authority is unavailable'; END IF;
    IF candidate.fact_key NOT IN ('student.preferred_countries','family.budget','student.intake') THEN
      RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='unsupported planning revision fact';
    END IF;
    IF EXISTS (SELECT 1 FROM app.family_decisions decision_row WHERE decision_row.organization_id=p_org AND decision_row.case_id=resolved_case)
       OR EXISTS (SELECT 1 FROM app.timeline_plans timeline_row JOIN app.family_decisions decision_row ON decision_row.organization_id=timeline_row.organization_id AND decision_row.id=timeline_row.family_decision_id WHERE decision_row.organization_id=p_org AND decision_row.case_id=resolved_case) THEN
      RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='finalized Case cannot be revised';
    END IF;
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

  IF current_run.id IS NOT NULL AND candidate.fact_key='student.intake' THEN
    IF candidate.proposed_value IS NOT DISTINCT FROM current_revision.student_preferences->'intake' THEN
      RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='unchanged intake fact';
    END IF;
    IF current_revision.student_preferences->>'intake' IS DISTINCT FROM '2027-02'
       OR candidate.proposed_value IS DISTINCT FROM '"2028-02"'::jsonb
       OR current_run.source_pack_id IS DISTINCT FROM '50000000-0000-0000-0000-000000000001'::uuid
       OR current_run.source_pack_version IS DISTINCT FROM 1 OR current_run.policy_version IS DISTINCT FROM 'm3a-policy-v1' THEN
      RAISE EXCEPTION USING ERRCODE='NV027', MESSAGE='intake evidence unavailable';
    END IF;
    PERFORM app.assert_controlled_intake_source(p_org,'50000000-0000-0000-0000-000000000017',1,'2028-02');
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
    organization_id,case_id,revision,schema_version,student_preferences,family_preferences,
    revision_requested_by_review_id,superseded_planning_run_id
  ) VALUES(p_org,resolved_case,next_revision,1,next_student,next_family,request_review.id,current_run.id);
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

PENDING_SQL = r"""

CREATE OR REPLACE FUNCTION app.read_connected_journey_fact_pending(
  p_org uuid,
  p_actor uuid,
  p_role text,
  p_case uuid
) RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
  selected_case app.student_cases%ROWTYPE;
  pending boolean;
BEGIN
  IF p_org IS NULL OR p_actor IS NULL OR p_role IS NULL OR p_case IS NULL
     OR p_role NOT IN ('advisor','student','parent') THEN
    RAISE EXCEPTION USING ERRCODE='NV006',
      MESSAGE='invalid connected journey fact projection';
  END IF;
  PERFORM app.assert_collaboration_context(p_org,p_actor,p_role);
  SELECT * INTO selected_case
    FROM app.student_cases selected_case_row
   WHERE selected_case_row.organization_id=p_org
     AND selected_case_row.id=p_case;
  IF NOT FOUND OR NOT EXISTS (
    SELECT 1
      FROM app.student_case_participants participant
     WHERE participant.organization_id=p_org
       AND participant.case_id=p_case
       AND participant.actor_id=p_actor
       AND participant.role=p_role
  ) THEN
    RAISE EXCEPTION USING ERRCODE='NV007',
      MESSAGE='collaboration resource unavailable';
  END IF;
  SELECT EXISTS(
    SELECT 1
      FROM app.memory_candidates candidate
     WHERE candidate.organization_id=p_org
       AND candidate.case_id=p_case
       AND candidate.case_revision=selected_case.current_revision
       AND candidate.fact_key IN ('student.preferred_countries','family.budget','student.intake')
       AND candidate.expires_at>clock_timestamp()
       AND NOT EXISTS(
         SELECT 1
           FROM app.memory_candidate_verifications verification
          WHERE verification.organization_id=candidate.organization_id
            AND verification.candidate_id=candidate.id
       )
  ) INTO pending;
  RETURN pending;
END; $$;

"""

CREATE_SQL = r"""
CREATE OR REPLACE FUNCTION app.create_agent_task(p_org uuid,p_actor uuid,p_case uuid,p_task uuid,p_operation text,p_revision integer,p_pack uuid,p_pack_version integer,p_policy text,p_skill_manifest jsonb,p_request_hash text,p_key_hash text) RETURNS TABLE(task_id uuid,row_version integer,state text,attempt_count integer,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE prior app.idempotency_records%ROWTYPE; selected app.agent_tasks%ROWTYPE; current_case app.student_cases%ROWTYPE; current_revision app.student_case_revisions%ROWTYPE; definition app.skill_definitions%ROWTYPE; activation app.skill_activation_events%ROWTYPE; version app.skill_versions%ROWTYPE; starts_planning boolean := false; expected_pack uuid; expected_version integer; expected_policy text; previous_intake text;
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
     OR (p_pack IS DISTINCT FROM '50000000-0000-0000-0000-000000000017'::uuid AND NOT EXISTS (
       SELECT 1 FROM app.source_packs s
       WHERE s.organization_id=p_org AND s.id=p_pack AND s.version=p_pack_version
     )) THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='task input is stale'; END IF;
  SELECT * INTO current_revision FROM app.student_case_revisions revision_row
   WHERE revision_row.organization_id=p_org AND revision_row.case_id=p_case
     AND revision_row.revision=p_revision FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='task revision lineage is unavailable'; END IF;

  IF current_revision.superseded_planning_run_id IS NOT NULL THEN
    SELECT run.source_pack_id,run.source_pack_version,run.policy_version,old.student_preferences->>'intake'
      INTO expected_pack,expected_version,expected_policy,previous_intake
      FROM app.planning_runs run JOIN app.student_case_revisions old
        ON old.organization_id=run.organization_id AND old.case_id=run.case_id AND old.revision=run.case_revision
     WHERE run.organization_id=p_org AND run.id=current_revision.superseded_planning_run_id AND run.case_id=p_case;
    IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV027', MESSAGE='intake source lineage unavailable'; END IF;
    IF current_revision.student_preferences->>'intake' IS DISTINCT FROM previous_intake THEN
      IF previous_intake IS DISTINCT FROM '2027-02' OR current_revision.student_preferences->>'intake' IS DISTINCT FROM '2028-02'
         OR expected_pack IS DISTINCT FROM '50000000-0000-0000-0000-000000000001'::uuid OR expected_version IS DISTINCT FROM 1
         OR expected_policy IS DISTINCT FROM 'm3a-policy-v1' THEN
        RAISE EXCEPTION USING ERRCODE='NV027', MESSAGE='intake evidence unavailable';
      END IF;
      expected_pack := '50000000-0000-0000-0000-000000000017'::uuid; expected_version := 1;
    END IF;
    IF p_pack IS DISTINCT FROM expected_pack OR p_pack_version IS DISTINCT FROM expected_version OR p_policy IS DISTINCT FROM expected_policy THEN
      RAISE EXCEPTION USING ERRCODE='NV027', MESSAGE='revision source pin mismatch';
    END IF;
  ELSIF p_pack='50000000-0000-0000-0000-000000000017'::uuid THEN
    RAISE EXCEPTION USING ERRCODE='NV027', MESSAGE='intake source lineage unavailable';
  END IF;
  IF p_pack='50000000-0000-0000-0000-000000000017'::uuid THEN
    PERFORM app.assert_controlled_intake_source(p_org,p_pack,p_pack_version,current_revision.student_preferences->>'intake');
  END IF;
  IF p_pack='50000000-0000-0000-0000-000000000017'::uuid AND p_operation<>'generate_planning_run_v1' THEN RAISE EXCEPTION USING ERRCODE='NV027', MESSAGE='intake operation unavailable'; END IF;
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
  IF EXISTS (SELECT 1 FROM app.agent_tasks live_task WHERE live_task.organization_id=p_org AND live_task.case_id=p_case AND live_task.case_revision=p_revision AND live_task.state IN ('queued','leased','running','waiting_review')) THEN RAISE EXCEPTION USING ERRCODE='NV009', MESSAGE='live task already exists'; END IF;
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
    skill_version_id,skill_activation_event_id,skill_activation_sequence,runtime_binding_sha256,
    predecessor_planning_run_id
  ) VALUES(
    p_org,p_task,p_case,p_operation,p_revision,p_pack,p_pack_version,p_policy,p_request_hash,
    p_actor,'queued',definition.id,version.id,activation.id,activation.activation_sequence,
    version.runtime_binding_sha256,current_revision.superseded_planning_run_id
  );
  INSERT INTO internal.agent_task_dispatch(task_id,organization_id,available_at) VALUES(p_task,p_org,clock_timestamp());
  PERFORM app.append_agent_task_event(p_org,p_task,'queued','preparing','queued',0,NULL);
  INSERT INTO app.idempotency_records VALUES(p_org,p_actor,'agent_task_create',p_key_hash,p_request_hash,'agent_task',p_task,clock_timestamp());
  SELECT * INTO selected FROM app.agent_tasks WHERE organization_id=p_org AND id=p_task;
  RETURN QUERY SELECT selected.id,selected.row_version,selected.state,selected.attempt_count,false;
END; $$;
"""

SNAPSHOT_SQL = r"""
CREATE OR REPLACE FUNCTION app.load_persisted_synthetic_planning_snapshot(p_org uuid,p_case uuid,p_revision integer,p_pack uuid,p_pack_version integer,p_policy text) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE expected_pack uuid; expected_version integer; expected_policy text; previous_intake text; selected_case app.student_cases%ROWTYPE; selected_revision app.student_case_revisions%ROWTYPE; selected_pack app.source_packs%ROWTYPE; countries text[]; canonical_countries text[];
BEGIN
  PERFORM app.assert_context(p_org);
  IF p_revision<=0 OR p_pack_version<>1 OR p_pack NOT IN ('50000000-0000-0000-0000-000000000001'::uuid,'50000000-0000-0000-0000-000000000017'::uuid) OR p_policy<>'m3a-policy-v1' THEN
    RAISE EXCEPTION USING ERRCODE='NV011', MESSAGE='persisted synthetic snapshot pins are invalid';
  END IF;
  SELECT * INTO selected_case FROM app.student_cases c
   WHERE c.organization_id=p_org AND c.id=p_case FOR SHARE;
  IF NOT FOUND OR selected_case.current_revision<>p_revision OR selected_case.state<>'planning' THEN
    RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='persisted synthetic Case is stale';
  END IF;
  SELECT * INTO selected_revision FROM app.student_case_revisions r
   WHERE r.organization_id=p_org AND r.case_id=p_case AND r.revision=p_revision;
  IF NOT FOUND OR selected_revision.schema_version<>1
     OR jsonb_typeof(selected_revision.student_preferences)<>'object'
     OR jsonb_typeof(selected_revision.family_preferences)<>'object'
     OR jsonb_typeof(selected_revision.student_preferences->'preferred_countries')<>'array' THEN
    RAISE EXCEPTION USING ERRCODE='NV011', MESSAGE='persisted synthetic Case facts are malformed';
  END IF;
  SELECT array_agg(value ORDER BY ordinality),array_agg(DISTINCT value ORDER BY value)
    INTO countries,canonical_countries
    FROM jsonb_array_elements_text(selected_revision.student_preferences->'preferred_countries') WITH ORDINALITY AS item(value,ordinality);
  IF cardinality(countries) NOT BETWEEN 1 AND 3 OR countries IS DISTINCT FROM canonical_countries
     OR EXISTS (SELECT 1 FROM unnest(countries) value WHERE value NOT IN ('australia','japan','malaysia')) THEN
    RAISE EXCEPTION USING ERRCODE='NV011', MESSAGE='persisted synthetic country scope is invalid';
  END IF;
  SELECT * INTO selected_pack FROM app.source_packs s
   WHERE s.organization_id=p_org AND s.id=p_pack AND s.version=p_pack_version;
  IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV011', MESSAGE='persisted synthetic source pack is unavailable'; END IF;

  IF selected_revision.superseded_planning_run_id IS NOT NULL THEN
    SELECT run.source_pack_id,run.source_pack_version,run.policy_version,old.student_preferences->>'intake'
      INTO expected_pack,expected_version,expected_policy,previous_intake
      FROM app.planning_runs run JOIN app.student_case_revisions old
        ON old.organization_id=run.organization_id AND old.case_id=run.case_id AND old.revision=run.case_revision
     WHERE run.organization_id=p_org AND run.id=selected_revision.superseded_planning_run_id AND run.case_id=p_case;
    IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV027', MESSAGE='intake source lineage unavailable'; END IF;
    IF selected_revision.student_preferences->>'intake' IS DISTINCT FROM previous_intake THEN
      IF previous_intake IS DISTINCT FROM '2027-02' OR selected_revision.student_preferences->>'intake' IS DISTINCT FROM '2028-02'
         OR expected_pack IS DISTINCT FROM '50000000-0000-0000-0000-000000000001'::uuid OR expected_version IS DISTINCT FROM 1
         OR expected_policy IS DISTINCT FROM 'm3a-policy-v1' THEN
        RAISE EXCEPTION USING ERRCODE='NV027', MESSAGE='intake evidence unavailable';
      END IF;
      expected_pack := '50000000-0000-0000-0000-000000000017'::uuid; expected_version := 1;
    END IF;
    IF p_pack IS DISTINCT FROM expected_pack OR p_pack_version IS DISTINCT FROM expected_version OR p_policy IS DISTINCT FROM expected_policy THEN
      RAISE EXCEPTION USING ERRCODE='NV027', MESSAGE='revision source pin mismatch';
    END IF;
  ELSIF p_pack='50000000-0000-0000-0000-000000000017'::uuid THEN
    RAISE EXCEPTION USING ERRCODE='NV027', MESSAGE='intake source lineage unavailable';
  END IF;
  IF p_pack='50000000-0000-0000-0000-000000000017'::uuid THEN
    PERFORM app.assert_controlled_intake_source(p_org,p_pack,p_pack_version,selected_revision.student_preferences->>'intake');
  END IF;
  RETURN jsonb_build_object(
    'schema_version',1,'organization_id',p_org,
    'case',jsonb_build_object(
      'schema_version',selected_revision.schema_version,'organization_id',p_org,
      'case_id',p_case,'revision',p_revision,
      'student',selected_revision.student_preferences,'family',selected_revision.family_preferences
    ),
    'source_pack_id',p_pack,'source_pack_version',p_pack_version,'policy_version',p_policy
  );
END; $$;
"""

SEED_SQL = r"""

CREATE FUNCTION app.seed_demo_intake_revision(
  p_org uuid,
  p_case uuid,
  p_thread uuid,
  p_advisor uuid,
  p_student uuid,
  p_message uuid,
  p_candidate uuid,
  p_verification uuid,
  p_fact uuid,
  p_intake jsonb,
  p_value_sha256 text,
  p_message_request_sha256 text,
  p_candidate_request_sha256 text,
  p_verification_request_sha256 text
) RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
  has_any boolean;
  exact_chain boolean;
BEGIN
  PERFORM app.assert_context(p_org);

  IF p_org IS DISTINCT FROM '10000000-0000-0000-0000-000000000001'::uuid
     OR p_advisor IS DISTINCT FROM '20000000-0000-0000-0000-000000000001'::uuid
     OR p_student IS DISTINCT FROM '20000000-0000-0000-0000-000000000002'::uuid
     OR p_intake IS DISTINCT FROM
        '"2027-02"'::jsonb
     OR p_value_sha256 IS DISTINCT FROM
        '44e97a6e214dc13821aadcb2a4178e6bead3b4fe629adb04fb9d9c8302efd91b'
  THEN
    RAISE EXCEPTION USING
      ERRCODE='NV003',
      MESSAGE='planning revision demo seed mismatch';
  END IF;

  IF p_case='49000000-0000-0000-0000-000000000003'::uuid THEN
    IF p_thread IS DISTINCT FROM '4b000000-0000-0000-0000-000000000003'::uuid
       OR p_message IS DISTINCT FROM '4c000000-0000-0000-0000-000000000003'::uuid
       OR p_candidate IS DISTINCT FROM '4d000000-0000-0000-0000-000000000003'::uuid
       OR p_verification IS DISTINCT FROM '4e000000-0000-0000-0000-000000000003'::uuid
       OR p_fact IS DISTINCT FROM '4f000000-0000-0000-0000-000000000003'::uuid
       OR p_message_request_sha256 IS DISTINCT FROM
          'eb2a3521f94fb2807bf16bb3b9c94d5448921a8ea4f05a2343a9d57f717cff75'
       OR p_candidate_request_sha256 IS DISTINCT FROM
          '8aff35fd35c7d41cd7a880c2ac578d2e7d84211244778c48b601f3dee3312ec0'
       OR p_verification_request_sha256 IS DISTINCT FROM
          '5faec16f35e9afaf42ab7dade680b6ca19659c65bd93ca5d30f592b3767be0d0'
    THEN
      RAISE EXCEPTION USING
        ERRCODE='NV003',
        MESSAGE='planning revision demo seed mismatch';
    END IF;
  ELSE
    RAISE EXCEPTION USING
      ERRCODE='NV003',
      MESSAGE='planning revision demo seed mismatch';
  END IF;

  IF NOT EXISTS (
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
  ) OR NOT EXISTS (
    SELECT 1
      FROM app.collaboration_threads thread_row
     WHERE thread_row.organization_id=p_org
       AND thread_row.case_id=p_case
       AND thread_row.id=p_thread
       AND thread_row.created_by_actor_id=p_advisor
       AND thread_row.created_by_role='advisor'
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
       AND participant.actor_id=p_student
       AND participant.role='student'
  ) THEN
    RAISE EXCEPTION USING
      ERRCODE='NV003',
      MESSAGE='planning revision demo seed mismatch';
  END IF;

  SELECT
    EXISTS(
      SELECT 1 FROM app.message_events
       WHERE organization_id=p_org
         AND (id=p_message OR case_id=p_case)
    ) OR EXISTS(
      SELECT 1 FROM app.memory_candidates
       WHERE organization_id=p_org
         AND (id=p_candidate OR case_id=p_case)
    ) OR EXISTS(
      SELECT 1 FROM app.memory_candidate_verifications
       WHERE organization_id=p_org
         AND (id=p_verification OR case_id=p_case)
    ) OR EXISTS(
      SELECT 1 FROM app.confirmed_facts
       WHERE organization_id=p_org
         AND (id=p_fact OR case_id=p_case)
    ) OR EXISTS(
      SELECT 1 FROM app.case_revision_confirmed_fact_refs
       WHERE organization_id=p_org
         AND case_id=p_case
         AND case_revision=1
         AND fact_key='student.intake'
    )
  INTO has_any;

  IF has_any THEN
    SELECT
      (SELECT count(*)=1 AND count(*) FILTER (
         WHERE id=p_message
           AND thread_id=p_thread
           AND sequence_no=1
           AND actor_id=p_student
           AND actor_role='student'
           AND body='Synthetic initial intake 2027-02.'
           AND content_sha256=
             'db4f04f35b6c23128023984f5d919bf3b219c098bcd94eb4fe27d948db32b7e3'
           AND request_sha256=p_message_request_sha256
           AND created_at=timestamptz '2026-01-01 00:00:01+00'
         )=1
         FROM app.message_events
        WHERE organization_id=p_org AND case_id=p_case)
      AND
      (SELECT count(*)=1 AND count(*) FILTER (
         WHERE id=p_candidate
           AND case_revision=1
           AND message_event_id=p_message
           AND subject_actor_id=p_student
           AND subject_role='student'
           AND proposing_actor_id=p_student
           AND proposing_role='student'
           AND fact_key='student.intake'
           AND proposed_value=p_intake
           AND value_sha256=p_value_sha256
           AND request_sha256=p_candidate_request_sha256
           AND provenance_kind='participant_proposal'
           AND created_at=timestamptz '2026-01-01 00:00:02+00'
           AND expires_at=timestamptz '2026-01-08 00:00:02+00'
         )=1
         FROM app.memory_candidates
        WHERE organization_id=p_org AND case_id=p_case)
      AND
      (SELECT count(*)=1 AND count(*) FILTER (
         WHERE id=p_fact
           AND fact_key='student.intake'
           AND value=p_intake
           AND value_sha256=p_value_sha256
           AND source_candidate_id=p_candidate
           AND source_message_event_id=p_message
           AND subject_actor_id=p_student
           AND subject_role='student'
           AND confirming_advisor_actor_id=p_advisor
           AND confirming_advisor_role='advisor'
           AND supersedes_fact_id IS NULL
           AND fact_version=1
           AND confirmed_at=timestamptz '2026-01-01 00:00:03+00'
         )=1
         FROM app.confirmed_facts
        WHERE organization_id=p_org AND case_id=p_case)
      AND
      (SELECT count(*)=1 AND count(*) FILTER (
         WHERE id=p_verification
           AND candidate_id=p_candidate
           AND advisor_actor_id=p_advisor
           AND advisor_role='advisor'
           AND decision='confirm'
           AND reason='Synthetic initial fact seed.'
           AND request_sha256=p_verification_request_sha256
           AND result_fact_id=p_fact
           AND result_revision=1
           AND created_at=timestamptz '2026-01-01 00:00:03+00'
         )=1
         FROM app.memory_candidate_verifications
        WHERE organization_id=p_org AND case_id=p_case)
      AND
      (SELECT count(*)=1 AND count(*) FILTER (
         WHERE confirmed_fact_id=p_fact
           AND created_at=timestamptz '2026-01-01 00:00:03+00'
         )=1
         FROM app.case_revision_confirmed_fact_refs
        WHERE organization_id=p_org
          AND case_id=p_case
          AND case_revision=1
          AND fact_key='student.intake')
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
    p_org,p_message,p_thread,p_case,1,p_student,'student',
    'Synthetic initial intake 2027-02.',
    'db4f04f35b6c23128023984f5d919bf3b219c098bcd94eb4fe27d948db32b7e3',
    p_message_request_sha256,timestamptz '2026-01-01 00:00:01+00'
  );
  INSERT INTO app.memory_candidates(
    organization_id,id,case_id,case_revision,message_event_id,
    subject_actor_id,subject_role,proposing_actor_id,proposing_role,
    fact_key,proposed_value,value_sha256,request_sha256,created_at,expires_at
  ) VALUES(
    p_org,p_candidate,p_case,1,p_message,p_student,'student',p_student,'student',
    'student.intake',p_intake,p_value_sha256,
    p_candidate_request_sha256,timestamptz '2026-01-01 00:00:02+00',
    timestamptz '2026-01-08 00:00:02+00'
  );
  INSERT INTO app.confirmed_facts(
    organization_id,id,case_id,fact_key,value,value_sha256,
    source_candidate_id,source_message_event_id,subject_actor_id,subject_role,
    confirming_advisor_actor_id,confirming_advisor_role,supersedes_fact_id,
    fact_version,confirmed_at
  ) VALUES(
    p_org,p_fact,p_case,'student.intake',p_intake,
    p_value_sha256,p_candidate,p_message,p_student,'student',p_advisor,'advisor',
    NULL,1,timestamptz '2026-01-01 00:00:03+00'
  );
  INSERT INTO app.memory_candidate_verifications(
    organization_id,id,candidate_id,case_id,advisor_actor_id,advisor_role,
    decision,reason,request_sha256,result_fact_id,result_revision,created_at
  ) VALUES(
    p_org,p_verification,p_candidate,p_case,p_advisor,'advisor','confirm',
    'Synthetic initial fact seed.',p_verification_request_sha256,p_fact,1,
    timestamptz '2026-01-01 00:00:03+00'
  );
  INSERT INTO app.case_revision_confirmed_fact_refs(
    organization_id,case_id,case_revision,fact_key,confirmed_fact_id,created_at
  ) VALUES(
    p_org,p_case,1,'student.intake',p_fact,
    timestamptz '2026-01-01 00:00:03+00'
  );
END; $$;

"""


SOURCE_SIGNATURE = "app.assert_controlled_intake_source(uuid,uuid,integer,text)"
SEED_SIGNATURE = "app.seed_demo_intake_revision(uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,jsonb,text,text,text,text)"


def upgrade() -> None:
    for sql in (
        SOURCE_SQL,
        VALIDATE_SQL,
        CONFIRM_SQL,
        PENDING_SQL,
        CREATE_SQL,
        SNAPSHOT_SQL,
        SEED_SQL,
    ):
        op.execute(sql)
    for signature in (SOURCE_SIGNATURE, SEED_SIGNATURE):
        op.execute(
            f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC, night_voyager_api, night_voyager_worker"
        )


def downgrade() -> None:
    tables = (
        "source_packs",
        "student_cases",
        "student_case_revisions",
        "planning_runs",
        "agent_tasks",
    )
    # Match the existing migration guard pattern: take exclusive locks and
    # inspect all tenants as the table owner, restoring FORCE before refusal.
    # Transactional DDL prevents other roles from observing a relaxed policy.
    op.execute(
        "LOCK TABLE " + ",".join(f"app.{name}" for name in tables) + " IN ACCESS EXCLUSIVE MODE"
    )
    for name in tables:
        op.execute(f"ALTER TABLE app.{name} NO FORCE ROW LEVEL SECURITY")
    try:
        history = (
            op.get_bind()
            .exec_driver_sql("""
          SELECT EXISTS(SELECT 1 FROM app.source_packs WHERE id='50000000-0000-0000-0000-000000000017'::uuid)
             OR EXISTS(SELECT 1 FROM app.student_cases WHERE id='49000000-0000-0000-0000-000000000003'::uuid)
             OR EXISTS(SELECT 1 FROM app.student_case_revisions r JOIN app.planning_runs p ON p.organization_id=r.organization_id AND p.id=r.superseded_planning_run_id JOIN app.student_case_revisions old ON old.organization_id=p.organization_id AND old.case_id=p.case_id AND old.revision=p.case_revision WHERE r.student_preferences->'intake' IS DISTINCT FROM old.student_preferences->'intake')
             OR EXISTS(SELECT 1 FROM app.agent_tasks WHERE source_pack_id='50000000-0000-0000-0000-000000000017'::uuid)
        """)
            .scalar_one()
        )
    finally:
        for name in tables:
            op.execute(f"ALTER TABLE app.{name} FORCE ROW LEVEL SECURITY")
    if history:
        raise RuntimeError("refusing downgrade: controlled intake fixture or lineage exists")
    for sql in (
        _BASE._as_replace(
            _BASE._extract_function(
                _BASE._legacy_constant("0007_conversation_and_memory", "DDL_SQL"),
                "validate_collaboration_fact",
            )
        ),
        _BASE.CONFIRM_SQL,
        _BASE._as_replace(_BASE.JOURNEY_PENDING_SQL),
        _RECOVERY.CREATE_SQL,
        _BASE._as_replace(
            _BASE._extract_function(
                _BASE._legacy_constant("0008_versioned_skills", "READ_SQL"),
                "load_persisted_synthetic_planning_snapshot",
            )
        ),
    ):
        op.execute(sql)
    op.execute(f"DROP FUNCTION {SEED_SIGNATURE}")
    op.execute(f"DROP FUNCTION {SOURCE_SIGNATURE}")
