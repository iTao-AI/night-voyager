# ruff: noqa: E501
"""Add the closed migrator-only planning revision demo seed helper."""

from __future__ import annotations

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

SIGNATURE = (
    "app.seed_demo_planning_revision_fact("
    "uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,jsonb,text,text,text,text)"
)

FUNCTION_SQL = r"""
CREATE FUNCTION app.seed_demo_planning_revision_fact(
  p_org uuid,
  p_case uuid,
  p_thread uuid,
  p_advisor uuid,
  p_student uuid,
  p_message uuid,
  p_candidate uuid,
  p_verification uuid,
  p_fact uuid,
  p_preferred_countries jsonb,
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
     OR p_preferred_countries IS DISTINCT FROM
        '["australia","japan","malaysia"]'::jsonb
     OR p_value_sha256 IS DISTINCT FROM
        '1a94b49fe4387c325f901de7f581b6b0c18ebbbef296c37b75f9cfb29e6aa2b7'
  THEN
    RAISE EXCEPTION USING
      ERRCODE='NV003',
      MESSAGE='planning revision demo seed mismatch';
  END IF;

  IF p_case='49000000-0000-0000-0000-000000000001'::uuid THEN
    IF p_thread IS DISTINCT FROM '4b000000-0000-0000-0000-000000000001'::uuid
       OR p_message IS DISTINCT FROM '4c000000-0000-0000-0000-000000000001'::uuid
       OR p_candidate IS DISTINCT FROM '4d000000-0000-0000-0000-000000000001'::uuid
       OR p_verification IS DISTINCT FROM '4e000000-0000-0000-0000-000000000001'::uuid
       OR p_fact IS DISTINCT FROM '4f000000-0000-0000-0000-000000000001'::uuid
       OR p_message_request_sha256 IS DISTINCT FROM
          '73c0530d8c132d21b6b0d14586af5dc3e73e87e9f8ef19e50991b055011f1244'
       OR p_candidate_request_sha256 IS DISTINCT FROM
          '8d260f0ae2dc3a421c5a7409f950f9f3f9e4743a1632791e576bd508b215dd63'
       OR p_verification_request_sha256 IS DISTINCT FROM
          '5a93792cc96bdc4aeb4957cf1280397f9028810c0d32f53bb15a75c284d6c036'
    THEN
      RAISE EXCEPTION USING
        ERRCODE='NV003',
        MESSAGE='planning revision demo seed mismatch';
    END IF;
  ELSIF p_case='49000000-0000-0000-0000-000000000002'::uuid THEN
    IF p_thread IS DISTINCT FROM '4b000000-0000-0000-0000-000000000002'::uuid
       OR p_message IS DISTINCT FROM '4c000000-0000-0000-0000-000000000002'::uuid
       OR p_candidate IS DISTINCT FROM '4d000000-0000-0000-0000-000000000002'::uuid
       OR p_verification IS DISTINCT FROM '4e000000-0000-0000-0000-000000000002'::uuid
       OR p_fact IS DISTINCT FROM '4f000000-0000-0000-0000-000000000002'::uuid
       OR p_message_request_sha256 IS DISTINCT FROM
          '7f877001d19e08e9596b7d2750ec360b7d4acf9b90b89286a9864f8dac1f1725'
       OR p_candidate_request_sha256 IS DISTINCT FROM
          'c3c418833190b6dcfb3fcbc22d686b69048a5e7a166f5b25d6a22fe48aa80135'
       OR p_verification_request_sha256 IS DISTINCT FROM
          '0f8dedd651fe442331f397304920fde252f08d2af0fff38645a27291ccfbbfd6'
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
         AND fact_key='student.preferred_countries'
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
           AND body='Synthetic initial preferred countries.'
           AND content_sha256=
             '2e5e0c34691d199e9b3ddc52cc8b869c8e0f03eee68f30eb08407cf3c01455c0'
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
           AND fact_key='student.preferred_countries'
           AND proposed_value=p_preferred_countries
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
           AND fact_key='student.preferred_countries'
           AND value=p_preferred_countries
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
          AND fact_key='student.preferred_countries')
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
    'Synthetic initial preferred countries.',
    '2e5e0c34691d199e9b3ddc52cc8b869c8e0f03eee68f30eb08407cf3c01455c0',
    p_message_request_sha256,timestamptz '2026-01-01 00:00:01+00'
  );
  INSERT INTO app.memory_candidates(
    organization_id,id,case_id,case_revision,message_event_id,
    subject_actor_id,subject_role,proposing_actor_id,proposing_role,
    fact_key,proposed_value,value_sha256,request_sha256,created_at,expires_at
  ) VALUES(
    p_org,p_candidate,p_case,1,p_message,p_student,'student',p_student,'student',
    'student.preferred_countries',p_preferred_countries,p_value_sha256,
    p_candidate_request_sha256,timestamptz '2026-01-01 00:00:02+00',
    timestamptz '2026-01-08 00:00:02+00'
  );
  INSERT INTO app.confirmed_facts(
    organization_id,id,case_id,fact_key,value,value_sha256,
    source_candidate_id,source_message_event_id,subject_actor_id,subject_role,
    confirming_advisor_actor_id,confirming_advisor_role,supersedes_fact_id,
    fact_version,confirmed_at
  ) VALUES(
    p_org,p_fact,p_case,'student.preferred_countries',p_preferred_countries,
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
    p_org,p_case,1,'student.preferred_countries',p_fact,
    timestamptz '2026-01-01 00:00:03+00'
  );
END; $$;
"""

PRIVILEGE_SQL = r"""
REVOKE ALL ON FUNCTION app.seed_demo_planning_revision_fact(uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,jsonb,text,text,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.seed_demo_planning_revision_fact(uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,jsonb,text,text,text,text) FROM night_voyager_api;
REVOKE ALL ON FUNCTION app.seed_demo_planning_revision_fact(uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,jsonb,text,text,text,text) FROM night_voyager_worker;
"""


def _execute_sql(sql: str) -> None:
    for statement in (item.strip() for item in sql.splitlines() if item.strip()):
        op.execute(statement)


def upgrade() -> None:
    op.execute(FUNCTION_SQL)
    _execute_sql(PRIVILEGE_SQL)


def downgrade() -> None:
    op.execute(
        "DROP FUNCTION app.seed_demo_planning_revision_fact(uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,jsonb,text,text,text,text)"
    )
