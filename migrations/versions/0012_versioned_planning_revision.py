# ruff: noqa: E501
"""Add durable planning revision, task predecessor, and successor authority."""

from __future__ import annotations

from collections.abc import Sequence
from importlib import import_module

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REVIEW_SIGNATURE = "app.review_planning_run(uuid,uuid,uuid,uuid,integer,text,uuid,jsonb,jsonb,text,uuid,jsonb,date,text,text)"
CONFIRM_SIGNATURE = "app.verify_memory_candidate(uuid,uuid,uuid,integer,text,text,uuid,uuid,text,text)"
CREATE_TASK_SIGNATURE = "app.create_agent_task(uuid,uuid,uuid,uuid,text,integer,uuid,integer,text,jsonb,text,text)"
FINALIZE_SIGNATURE = "app.finalize_agent_task_result(uuid,uuid,text,bigint,uuid,text,text,text,text,jsonb,uuid)"
PERSIST_SIGNATURE = "app.persist_planning_result(uuid,uuid,uuid,integer,uuid,integer,text,text,text,text,text,uuid,jsonb)"
JOURNEY_PENDING_SIGNATURE = (
    "app.read_connected_journey_fact_pending(uuid,uuid,text,uuid)"
)


def _legacy_constant(module_name: str, name: str) -> str:
    value = getattr(import_module(f"migrations.versions.{module_name}"), name)
    if not isinstance(value, str):
        raise TypeError(f"{module_name}.{name} must be SQL text")
    return value


def _extract_function(sql: str, function_name: str) -> str:
    create = f"CREATE FUNCTION app.{function_name}"
    replace = f"CREATE OR REPLACE FUNCTION app.{function_name}"
    start = sql.find(create)
    if start < 0:
        start = sql.find(replace)
    if start < 0:
        raise ValueError(f"legacy function unavailable: {function_name}")
    end = sql.find("$$;", start)
    if end < 0:
        raise ValueError(f"legacy function terminator unavailable: {function_name}")
    return sql[start : end + 3]


def _replace_once(value: str, old: str, new: str) -> str:
    if value.count(old) != 1:
        raise ValueError(f"expected one migration replacement for: {old[:80]}")
    return value.replace(old, new, 1)


def _as_replace(function_sql: str) -> str:
    return function_sql.replace("CREATE FUNCTION ", "CREATE OR REPLACE FUNCTION ", 1)


_BASE_REVIEW = _extract_function(
    _legacy_constant("0003_advisor_family_decision", "UPGRADE_SQL"),
    "review_planning_run",
)
review_sql = _as_replace(_BASE_REVIEW)
review_sql = _replace_once(
    review_sql,
    "DECLARE prior app.idempotency_records%ROWTYPE; selected app.planning_runs%ROWTYPE;",
    "DECLARE prior app.idempotency_records%ROWTYPE; selected_case app.student_cases%ROWTYPE; selected app.planning_runs%ROWTYPE;",
)
review_sql = _replace_once(
    review_sql,
    " IF NOT EXISTS (SELECT 1 FROM app.student_case_participants WHERE organization_id=p_org AND case_id=p_case AND actor_id=p_actor AND role='advisor') THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='participant not assigned'; END IF;\n SELECT * INTO selected FROM app.planning_runs WHERE organization_id=p_org AND id=p_run AND case_id=p_case AND case_revision=p_expected_revision AND state='review_required' AND is_current FOR SHARE;",
    " IF NOT EXISTS (SELECT 1 FROM app.student_case_participants WHERE organization_id=p_org AND case_id=p_case AND actor_id=p_actor AND role='advisor') THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='participant not assigned'; END IF;\n SELECT * INTO selected_case FROM app.student_cases WHERE organization_id=p_org AND id=p_case FOR UPDATE;\n IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='review target is stale'; END IF;\n SELECT * INTO prior FROM app.idempotency_records WHERE organization_id=p_org AND actor_id=p_actor AND operation='advisor_review' AND key_sha256=p_key_hash;\n IF FOUND THEN IF prior.request_sha256<>p_request_hash THEN RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='idempotency request mismatch'; END IF; RETURN QUERY SELECT prior.response_id,(SELECT id FROM app.decision_briefs WHERE organization_id=p_org AND advisor_review_id=prior.response_id),(SELECT state FROM app.student_cases WHERE organization_id=p_org AND id=p_case),true; RETURN; END IF;\n IF p_action='request_revision' AND EXISTS (SELECT 1 FROM app.advisor_reviews review_row WHERE review_row.organization_id=p_org AND review_row.planning_run_id=p_run AND review_row.action='request_revision') THEN RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='review authority already exists'; END IF;\n IF selected_case.current_revision IS DISTINCT FROM p_expected_revision OR selected_case.state IS DISTINCT FROM 'advisor_review' THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='review target is stale'; END IF;\n SELECT * INTO selected FROM app.planning_runs WHERE organization_id=p_org AND id=p_run AND case_id=p_case AND case_revision=p_expected_revision AND state='review_required' AND is_current FOR UPDATE;",
)
review_sql = _replace_once(
    review_sql,
    " INSERT INTO app.advisor_reviews VALUES(p_org,p_review,p_case,p_expected_revision,p_run,version,p_actor,p_action,p_eligible,p_risks,p_notes,clock_timestamp());",
    " BEGIN\n  INSERT INTO app.advisor_reviews VALUES(p_org,p_review,p_case,p_expected_revision,p_run,version,p_actor,p_action,p_eligible,p_risks,p_notes,clock_timestamp());\n EXCEPTION WHEN unique_violation THEN\n  RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='review authority already exists';\n END;",
)
REVIEW_SQL = review_sql

