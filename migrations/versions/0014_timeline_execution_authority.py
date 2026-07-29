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
    "app.start_timeline_execution(uuid,uuid,text,uuid,uuid,uuid,text,text)",
    "app.attest_timeline_checkpoint(uuid,uuid,text,uuid,uuid,integer,integer,text,text,text,text,uuid,uuid,text,text)",
    "app.verify_timeline_checkpoint(uuid,uuid,text,uuid,uuid,uuid,integer,integer,text,text,uuid,uuid,text,text)",
    "app.request_timeline_reassessment(uuid,uuid,text,uuid,uuid,uuid,integer,integer,text,uuid,uuid,text,text)",
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
  FOREIGN KEY (organization_id,attestation_id)
    REFERENCES app.timeline_checkpoint_attestations(organization_id,attestation_id),
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
CREATE FUNCTION app.start_timeline_execution(p_org uuid,p_actor uuid,p_role text,p_timeline uuid,p_execution uuid,p_receipt uuid,p_key_hash text,p_request_hash text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN RAISE EXCEPTION USING ERRCODE='NV003',MESSAGE='timeline execution mutation unavailable'; END; $$;
CREATE FUNCTION app.attest_timeline_checkpoint(p_org uuid,p_actor uuid,p_role text,p_execution uuid,p_checkpoint uuid,p_expected_execution_version integer,p_expected_checkpoint_version integer,p_kind text,p_status text,p_attestation_code text,p_reason_code text,p_attestation uuid,p_receipt uuid,p_key_hash text,p_request_hash text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN RAISE EXCEPTION USING ERRCODE='NV003',MESSAGE='timeline execution mutation unavailable'; END; $$;
CREATE FUNCTION app.verify_timeline_checkpoint(p_org uuid,p_actor uuid,p_role text,p_execution uuid,p_checkpoint uuid,p_attestation uuid,p_expected_execution_version integer,p_expected_checkpoint_version integer,p_action text,p_reason_code text,p_verification uuid,p_receipt uuid,p_key_hash text,p_request_hash text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN RAISE EXCEPTION USING ERRCODE='NV003',MESSAGE='timeline execution mutation unavailable'; END; $$;
CREATE FUNCTION app.request_timeline_reassessment(p_org uuid,p_actor uuid,p_role text,p_execution uuid,p_checkpoint uuid,p_trigger_reference uuid,p_expected_execution_version integer,p_expected_checkpoint_version integer,p_trigger text,p_reassessment uuid,p_receipt uuid,p_key_hash text,p_request_hash text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN RAISE EXCEPTION USING ERRCODE='NV003',MESSAGE='timeline execution mutation unavailable'; END; $$;

REVOKE ALL ON FUNCTION app.read_plan_execution_context(uuid,uuid,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.read_timeline_execution(uuid,uuid,text,uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.start_timeline_execution(uuid,uuid,text,uuid,uuid,uuid,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.attest_timeline_checkpoint(uuid,uuid,text,uuid,uuid,integer,integer,text,text,text,text,uuid,uuid,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.verify_timeline_checkpoint(uuid,uuid,text,uuid,uuid,uuid,integer,integer,text,text,uuid,uuid,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.request_timeline_reassessment(uuid,uuid,text,uuid,uuid,uuid,integer,integer,text,uuid,uuid,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.read_plan_execution_context(uuid,uuid,text,text) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.read_timeline_execution(uuid,uuid,text,uuid) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.start_timeline_execution(uuid,uuid,text,uuid,uuid,uuid,text,text) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.attest_timeline_checkpoint(uuid,uuid,text,uuid,uuid,integer,integer,text,text,text,text,uuid,uuid,text,text) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.verify_timeline_checkpoint(uuid,uuid,text,uuid,uuid,uuid,integer,integer,text,text,uuid,uuid,text,text) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.request_timeline_reassessment(uuid,uuid,text,uuid,uuid,uuid,integer,integer,text,uuid,uuid,text,text) TO night_voyager_api;
GRANT SELECT ON app.timeline_executions,app.timeline_checkpoints,
  app.timeline_checkpoint_attestations,app.timeline_checkpoint_verifications,
  app.timeline_reassessment_requests,app.timeline_mutation_receipts
  TO night_voyager_api;
REVOKE ALL ON app.timeline_executions,app.timeline_checkpoints,
  app.timeline_checkpoint_attestations,app.timeline_checkpoint_verifications,
  app.timeline_reassessment_requests,app.timeline_mutation_receipts
  FROM night_voyager_worker;
"""


def upgrade() -> None:
    for statement in _split_statements(UPGRADE_SQL):
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