_BASE_CONFIRM = _extract_function(
    _legacy_constant("0007_conversation_and_memory", "MUTATION_SQL"),
    "verify_memory_candidate",
)
confirm_sql = _as_replace(_BASE_CONFIRM)
confirm_sql = _replace_once(
    confirm_sql,
    "current_run app.planning_runs%ROWTYPE; current_revision app.student_case_revisions%ROWTYPE;",
    "current_run app.planning_runs%ROWTYPE; request_review app.advisor_reviews%ROWTYPE; current_revision app.student_case_revisions%ROWTYPE;",
)
confirm_sql = _replace_once(
    confirm_sql,
    "  IF EXISTS (\n    SELECT 1 FROM app.agent_tasks task\n     WHERE task.organization_id=p_org AND task.case_id=resolved_case\n       AND task.state IN ('queued','leased','running','waiting_review')\n  ) THEN\n    RAISE EXCEPTION USING ERRCODE='NV014', MESSAGE='active task blocks revision publication';\n  END IF;",
    "  SELECT * INTO request_review FROM app.advisor_reviews review_row\n   WHERE review_row.organization_id=p_org AND review_row.case_id=resolved_case\n     AND review_row.case_revision=p_expected_revision\n     AND review_row.planning_run_id=current_run.id\n     AND review_row.action='request_revision' FOR SHARE;\n  IF EXISTS (\n    SELECT 1 FROM app.agent_tasks task\n     WHERE task.organization_id=p_org AND task.case_id=resolved_case\n       AND task.state IN ('queued','leased','running','waiting_review')\n       AND NOT (\n         task.state='waiting_review'\n         AND task.case_revision=p_expected_revision\n         AND task.result_planning_run_id=current_run.id\n         AND request_review.id IS NOT NULL\n       )\n  ) THEN\n    RAISE EXCEPTION USING ERRCODE='NV014', MESSAGE='active task blocks revision publication';\n  END IF;",
)
confirm_sql = _replace_once(
    confirm_sql,
    "  IF selected_case.state='planning' AND current_run.id IS NULL THEN\n    RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='current planning run is unavailable';\n  END IF;\n\n  SELECT * INTO current_revision",
    "  IF selected_case.state='planning' AND current_run.id IS NULL THEN\n    RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='current planning run is unavailable';\n  END IF;\n  IF current_run.id IS NOT NULL THEN\n    SELECT * INTO request_review FROM app.advisor_reviews review_row\n     WHERE review_row.organization_id=p_org AND review_row.case_id=resolved_case\n       AND review_row.case_revision=p_expected_revision\n       AND review_row.planning_run_id=current_run.id\n       AND review_row.action='request_revision' FOR SHARE;\n    IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='request revision authority is unavailable'; END IF;\n    IF candidate.fact_key NOT IN ('student.preferred_countries','family.budget') THEN\n      RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='unsupported planning revision fact';\n    END IF;\n    IF EXISTS (SELECT 1 FROM app.family_decisions decision_row WHERE decision_row.organization_id=p_org AND decision_row.case_id=resolved_case)\n       OR EXISTS (SELECT 1 FROM app.timeline_plans timeline_row JOIN app.family_decisions decision_row ON decision_row.organization_id=timeline_row.organization_id AND decision_row.id=timeline_row.family_decision_id WHERE decision_row.organization_id=p_org AND decision_row.case_id=resolved_case) THEN\n      RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='finalized Case cannot be revised';\n    END IF;\n  END IF;\n\n  SELECT * INTO current_revision",
)
confirm_sql = _replace_once(
    confirm_sql,
    "  INSERT INTO app.student_case_revisions(\n    organization_id,case_id,revision,schema_version,student_preferences,family_preferences\n  ) VALUES(p_org,resolved_case,next_revision,1,next_student,next_family);",
    "  INSERT INTO app.student_case_revisions(\n    organization_id,case_id,revision,schema_version,student_preferences,family_preferences,\n    revision_requested_by_review_id,superseded_planning_run_id\n  ) VALUES(p_org,resolved_case,next_revision,1,next_student,next_family,request_review.id,current_run.id);",
)
CONFIRM_SQL = confirm_sql

_BASE_CREATE_TASK = _extract_function(
    _legacy_constant("0009_explicit_planning_start_authority", "CREATE_TASK_SQL"),
    "create_agent_task",
)
create_task_sql = _as_replace(_BASE_CREATE_TASK)
create_task_sql = _replace_once(
    create_task_sql,
    "current_case app.student_cases%ROWTYPE; definition",
    "current_case app.student_cases%ROWTYPE; current_revision app.student_case_revisions%ROWTYPE; definition",
)
create_task_sql = _replace_once(
    create_task_sql,
    "  IF current_case.state='intake' AND p_operation='generate_planning_run_v1' THEN",
    "  SELECT * INTO current_revision FROM app.student_case_revisions revision_row\n   WHERE revision_row.organization_id=p_org AND revision_row.case_id=p_case\n     AND revision_row.revision=p_revision FOR SHARE;\n  IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='task revision lineage is unavailable'; END IF;\n  IF current_case.state='intake' AND p_operation='generate_planning_run_v1' THEN",
)
create_task_sql = _replace_once(
    create_task_sql,
    "    skill_version_id,skill_activation_event_id,skill_activation_sequence,runtime_binding_sha256\n  ) VALUES(",
    "    skill_version_id,skill_activation_event_id,skill_activation_sequence,runtime_binding_sha256,\n    predecessor_planning_run_id\n  ) VALUES(",
)
create_task_sql = _replace_once(
    create_task_sql,
    "    version.runtime_binding_sha256\n  );",
    "    version.runtime_binding_sha256,current_revision.superseded_planning_run_id\n  );",
)
CREATE_TASK_SQL = create_task_sql

_BASE_PERSIST = _extract_function(
    _legacy_constant("0007_conversation_and_memory", "PLANNING_PERSISTENCE_LOCK_SQL"),
    "persist_planning_result",
)
persist_sql = _as_replace(_BASE_PERSIST)
persist_sql = _replace_once(
    persist_sql,
    "selected_case app.student_cases%ROWTYPE;",
    "selected_case app.student_cases%ROWTYPE; selected_revision app.student_case_revisions%ROWTYPE; predecessor app.planning_runs%ROWTYPE;",
)
persist_sql = _replace_once(
    persist_sql,
    " IF p_supersedes IS NOT NULL THEN UPDATE app.planning_runs SET is_current=false WHERE organization_id=p_org AND id=p_supersedes AND is_current=true; IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='superseded run is stale'; END IF; END IF;",
    " SELECT * INTO selected_revision FROM app.student_case_revisions revision_row WHERE revision_row.organization_id=p_org AND revision_row.case_id=p_case AND revision_row.revision=p_revision FOR SHARE;\n IF NOT FOUND OR selected_revision.superseded_planning_run_id IS DISTINCT FROM p_supersedes THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='planning predecessor differs from revision lineage'; END IF;\n IF p_supersedes IS NOT NULL THEN\n  SELECT * INTO predecessor FROM app.planning_runs predecessor_row WHERE predecessor_row.organization_id=p_org AND predecessor_row.id=p_supersedes AND predecessor_row.case_id=p_case AND predecessor_row.case_revision=p_revision-1 FOR SHARE;\n  IF NOT FOUND OR predecessor.is_current THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='planning predecessor is unavailable'; END IF;\n END IF;",
)
PERSIST_SQL = persist_sql

_BASE_FINALIZE = _extract_function(
    _legacy_constant("0004_agent_tasks_executions_events", "UPGRADE_SQL"),
    "finalize_agent_task_result",
)
finalize_sql = _as_replace(_BASE_FINALIZE)
finalize_sql = _replace_once(
    finalize_sql,
    "  IF NOT FOUND OR selected.state NOT IN ('leased','running')",
    "  IF FOUND AND selected.result_planning_run_id=p_run AND selected.state IN ('waiting_review','blocked','failed') THEN\n    IF selected.lease_generation IS DISTINCT FROM p_generation THEN RAISE EXCEPTION USING ERRCODE='NV010', MESSAGE='lease generation lost'; END IF;\n    IF selected.state IS DISTINCT FROM CASE WHEN p_state='review_required' THEN 'waiting_review' ELSE p_state END\n       OR p_supersedes IS DISTINCT FROM selected.predecessor_planning_run_id\n       OR NOT EXISTS (SELECT 1 FROM app.planning_runs run_row WHERE run_row.organization_id=p_org AND run_row.id=p_run AND run_row.state=p_state AND run_row.reason_code IS NOT DISTINCT FROM p_reason AND run_row.evidence_projection_sha256=p_evidence_hash AND run_row.output_sha256=p_output_hash AND run_row.supersedes_run_id IS NOT DISTINCT FROM p_supersedes)\n       OR NOT EXISTS (SELECT 1 FROM app.agent_executions execution_row WHERE execution_row.organization_id=p_org AND execution_row.task_id=p_task AND execution_row.lease_generation=p_generation AND execution_row.status=CASE WHEN p_state='review_required' THEN 'succeeded' ELSE p_state END AND execution_row.output_sha256=p_output_hash AND execution_row.result_planning_run_id=p_run AND execution_row.public_code IS NOT DISTINCT FROM p_reason)\n    THEN RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='task result replay mismatch'; END IF;\n    RETURN selected.state;\n  END IF;\n  IF NOT FOUND OR selected.state NOT IN ('leased','running')",
)
finalize_sql = _replace_once(
    finalize_sql,
    "  IF p_state NOT IN ('review_required','blocked','failed') THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid planning result state'; END IF;\n  PERFORM app.persist_planning_result",
    "  IF p_state NOT IN ('review_required','blocked','failed') THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid planning result state'; END IF;\n  IF p_supersedes IS DISTINCT FROM selected.predecessor_planning_run_id THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='task predecessor mismatch'; END IF;\n  PERFORM app.persist_planning_result",
)
finalize_sql = _replace_once(
    finalize_sql,
    "p_output_hash,p_supersedes,p_output);",
    "p_output_hash,selected.predecessor_planning_run_id,p_output);",
)
FINALIZE_SQL = finalize_sql

DDL_SQL = r"""
ALTER TABLE app.advisor_reviews
  ADD CONSTRAINT advisor_reviews_org_case_id_unique
    UNIQUE (organization_id,case_id,id);

ALTER TABLE app.planning_runs
  ADD CONSTRAINT planning_runs_org_case_id_unique
    UNIQUE (organization_id,case_id,id);

ALTER TABLE app.student_case_revisions
  ADD COLUMN revision_requested_by_review_id uuid,
  ADD COLUMN superseded_planning_run_id uuid,
  ADD CONSTRAINT student_case_revisions_lineage_pair CHECK (
    (revision_requested_by_review_id IS NULL) =
    (superseded_planning_run_id IS NULL)
  ),
  ADD CONSTRAINT student_case_revisions_initial_lineage_null CHECK (
    revision <> 1 OR (
      revision_requested_by_review_id IS NULL AND
      superseded_planning_run_id IS NULL
    )
  ),
  ADD CONSTRAINT student_case_revisions_review_fk
    FOREIGN KEY (organization_id,case_id,revision_requested_by_review_id)
    REFERENCES app.advisor_reviews(organization_id,case_id,id),
  ADD CONSTRAINT student_case_revisions_predecessor_fk
    FOREIGN KEY (organization_id,case_id,superseded_planning_run_id)
    REFERENCES app.planning_runs(organization_id,case_id,id);

ALTER TABLE app.agent_tasks
  ADD COLUMN predecessor_planning_run_id uuid,
  ADD CONSTRAINT agent_tasks_predecessor_fk
    FOREIGN KEY (organization_id,case_id,predecessor_planning_run_id)
    REFERENCES app.planning_runs(organization_id,case_id,id);

CREATE UNIQUE INDEX student_case_revisions_one_planning_successor
ON app.student_case_revisions(
  organization_id,
  case_id,
  superseded_planning_run_id
)
WHERE superseded_planning_run_id IS NOT NULL;

CREATE UNIQUE INDEX planning_runs_one_successor
ON app.planning_runs(organization_id,supersedes_run_id)
WHERE supersedes_run_id IS NOT NULL;

CREATE UNIQUE INDEX advisor_reviews_one_request_revision_per_run
ON app.advisor_reviews(organization_id,planning_run_id)
WHERE action='request_revision';

CREATE INDEX agent_tasks_case_revision_read_idx
ON app.agent_tasks(
  organization_id,case_id,case_revision,created_at DESC,id
);

CREATE INDEX advisor_reviews_case_revision_run_idx
ON app.advisor_reviews(
  organization_id,case_id,case_revision,planning_run_id,review_version DESC
);
"""

JOURNEY_PENDING_SQL = r"""
CREATE FUNCTION app.read_connected_journey_fact_pending(
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
       AND candidate.fact_key IN ('student.preferred_countries','family.budget')
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

PRIVILEGE_SQL = f"""
REVOKE ALL ON FUNCTION {REVIEW_SIGNATURE} FROM PUBLIC;
REVOKE ALL ON FUNCTION {REVIEW_SIGNATURE} FROM night_voyager_worker;
GRANT EXECUTE ON FUNCTION {REVIEW_SIGNATURE} TO night_voyager_api;
REVOKE ALL ON FUNCTION {CONFIRM_SIGNATURE} FROM PUBLIC;
REVOKE ALL ON FUNCTION {CONFIRM_SIGNATURE} FROM night_voyager_worker;
GRANT EXECUTE ON FUNCTION {CONFIRM_SIGNATURE} TO night_voyager_api;
REVOKE ALL ON FUNCTION {CREATE_TASK_SIGNATURE} FROM PUBLIC;
REVOKE ALL ON FUNCTION {CREATE_TASK_SIGNATURE} FROM night_voyager_worker;
GRANT EXECUTE ON FUNCTION {CREATE_TASK_SIGNATURE} TO night_voyager_api;
REVOKE ALL ON FUNCTION {FINALIZE_SIGNATURE} FROM PUBLIC;
REVOKE ALL ON FUNCTION {FINALIZE_SIGNATURE} FROM night_voyager_api;
GRANT EXECUTE ON FUNCTION {FINALIZE_SIGNATURE} TO night_voyager_worker;
REVOKE ALL ON FUNCTION {PERSIST_SIGNATURE} FROM PUBLIC;
REVOKE ALL ON FUNCTION {PERSIST_SIGNATURE} FROM night_voyager_api;
REVOKE ALL ON FUNCTION {PERSIST_SIGNATURE} FROM night_voyager_worker;
REVOKE ALL ON FUNCTION {JOURNEY_PENDING_SIGNATURE} FROM PUBLIC;
REVOKE ALL ON FUNCTION {JOURNEY_PENDING_SIGNATURE} FROM night_voyager_worker;
GRANT EXECUTE ON FUNCTION {JOURNEY_PENDING_SIGNATURE} TO night_voyager_api;
"""


def _split_statements(sql: str) -> list[str]:
    statements: list[str] = []
    buffer: list[str] = []
    in_dollar_quote = False
    for line in sql.splitlines():
        if "$$" in line:
            in_dollar_quote = not in_dollar_quote
        buffer.append(line)
        if not in_dollar_quote and line.rstrip().endswith(";"):
            statement = "\n".join(buffer).strip()
            if statement:
                statements.append(statement)
            buffer = []
    if buffer and "\n".join(buffer).strip():
        raise ValueError("unterminated SQL statement")
    return statements


def _execute_sql(sql: str) -> None:
    for statement in _split_statements(sql):
        op.execute(statement)


def upgrade() -> None:
    _execute_sql(DDL_SQL)
    for function_sql in (
        REVIEW_SQL,
        CONFIRM_SQL,
        CREATE_TASK_SQL,
        PERSIST_SQL,
        FINALIZE_SQL,
        JOURNEY_PENDING_SQL,
    ):
        op.execute(function_sql)
    _execute_sql(PRIVILEGE_SQL)


def downgrade() -> None:
    connection = op.get_bind()
    op.execute(
        "LOCK TABLE app.student_case_revisions,app.agent_tasks "
        "IN ACCESS EXCLUSIVE MODE"
    )
    op.execute(
        "ALTER TABLE app.student_case_revisions NO FORCE ROW LEVEL SECURITY"
    )
    op.execute("ALTER TABLE app.agent_tasks NO FORCE ROW LEVEL SECURITY")
    try:
        history = connection.exec_driver_sql(
            "SELECT EXISTS("
            "SELECT 1 FROM app.student_case_revisions "
            "WHERE superseded_planning_run_id IS NOT NULL "
            "UNION ALL "
            "SELECT 1 FROM app.agent_tasks "
            "WHERE predecessor_planning_run_id IS NOT NULL)"
        ).scalar_one()
    finally:
        op.execute(
            "ALTER TABLE app.student_case_revisions FORCE ROW LEVEL SECURITY"
        )
        op.execute("ALTER TABLE app.agent_tasks FORCE ROW LEVEL SECURITY")
    if history:
        raise RuntimeError("refusing downgrade: planning revision lineage exists")

    op.execute(f"DROP FUNCTION {JOURNEY_PENDING_SIGNATURE}")
    for function_sql in (
        _as_replace(_BASE_REVIEW),
        _as_replace(_BASE_CONFIRM),
        _as_replace(_BASE_CREATE_TASK),
        _as_replace(_BASE_PERSIST),
        _as_replace(_BASE_FINALIZE),
    ):
        op.execute(function_sql)

    _execute_sql(
        f"""
REVOKE ALL ON FUNCTION {REVIEW_SIGNATURE} FROM PUBLIC;
GRANT EXECUTE ON FUNCTION {REVIEW_SIGNATURE} TO night_voyager_api;
REVOKE ALL ON FUNCTION {CONFIRM_SIGNATURE} FROM PUBLIC;
GRANT EXECUTE ON FUNCTION {CONFIRM_SIGNATURE} TO night_voyager_api;
REVOKE ALL ON FUNCTION {CREATE_TASK_SIGNATURE} FROM PUBLIC;
GRANT EXECUTE ON FUNCTION {CREATE_TASK_SIGNATURE} TO night_voyager_api;
REVOKE ALL ON FUNCTION {FINALIZE_SIGNATURE} FROM PUBLIC;
GRANT EXECUTE ON FUNCTION {FINALIZE_SIGNATURE} TO night_voyager_worker;
REVOKE ALL ON FUNCTION {PERSIST_SIGNATURE} FROM PUBLIC;
GRANT EXECUTE ON FUNCTION {PERSIST_SIGNATURE} TO night_voyager_api;
"""
    )
    _execute_sql(
        """
DROP INDEX app.advisor_reviews_case_revision_run_idx;
DROP INDEX app.agent_tasks_case_revision_read_idx;
DROP INDEX app.advisor_reviews_one_request_revision_per_run;
DROP INDEX app.planning_runs_one_successor;
DROP INDEX app.student_case_revisions_one_planning_successor;
ALTER TABLE app.agent_tasks
  DROP CONSTRAINT agent_tasks_predecessor_fk,
  DROP COLUMN predecessor_planning_run_id;
ALTER TABLE app.student_case_revisions
  DROP CONSTRAINT student_case_revisions_predecessor_fk,
  DROP CONSTRAINT student_case_revisions_review_fk,
  DROP CONSTRAINT student_case_revisions_initial_lineage_null,
  DROP CONSTRAINT student_case_revisions_lineage_pair,
  DROP COLUMN superseded_planning_run_id,
  DROP COLUMN revision_requested_by_review_id;
ALTER TABLE app.planning_runs
  DROP CONSTRAINT planning_runs_org_case_id_unique;
ALTER TABLE app.advisor_reviews
  DROP CONSTRAINT advisor_reviews_org_case_id_unique;
"""
    )
