# ruff: noqa: E501
"""Add versioned Skill governance and runtime pin authority."""

import base64
from collections.abc import Sequence

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "skill_definitions",
    "skill_versions",
    "skill_change_candidates",
    "skill_evaluation_results",
    "skill_activation_events",
)

SCHEMA_SQL = r"""
CREATE TABLE app.skill_definitions (
  organization_id uuid NOT NULL,
  id uuid NOT NULL,
  skill_key text NOT NULL CHECK (skill_key IN (
    'student-profile-intake','study-destination-compare','evidence-research',
    'document-evidence-retrieval','family-decision-brief','application-timeline-guard'
  )),
  owner_actor_id uuid NOT NULL,
  owner_role text NOT NULL DEFAULT 'advisor' CHECK (owner_role='advisor'),
  binding_kind text NOT NULL CHECK (binding_kind IN ('catalog_only','planning_runtime')),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id,id),
  UNIQUE (organization_id,skill_key),
  UNIQUE (organization_id,id,binding_kind),
  UNIQUE (organization_id,id,skill_key,binding_kind),
  FOREIGN KEY (organization_id,owner_actor_id,owner_role)
    REFERENCES app.memberships(organization_id,actor_id,role)
);
CREATE TABLE app.skill_versions (
  organization_id uuid NOT NULL,
  id uuid NOT NULL,
  definition_id uuid NOT NULL,
  skill_key text NOT NULL,
  semantic_version text NOT NULL CHECK (semantic_version ~ '^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'),
  binding_kind text NOT NULL CHECK (binding_kind IN ('catalog_only','planning_runtime')),
  executor_id text,
  executor_version text,
  input_contract_id text NOT NULL,
  input_schema_sha256 text NOT NULL CHECK (input_schema_sha256 ~ '^[0-9a-f]{64}$'),
  output_contract_id text NOT NULL,
  output_schema_sha256 text NOT NULL CHECK (output_schema_sha256 ~ '^[0-9a-f]{64}$'),
  content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
  tool_ids jsonb NOT NULL CHECK (jsonb_typeof(tool_ids)='array'),
  tool_allowlist_sha256 text NOT NULL CHECK (tool_allowlist_sha256 ~ '^[0-9a-f]{64}$'),
  data_scopes jsonb NOT NULL CHECK (jsonb_typeof(data_scopes)='array'),
  data_scope_sha256 text NOT NULL CHECK (data_scope_sha256 ~ '^[0-9a-f]{64}$'),
  side_effect_level text NOT NULL CHECK (side_effect_level IN ('none','bounded_product_write')),
  approval_policy text NOT NULL CHECK (approval_policy IN ('advisor_review_required','family_decision_required')),
  policy_version text NOT NULL,
  policy_sha256 text NOT NULL CHECK (policy_sha256 ~ '^[0-9a-f]{64}$'),
  evaluation_dataset_id text NOT NULL,
  evaluation_dataset_version text NOT NULL,
  evaluation_dataset_sha256 text NOT NULL CHECK (evaluation_dataset_sha256 ~ '^[0-9a-f]{64}$'),
  expected_evaluation_projection jsonb NOT NULL
    CHECK (jsonb_typeof(expected_evaluation_projection)='object'),
  runtime_manifest_id text NOT NULL,
  runtime_manifest_version text NOT NULL,
  runtime_manifest_sha256 text NOT NULL CHECK (runtime_manifest_sha256 ~ '^[0-9a-f]{64}$'),
  operation_bindings jsonb,
  runtime_binding_sha256 text CHECK (runtime_binding_sha256 ~ '^[0-9a-f]{64}$'),
  manifest_projection jsonb NOT NULL CHECK (jsonb_typeof(manifest_projection)='object'),
  supersedes_version_id uuid,
  is_seed boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id,id),
  UNIQUE (organization_id,definition_id,id),
  UNIQUE (organization_id,definition_id,semantic_version),
  UNIQUE (organization_id,definition_id,id,binding_kind),
  UNIQUE (organization_id,definition_id,id,runtime_binding_sha256),
  CHECK (
    (binding_kind='planning_runtime' AND executor_id IS NOT NULL AND executor_version IS NOT NULL
      AND operation_bindings IS NOT NULL AND runtime_binding_sha256 IS NOT NULL)
    OR
    (binding_kind='catalog_only' AND executor_id IS NULL AND executor_version IS NULL
      AND operation_bindings IS NULL AND runtime_binding_sha256 IS NULL)
  ),
  CHECK (
    runtime_manifest_id='night-voyager.skill-runtime-manifest'
    AND runtime_manifest_version='1.0.0'
    AND runtime_manifest_sha256=
      '5e25b89af19a5bff6323e762c9986a7beec93d3e61a55cef18ea1cfc6e2e1e1f'
  ),
  CHECK (
    manifest_projection=jsonb_strip_nulls(jsonb_build_object(
      'schema_version',1,'skill_key',skill_key,'version',semantic_version,
      'binding_kind',binding_kind,'input_contract_id',input_contract_id,
      'input_schema_sha256',input_schema_sha256,
      'output_contract_id',output_contract_id,
      'output_schema_sha256',output_schema_sha256,'content_sha256',content_sha256,
      'tool_ids',tool_ids,'tool_allowlist_sha256',tool_allowlist_sha256,
      'data_scopes',data_scopes,'data_scope_sha256',data_scope_sha256,
      'side_effect_level',side_effect_level,'approval_policy',approval_policy,
      'policy_version',policy_version,'policy_sha256',policy_sha256,
      'evaluation_dataset_id',evaluation_dataset_id,
      'evaluation_dataset_version',evaluation_dataset_version,
      'evaluation_dataset_sha256',evaluation_dataset_sha256,
      'executor_id',executor_id,'executor_version',executor_version,
      'operation_bindings',operation_bindings,
      'runtime_binding_sha256',runtime_binding_sha256
    ))
  ),
  CHECK (
    expected_evaluation_projection->>'schema_version'='1'
    AND expected_evaluation_projection->>'skill_key'=skill_key
    AND expected_evaluation_projection->>'version'=semantic_version
    AND expected_evaluation_projection->>'evaluator_id'=
      'night-voyager.deterministic-skill-evaluator'
    AND expected_evaluation_projection->>'evaluator_version'='v1'
    AND expected_evaluation_projection->>'dataset_id'=evaluation_dataset_id
    AND expected_evaluation_projection->>'dataset_version'=evaluation_dataset_version
    AND expected_evaluation_projection->>'dataset_sha256'=evaluation_dataset_sha256
    AND jsonb_typeof(expected_evaluation_projection->'assertions')='array'
    AND jsonb_array_length(expected_evaluation_projection->'assertions')>0
    AND jsonb_typeof(expected_evaluation_projection->'failed_assertion_ids')='array'
    AND expected_evaluation_projection->>'status' IN ('passed','failed')
    AND expected_evaluation_projection->>'output_sha256' ~ '^[0-9a-f]{64}$'
  ),
  FOREIGN KEY (organization_id,definition_id,skill_key,binding_kind)
    REFERENCES app.skill_definitions(organization_id,id,skill_key,binding_kind),
  FOREIGN KEY (organization_id,definition_id,supersedes_version_id)
    REFERENCES app.skill_versions(organization_id,definition_id,id)
);
CREATE TABLE app.skill_change_candidates (
  organization_id uuid NOT NULL,
  id uuid NOT NULL,
  definition_id uuid NOT NULL,
  base_version_id uuid NOT NULL,
  proposed_version_id uuid NOT NULL,
  provenance text NOT NULL CHECK (provenance IN ('badcase','advisor_feedback','eval_failure','maintainer_proposal')),
  reason text NOT NULL CHECK (octet_length(reason) BETWEEN 1 AND 512),
  reference text CHECK (reference IS NULL OR octet_length(reference) BETWEEN 1 AND 512),
  created_by_actor_id uuid NOT NULL,
  created_by_role text NOT NULL DEFAULT 'advisor' CHECK (created_by_role='advisor'),
  request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id,id),
  UNIQUE (organization_id,definition_id,id),
  UNIQUE (organization_id,definition_id,proposed_version_id),
  CONSTRAINT skill_change_candidates_identity_version_unique
    UNIQUE (organization_id,definition_id,id,proposed_version_id),
  FOREIGN KEY (organization_id,definition_id,base_version_id)
    REFERENCES app.skill_versions(organization_id,definition_id,id),
  FOREIGN KEY (organization_id,definition_id,proposed_version_id)
    REFERENCES app.skill_versions(organization_id,definition_id,id),
  FOREIGN KEY (organization_id,created_by_actor_id,created_by_role)
    REFERENCES app.memberships(organization_id,actor_id,role),
  CHECK (base_version_id<>proposed_version_id)
);
CREATE TABLE app.skill_evaluation_results (
  organization_id uuid NOT NULL,
  id uuid NOT NULL,
  definition_id uuid NOT NULL,
  candidate_id uuid,
  version_id uuid NOT NULL,
  evaluator_id text NOT NULL
    CHECK (evaluator_id='night-voyager.deterministic-skill-evaluator'),
  evaluator_version text NOT NULL CHECK (evaluator_version='v1'),
  dataset_id text NOT NULL,
  dataset_version text NOT NULL,
  dataset_sha256 text NOT NULL CHECK (dataset_sha256 ~ '^[0-9a-f]{64}$'),
  assertion_projection jsonb NOT NULL CHECK (jsonb_typeof(assertion_projection)='array'),
  output_sha256 text NOT NULL CHECK (output_sha256 ~ '^[0-9a-f]{64}$'),
  status text NOT NULL CHECK (status IN ('passed','failed')),
  failed_assertion_ids jsonb NOT NULL CHECK (jsonb_typeof(failed_assertion_ids)='array'),
  request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
  is_seed boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id,id),
  UNIQUE (organization_id,definition_id,id),
  UNIQUE (organization_id,candidate_id),
  UNIQUE (organization_id,definition_id,version_id,evaluator_id,evaluator_version,dataset_id,dataset_version),
  CONSTRAINT skill_evaluation_results_identity_version_unique
    UNIQUE (organization_id,definition_id,id,version_id),
  CONSTRAINT skill_evaluation_results_identity_candidate_unique
    UNIQUE (organization_id,definition_id,id,candidate_id),
  FOREIGN KEY (organization_id,definition_id,version_id)
    REFERENCES app.skill_versions(organization_id,definition_id,id),
  CONSTRAINT skill_evaluation_results_candidate_version_fk
    FOREIGN KEY (organization_id,definition_id,candidate_id,version_id)
    REFERENCES app.skill_change_candidates(
      organization_id,definition_id,id,proposed_version_id
    ),
  CHECK ((is_seed AND candidate_id IS NULL) OR (NOT is_seed AND candidate_id IS NOT NULL)),
  CHECK ((status='passed' AND failed_assertion_ids='[]'::jsonb) OR status='failed')
);
CREATE TABLE app.skill_activation_events (
  organization_id uuid NOT NULL,
  id uuid NOT NULL,
  definition_id uuid NOT NULL,
  binding_kind text NOT NULL DEFAULT 'planning_runtime'
    CHECK (binding_kind='planning_runtime'),
  activated_version_id uuid NOT NULL,
  previous_version_id uuid,
  candidate_id uuid,
  evaluation_id uuid,
  event_kind text NOT NULL CHECK (event_kind IN ('seed','promote','rollback')),
  owner_actor_id uuid NOT NULL,
  owner_role text NOT NULL DEFAULT 'advisor' CHECK (owner_role='advisor'),
  reason text NOT NULL CHECK (octet_length(reason) BETWEEN 1 AND 512),
  request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
  activation_sequence bigint NOT NULL CHECK (activation_sequence>0),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (organization_id,id),
  UNIQUE (organization_id,definition_id,id),
  UNIQUE (organization_id,definition_id,id,activated_version_id,activation_sequence),
  UNIQUE (organization_id,definition_id,activation_sequence),
  FOREIGN KEY (organization_id,definition_id,binding_kind)
    REFERENCES app.skill_definitions(organization_id,id,binding_kind),
  FOREIGN KEY (organization_id,definition_id,activated_version_id,binding_kind)
    REFERENCES app.skill_versions(organization_id,definition_id,id,binding_kind),
  FOREIGN KEY (organization_id,definition_id,previous_version_id,binding_kind)
    REFERENCES app.skill_versions(organization_id,definition_id,id,binding_kind),
  CONSTRAINT skill_activation_events_candidate_version_fk
    FOREIGN KEY (organization_id,definition_id,candidate_id,activated_version_id)
    REFERENCES app.skill_change_candidates(
      organization_id,definition_id,id,proposed_version_id
    ),
  CONSTRAINT skill_activation_events_evaluation_version_fk
    FOREIGN KEY (organization_id,definition_id,evaluation_id,activated_version_id)
    REFERENCES app.skill_evaluation_results(
      organization_id,definition_id,id,version_id
    ),
  CONSTRAINT skill_activation_events_evaluation_candidate_fk
    FOREIGN KEY (organization_id,definition_id,evaluation_id,candidate_id)
    REFERENCES app.skill_evaluation_results(
      organization_id,definition_id,id,candidate_id
    ),
  FOREIGN KEY (organization_id,owner_actor_id,owner_role)
    REFERENCES app.memberships(organization_id,actor_id,role),
  CHECK (
    (event_kind='seed' AND previous_version_id IS NULL AND candidate_id IS NULL AND evaluation_id IS NOT NULL)
    OR (event_kind='promote' AND previous_version_id IS NOT NULL AND candidate_id IS NOT NULL AND evaluation_id IS NOT NULL)
    OR (event_kind='rollback' AND previous_version_id IS NOT NULL AND candidate_id IS NULL AND evaluation_id IS NULL)
  )
);

ALTER TABLE app.skill_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.skill_definitions FORCE ROW LEVEL SECURITY;
CREATE POLICY skill_definitions_tenant_isolation ON app.skill_definitions USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid) WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);
ALTER TABLE app.skill_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.skill_versions FORCE ROW LEVEL SECURITY;
CREATE POLICY skill_versions_tenant_isolation ON app.skill_versions USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid) WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);
ALTER TABLE app.skill_change_candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.skill_change_candidates FORCE ROW LEVEL SECURITY;
CREATE POLICY skill_change_candidates_tenant_isolation ON app.skill_change_candidates USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid) WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);
ALTER TABLE app.skill_evaluation_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.skill_evaluation_results FORCE ROW LEVEL SECURITY;
CREATE POLICY skill_evaluation_results_tenant_isolation ON app.skill_evaluation_results USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid) WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);
ALTER TABLE app.skill_activation_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.skill_activation_events FORCE ROW LEVEL SECURITY;
CREATE POLICY skill_activation_events_tenant_isolation ON app.skill_activation_events USING (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid) WITH CHECK (organization_id=NULLIF(current_setting('night_voyager.organization_id',true),'')::uuid);

CREATE FUNCTION app.reject_skill_authority_mutation() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='Skill authority record is immutable';
END; $$;
CREATE TRIGGER skill_definitions_immutable BEFORE UPDATE OR DELETE ON app.skill_definitions FOR EACH ROW EXECUTE FUNCTION app.reject_skill_authority_mutation();
CREATE TRIGGER skill_versions_immutable BEFORE UPDATE OR DELETE ON app.skill_versions FOR EACH ROW EXECUTE FUNCTION app.reject_skill_authority_mutation();
CREATE TRIGGER skill_change_candidates_immutable BEFORE UPDATE OR DELETE ON app.skill_change_candidates FOR EACH ROW EXECUTE FUNCTION app.reject_skill_authority_mutation();
CREATE TRIGGER skill_evaluation_results_immutable BEFORE UPDATE OR DELETE ON app.skill_evaluation_results FOR EACH ROW EXECUTE FUNCTION app.reject_skill_authority_mutation();
CREATE TRIGGER skill_activation_events_immutable BEFORE UPDATE OR DELETE ON app.skill_activation_events FOR EACH ROW EXECUTE FUNCTION app.reject_skill_authority_mutation();
"""

PIN_SQL = r"""
ALTER TABLE app.agent_tasks ADD COLUMN skill_definition_id uuid;
ALTER TABLE app.agent_tasks ADD COLUMN skill_version_id uuid;
ALTER TABLE app.agent_tasks ADD COLUMN skill_activation_event_id uuid;
ALTER TABLE app.agent_tasks ADD COLUMN skill_activation_sequence bigint;
ALTER TABLE app.agent_tasks ADD COLUMN runtime_binding_sha256 text;
ALTER TABLE app.agent_tasks ADD CONSTRAINT agent_tasks_skill_pin_all_or_none CHECK (
  (skill_definition_id IS NULL AND skill_version_id IS NULL AND skill_activation_event_id IS NULL
    AND skill_activation_sequence IS NULL AND runtime_binding_sha256 IS NULL)
  OR
  (skill_definition_id IS NOT NULL AND skill_version_id IS NOT NULL AND skill_activation_event_id IS NOT NULL
    AND skill_activation_sequence IS NOT NULL AND runtime_binding_sha256 ~ '^[0-9a-f]{64}$')
);
ALTER TABLE app.agent_tasks ADD CONSTRAINT agent_tasks_skill_version_fk
  FOREIGN KEY (organization_id,skill_definition_id,skill_version_id,runtime_binding_sha256)
  REFERENCES app.skill_versions(organization_id,definition_id,id,runtime_binding_sha256);
ALTER TABLE app.agent_tasks ADD CONSTRAINT agent_tasks_skill_activation_fk
  FOREIGN KEY (organization_id,skill_definition_id,skill_activation_event_id,skill_version_id,skill_activation_sequence)
  REFERENCES app.skill_activation_events(organization_id,definition_id,id,activated_version_id,activation_sequence);
ALTER TABLE app.agent_tasks ADD CONSTRAINT agent_tasks_skill_pin_identity_unique
  UNIQUE (organization_id,id,skill_definition_id,skill_version_id,skill_activation_event_id,skill_activation_sequence,runtime_binding_sha256);

ALTER TABLE app.agent_executions ADD COLUMN skill_definition_id uuid;
ALTER TABLE app.agent_executions ADD COLUMN skill_version_id uuid;
ALTER TABLE app.agent_executions ADD COLUMN skill_activation_event_id uuid;
ALTER TABLE app.agent_executions ADD COLUMN skill_activation_sequence bigint;
ALTER TABLE app.agent_executions ADD COLUMN runtime_binding_sha256 text;
ALTER TABLE app.agent_executions ADD CONSTRAINT agent_executions_skill_pin_all_or_none CHECK (
  (skill_definition_id IS NULL AND skill_version_id IS NULL AND skill_activation_event_id IS NULL
    AND skill_activation_sequence IS NULL AND runtime_binding_sha256 IS NULL)
  OR
  (skill_definition_id IS NOT NULL AND skill_version_id IS NOT NULL AND skill_activation_event_id IS NOT NULL
    AND skill_activation_sequence IS NOT NULL AND runtime_binding_sha256 ~ '^[0-9a-f]{64}$')
);
ALTER TABLE app.agent_executions ADD CONSTRAINT agent_executions_task_skill_pin_fk
  FOREIGN KEY (organization_id,task_id,skill_definition_id,skill_version_id,skill_activation_event_id,skill_activation_sequence,runtime_binding_sha256)
  REFERENCES app.agent_tasks(organization_id,id,skill_definition_id,skill_version_id,skill_activation_event_id,skill_activation_sequence,runtime_binding_sha256);

DROP INDEX app.agent_tasks_one_effective_operation;
CREATE UNIQUE INDEX agent_tasks_one_effective_operation ON app.agent_tasks(
  organization_id,case_id,operation,case_revision,source_pack_id,source_pack_version,policy_version,
  skill_definition_id,skill_version_id,skill_activation_event_id,skill_activation_sequence,runtime_binding_sha256
) WHERE state IN ('queued','leased','running','waiting_review','succeeded');
"""

LEGACY_UPGRADE_SQL = r"""
DO $$
DECLARE selected record;
BEGIN
  FOR selected IN
    SELECT organization_id,id,attempt_count,lease_generation
      FROM app.agent_tasks
     WHERE state IN ('queued','leased','running')
       AND skill_definition_id IS NULL
     ORDER BY organization_id,id
     FOR UPDATE
  LOOP
    PERFORM set_config('night_voyager.organization_id',selected.organization_id::text,true);
    UPDATE app.agent_executions
       SET status='cancelled',retryable=false,public_code='legacy_unpinned',
           duration_ms=GREATEST(0,floor(extract(epoch FROM (clock_timestamp()-COALESCE(started_at,created_at)))*1000)::integer),
           finished_at=clock_timestamp()
     WHERE organization_id=selected.organization_id AND task_id=selected.id
       AND lease_generation=selected.lease_generation AND status IN ('leased','running');
    UPDATE app.agent_tasks
       SET state='cancelled',row_version=row_version+1,lease_owner=NULL,lease_expires_at=NULL,
           terminal_code='legacy_unpinned',updated_at=clock_timestamp()
     WHERE organization_id=selected.organization_id AND id=selected.id;
    DELETE FROM internal.agent_task_dispatch
     WHERE organization_id=selected.organization_id AND task_id=selected.id;
    PERFORM app.append_agent_task_event(
      selected.organization_id,selected.id,'cancelled','cancelled','legacy_unpinned',selected.attempt_count,NULL
    );
  END LOOP;
END; $$;
"""


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
        op.execute(statement)


READ_SQL = r"""
CREATE FUNCTION app.list_skill_catalog(p_org uuid,p_actor uuid) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE result jsonb;
BEGIN
  PERFORM app.assert_m3b_context(p_org,p_actor,'advisor');
  SELECT COALESCE(jsonb_agg(jsonb_build_object(
    'skill_key',d.skill_key,'definition_id',d.id,'owner_actor_id',d.owner_actor_id,
    'binding_kind',d.binding_kind,'latest_version',latest.semantic_version,
    'active_version',active.semantic_version,'activation_sequence',event.activation_sequence
  ) ORDER BY d.skill_key),'[]'::jsonb) INTO result
  FROM app.skill_definitions d
  LEFT JOIN LATERAL (
    SELECT v.semantic_version FROM app.skill_versions v
    WHERE v.organization_id=d.organization_id AND v.definition_id=d.id
    ORDER BY split_part(v.semantic_version,'.',1)::integer DESC,
             split_part(v.semantic_version,'.',2)::integer DESC,
             split_part(v.semantic_version,'.',3)::integer DESC LIMIT 1
  ) latest ON true
  LEFT JOIN LATERAL (
    SELECT e.activated_version_id,e.activation_sequence FROM app.skill_activation_events e
    WHERE e.organization_id=d.organization_id AND e.definition_id=d.id
    ORDER BY e.activation_sequence DESC LIMIT 1
  ) event ON true
  LEFT JOIN app.skill_versions active
    ON active.organization_id=d.organization_id AND active.definition_id=d.id
   AND active.id=event.activated_version_id
  WHERE d.organization_id=p_org;
  RETURN result;
END; $$;

CREATE FUNCTION app.get_skill_catalog_item(p_org uuid,p_actor uuid,p_skill_key text) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE definition app.skill_definitions%ROWTYPE; versions jsonb; events jsonb;
BEGIN
  PERFORM app.assert_m3b_context(p_org,p_actor,'advisor');
  SELECT * INTO definition FROM app.skill_definitions
   WHERE organization_id=p_org AND skill_key=p_skill_key FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='Skill unavailable'; END IF;
  SELECT COALESCE(jsonb_agg(jsonb_build_object(
    'version_id',v.id,'semantic_version',v.semantic_version,'binding_kind',v.binding_kind,
    'input_contract_id',v.input_contract_id,'input_schema_sha256',v.input_schema_sha256,
    'output_contract_id',v.output_contract_id,'output_schema_sha256',v.output_schema_sha256,
    'content_sha256',v.content_sha256,'tool_allowlist_sha256',v.tool_allowlist_sha256,
    'data_scope_sha256',v.data_scope_sha256,'side_effect_level',v.side_effect_level,
    'approval_policy',v.approval_policy,'policy_version',v.policy_version,
    'policy_sha256',v.policy_sha256,'evaluation_dataset_id',v.evaluation_dataset_id,
    'evaluation_dataset_version',v.evaluation_dataset_version,
    'evaluation_dataset_sha256',v.evaluation_dataset_sha256,
    'runtime_manifest_id',v.runtime_manifest_id,
    'runtime_manifest_version',v.runtime_manifest_version,
    'runtime_manifest_sha256',v.runtime_manifest_sha256,
    'runtime_binding_sha256',v.runtime_binding_sha256
  ) ORDER BY split_part(v.semantic_version,'.',1)::integer,
             split_part(v.semantic_version,'.',2)::integer,
             split_part(v.semantic_version,'.',3)::integer),'[]'::jsonb)
    INTO versions FROM app.skill_versions v
   WHERE v.organization_id=p_org AND v.definition_id=definition.id;
  SELECT COALESCE(jsonb_agg(jsonb_build_object(
    'event_id',e.id,'kind',e.event_kind,'activated_version_id',e.activated_version_id,
    'previous_version_id',e.previous_version_id,'activation_sequence',e.activation_sequence,
    'created_at',e.created_at
  ) ORDER BY e.activation_sequence),'[]'::jsonb)
    INTO events FROM app.skill_activation_events e
   WHERE e.organization_id=p_org AND e.definition_id=definition.id;
  RETURN jsonb_build_object(
    'skill_key',definition.skill_key,'definition_id',definition.id,
    'owner_actor_id',definition.owner_actor_id,'binding_kind',definition.binding_kind,
    'versions',versions,'activation_events',events
  );
END; $$;

CREATE FUNCTION app.load_skill_candidate_context(p_org uuid,p_actor uuid,p_candidate uuid) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE candidate app.skill_change_candidates%ROWTYPE; definition app.skill_definitions%ROWTYPE; proposed app.skill_versions%ROWTYPE; evaluation app.skill_evaluation_results%ROWTYPE;
BEGIN
  PERFORM app.assert_m3b_context(p_org,p_actor,'advisor');
  SELECT * INTO candidate FROM app.skill_change_candidates WHERE organization_id=p_org AND id=p_candidate;
  IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='Skill candidate unavailable'; END IF;
  SELECT * INTO definition FROM app.skill_definitions WHERE organization_id=p_org AND id=candidate.definition_id;
  IF definition.owner_actor_id<>p_actor THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='Skill candidate unavailable'; END IF;
  SELECT * INTO proposed FROM app.skill_versions WHERE organization_id=p_org AND id=candidate.proposed_version_id;
  SELECT * INTO evaluation FROM app.skill_evaluation_results WHERE organization_id=p_org AND candidate_id=candidate.id;
  RETURN jsonb_build_object(
    'candidate_id',candidate.id,'skill_key',definition.skill_key,'binding_kind',definition.binding_kind,
    'base_version_id',candidate.base_version_id,'proposed_version_id',candidate.proposed_version_id,
    'proposed_version',proposed.semantic_version,'manifest_projection',proposed.manifest_projection,
    'evaluation_id',evaluation.id,'evaluation_status',evaluation.status
  );
END; $$;

CREATE FUNCTION app.inspect_planning_skill(p_org uuid,p_actor uuid,p_case uuid) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE definition app.skill_definitions%ROWTYPE; event app.skill_activation_events%ROWTYPE; version app.skill_versions%ROWTYPE; evaluation app.skill_evaluation_results%ROWTYPE; selected_task app.agent_tasks%ROWTYPE; selected_execution app.agent_executions%ROWTYPE; task_found boolean := false; execution_found boolean := false; selected_adapter_id text; selected_adapter_version text; selected_pin_status text;
BEGIN
  PERFORM app.assert_m3b_context(p_org,p_actor,'advisor');
  IF NOT EXISTS (
    SELECT 1 FROM app.student_case_participants
    WHERE organization_id=p_org AND case_id=p_case AND actor_id=p_actor AND role='advisor'
  ) THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='planning Skill inspector unavailable'; END IF;
  SELECT * INTO definition FROM app.skill_definitions
   WHERE organization_id=p_org AND skill_key='study-destination-compare';
  IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='planning Skill inspector unavailable'; END IF;
  SELECT * INTO event FROM app.skill_activation_events
   WHERE organization_id=p_org AND definition_id=definition.id
   ORDER BY activation_sequence DESC LIMIT 1;
  IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV015', MESSAGE='active Skill version unavailable'; END IF;
  SELECT * INTO version FROM app.skill_versions
   WHERE organization_id=p_org AND definition_id=definition.id AND id=event.activated_version_id;
  IF NOT FOUND OR version.binding_kind<>'planning_runtime' OR version.runtime_binding_sha256 IS NULL THEN
    RAISE EXCEPTION USING ERRCODE='NV015', MESSAGE='active Skill version unavailable';
  END IF;
  SELECT * INTO evaluation FROM app.skill_evaluation_results
   WHERE organization_id=p_org AND definition_id=definition.id AND version_id=version.id
     AND status='passed'
   ORDER BY created_at DESC,id DESC LIMIT 1;
  IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV015', MESSAGE='active Skill evaluation unavailable'; END IF;
  SELECT * INTO selected_task FROM app.agent_tasks
   WHERE organization_id=p_org AND case_id=p_case
     AND operation IN ('generate_planning_run_v1','generate_governed_mixed_planning_run_v1')
   ORDER BY created_at DESC,id DESC LIMIT 1;
  task_found := FOUND;
  IF task_found THEN
    SELECT * INTO selected_execution FROM app.agent_executions
     WHERE organization_id=p_org AND task_id=selected_task.id
     ORDER BY attempt_no DESC,created_at DESC,id DESC LIMIT 1;
    execution_found := FOUND;
    IF selected_task.skill_definition_id IS NULL THEN
      selected_pin_status := 'legacy_unpinned';
      IF execution_found THEN
        selected_adapter_id := selected_execution.adapter_id;
        selected_adapter_version := selected_execution.adapter_version;
      END IF;
    ELSE
      IF NOT EXISTS (
        SELECT 1 FROM app.skill_versions pinned_version
        JOIN app.skill_activation_events pinned_event
          ON pinned_event.organization_id=pinned_version.organization_id
         AND pinned_event.definition_id=pinned_version.definition_id
         AND pinned_event.id=selected_task.skill_activation_event_id
         AND pinned_event.activated_version_id=pinned_version.id
         AND pinned_event.activation_sequence=selected_task.skill_activation_sequence
        WHERE pinned_version.organization_id=p_org
          AND pinned_version.definition_id=selected_task.skill_definition_id
          AND pinned_version.id=selected_task.skill_version_id
          AND pinned_version.runtime_binding_sha256=selected_task.runtime_binding_sha256
          AND pinned_version.binding_kind='planning_runtime'
      ) THEN RAISE EXCEPTION USING ERRCODE='NV022', MESSAGE='Skill runtime pin is invalid'; END IF;
      selected_pin_status := 'matched';
      IF execution_found THEN
        selected_adapter_id := selected_execution.adapter_id;
        selected_adapter_version := selected_execution.adapter_version;
      ELSE
        selected_adapter_id := CASE selected_task.operation
          WHEN 'generate_planning_run_v1' THEN 'deterministic_planning'
          WHEN 'generate_governed_mixed_planning_run_v1' THEN 'governed_mixed_planning'
        END;
        selected_adapter_version := CASE selected_task.operation
          WHEN 'generate_planning_run_v1' THEN 'm4a-v1'
          WHEN 'generate_governed_mixed_planning_run_v1' THEN 'dra-mixed-v1'
        END;
      END IF;
    END IF;
    IF selected_adapter_id IS NOT NULL AND (
      (selected_task.operation='generate_planning_run_v1'
       AND (selected_adapter_id,selected_adapter_version) IS DISTINCT FROM ('deterministic_planning','m4a-v1'))
      OR
      (selected_task.operation='generate_governed_mixed_planning_run_v1'
       AND (selected_adapter_id,selected_adapter_version) IS DISTINCT FROM ('governed_mixed_planning','dra-mixed-v1'))
    ) THEN RAISE EXCEPTION USING ERRCODE='NV022', MESSAGE='Skill runtime pin is invalid'; END IF;
  ELSE
    selected_pin_status := 'not_created';
  END IF;
  RETURN jsonb_build_object(
    'case_id',p_case,
    'operation',CASE WHEN task_found THEN selected_task.operation ELSE NULL END,
    'active_skill_key',definition.skill_key,'active_version',version.semantic_version,
    'activation_sequence',event.activation_sequence,
    'evaluator_id',evaluation.evaluator_id,'evaluator_version',evaluation.evaluator_version,
    'evaluation_dataset_id',evaluation.dataset_id,
    'evaluation_dataset_version',evaluation.dataset_version,
    'task_request_sha256_prefix',CASE WHEN task_found THEN substr(selected_task.request_sha256,1,12) ELSE NULL END,
    'version_content_sha256_prefix',substr(version.content_sha256,1,12),
    'runtime_binding_sha256_prefix',substr(version.runtime_binding_sha256,1,12),
    'adapter_id',selected_adapter_id,'adapter_version',selected_adapter_version,
    'pin_status',selected_pin_status
  );
END; $$;

CREATE FUNCTION app.load_agent_task_skill_pin(p_org uuid,p_task uuid,p_generation bigint) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE result jsonb;
BEGIN
  PERFORM app.assert_context(p_org);
  SELECT jsonb_build_object(
    'task_id',t.id,'operation',t.operation,'skill_key',d.skill_key,
    'semantic_version',v.semantic_version,'binding_kind',d.binding_kind,
    'skill_definition_id',e.skill_definition_id,'skill_version_id',e.skill_version_id,
    'skill_activation_event_id',e.skill_activation_event_id,
    'skill_activation_sequence',e.skill_activation_sequence,
    'runtime_binding_sha256',e.runtime_binding_sha256,
    'runtime_manifest_id',v.runtime_manifest_id,
    'runtime_manifest_version',v.runtime_manifest_version,
    'runtime_manifest_sha256',v.runtime_manifest_sha256,
    'manifest_projection',v.manifest_projection,
    'claimed_adapter_id',e.adapter_id,'claimed_adapter_version',e.adapter_version
  ) INTO result
  FROM app.agent_tasks t
  JOIN app.agent_executions e
    ON e.organization_id=t.organization_id AND e.task_id=t.id AND e.lease_generation=p_generation
  JOIN app.skill_definitions d
    ON d.organization_id=t.organization_id AND d.id=t.skill_definition_id
  JOIN app.skill_versions v
    ON v.organization_id=t.organization_id AND v.definition_id=t.skill_definition_id
   AND v.id=t.skill_version_id AND v.runtime_binding_sha256=t.runtime_binding_sha256
  JOIN app.skill_activation_events a
    ON a.organization_id=t.organization_id AND a.definition_id=t.skill_definition_id
   AND a.id=t.skill_activation_event_id AND a.activated_version_id=t.skill_version_id
   AND a.activation_sequence=t.skill_activation_sequence
  WHERE t.organization_id=p_org AND t.id=p_task
    AND t.lease_generation=p_generation AND t.state='leased'
    AND e.status='leased'
    AND e.skill_definition_id=t.skill_definition_id
    AND e.skill_version_id=t.skill_version_id
    AND e.skill_activation_event_id=t.skill_activation_event_id
    AND e.skill_activation_sequence=t.skill_activation_sequence
    AND e.runtime_binding_sha256=t.runtime_binding_sha256;
  IF result IS NULL THEN RAISE EXCEPTION USING ERRCODE='NV022', MESSAGE='Skill runtime pin is invalid'; END IF;
  RETURN result;
END; $$;

CREATE FUNCTION app.load_persisted_synthetic_planning_snapshot(p_org uuid,p_case uuid,p_revision integer,p_pack uuid,p_pack_version integer,p_policy text) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE selected_case app.student_cases%ROWTYPE; selected_revision app.student_case_revisions%ROWTYPE; selected_pack app.source_packs%ROWTYPE; countries text[]; canonical_countries text[];
BEGIN
  PERFORM app.assert_context(p_org);
  IF p_revision<=0 OR p_pack_version<>1 OR p_pack<>'50000000-0000-0000-0000-000000000001'::uuid OR p_policy<>'m3a-policy-v1' THEN
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

MUTATION_SQL = r"""
CREATE FUNCTION app.create_skill_change_candidate(p_org uuid,p_actor uuid,p_skill_key text,p_candidate uuid,p_proposed_version text,p_provenance text,p_reason text,p_reference text,p_manifest jsonb,p_request_hash text,p_key_hash text) RETURNS TABLE(candidate_id uuid,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE prior app.idempotency_records%ROWTYPE; definition app.skill_definitions%ROWTYPE; proposed app.skill_versions%ROWTYPE; base_id uuid; selected app.skill_change_candidates%ROWTYPE;
BEGIN
  PERFORM app.assert_m3b_context(p_org,p_actor,'advisor');
  SELECT * INTO prior FROM app.idempotency_records WHERE organization_id=p_org AND actor_id=p_actor AND operation='skill_candidate_create' AND key_sha256=p_key_hash;
  IF FOUND THEN
    IF prior.request_sha256<>p_request_hash THEN RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='idempotency request mismatch'; END IF;
    SELECT * INTO selected FROM app.skill_change_candidates WHERE organization_id=p_org AND id=prior.response_id;
    RETURN QUERY SELECT selected.id,true; RETURN;
  END IF;
  IF p_request_hash !~ '^[0-9a-f]{64}$' OR p_key_hash !~ '^[0-9a-f]{64}$' OR jsonb_typeof(p_manifest)<>'object' THEN
    RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid Skill candidate request';
  END IF;
  SELECT * INTO definition FROM app.skill_definitions
   WHERE organization_id=p_org AND skill_key=p_skill_key FOR SHARE;
  IF NOT FOUND OR definition.owner_actor_id<>p_actor THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='Skill unavailable'; END IF;
  SELECT * INTO proposed FROM app.skill_versions
   WHERE organization_id=p_org AND definition_id=definition.id
     AND semantic_version=p_proposed_version AND NOT is_seed;
  IF NOT FOUND OR proposed.manifest_projection<>p_manifest THEN RAISE EXCEPTION USING ERRCODE='NV015', MESSAGE='Skill version unavailable'; END IF;
  IF definition.binding_kind='planning_runtime' THEN
    SELECT activated_version_id INTO base_id FROM app.skill_activation_events
     WHERE organization_id=p_org AND definition_id=definition.id
     ORDER BY activation_sequence DESC LIMIT 1;
  ELSE
    SELECT id INTO base_id FROM app.skill_versions
     WHERE organization_id=p_org AND definition_id=definition.id AND id<>proposed.id
     ORDER BY split_part(semantic_version,'.',1)::integer DESC,
              split_part(semantic_version,'.',2)::integer DESC,
              split_part(semantic_version,'.',3)::integer DESC LIMIT 1;
  END IF;
  IF base_id IS NULL OR base_id=proposed.id THEN RAISE EXCEPTION USING ERRCODE='NV016', MESSAGE='Skill candidate base is stale'; END IF;
  IF EXISTS (SELECT 1 FROM app.skill_change_candidates WHERE organization_id=p_org AND definition_id=definition.id AND proposed_version_id=proposed.id) THEN
    RAISE EXCEPTION USING ERRCODE='NV017', MESSAGE='Skill candidate is terminal';
  END IF;
  INSERT INTO app.skill_change_candidates(
    organization_id,id,definition_id,base_version_id,proposed_version_id,provenance,reason,reference,
    created_by_actor_id,request_sha256
  ) VALUES(p_org,p_candidate,definition.id,base_id,proposed.id,p_provenance,p_reason,p_reference,p_actor,p_request_hash);
  INSERT INTO app.idempotency_records VALUES(p_org,p_actor,'skill_candidate_create',p_key_hash,p_request_hash,'skill_change_candidate',p_candidate,clock_timestamp());
  RETURN QUERY SELECT p_candidate,false;
END; $$;

CREATE FUNCTION app.record_skill_candidate_evaluation(p_org uuid,p_actor uuid,p_candidate uuid,p_evaluation uuid,p_result jsonb,p_request_hash text,p_key_hash text) RETURNS TABLE(evaluation_id uuid,status text,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE prior app.idempotency_records%ROWTYPE; candidate app.skill_change_candidates%ROWTYPE; definition app.skill_definitions%ROWTYPE; version app.skill_versions%ROWTYPE; selected app.skill_evaluation_results%ROWTYPE;
BEGIN
  PERFORM app.assert_m3b_context(p_org,p_actor,'advisor');
  SELECT * INTO prior FROM app.idempotency_records WHERE organization_id=p_org AND actor_id=p_actor AND operation='skill_candidate_evaluate' AND key_sha256=p_key_hash;
  IF FOUND THEN
    IF prior.request_sha256<>p_request_hash THEN RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='idempotency request mismatch'; END IF;
    SELECT * INTO selected FROM app.skill_evaluation_results WHERE organization_id=p_org AND id=prior.response_id;
    RETURN QUERY SELECT selected.id,selected.status,true; RETURN;
  END IF;
  SELECT * INTO candidate FROM app.skill_change_candidates WHERE organization_id=p_org AND id=p_candidate;
  IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='Skill candidate unavailable'; END IF;
  SELECT * INTO definition FROM app.skill_definitions WHERE organization_id=p_org AND id=candidate.definition_id;
  IF definition.owner_actor_id<>p_actor THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='Skill candidate unavailable'; END IF;
  IF EXISTS (SELECT 1 FROM app.skill_evaluation_results WHERE organization_id=p_org AND candidate_id=p_candidate) THEN
    RAISE EXCEPTION USING ERRCODE='NV017', MESSAGE='Skill candidate is terminal';
  END IF;
  SELECT * INTO version FROM app.skill_versions WHERE organization_id=p_org AND id=candidate.proposed_version_id;
  IF p_result IS DISTINCT FROM version.expected_evaluation_projection THEN
    RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid Skill evaluation result';
  END IF;
  INSERT INTO app.skill_evaluation_results(
    organization_id,id,definition_id,candidate_id,version_id,evaluator_id,evaluator_version,
    dataset_id,dataset_version,dataset_sha256,assertion_projection,output_sha256,status,
    failed_assertion_ids,request_sha256,is_seed
  ) VALUES(
    p_org,p_evaluation,candidate.definition_id,candidate.id,candidate.proposed_version_id,
    p_result->>'evaluator_id',p_result->>'evaluator_version',p_result->>'dataset_id',
    p_result->>'dataset_version',p_result->>'dataset_sha256',p_result->'assertions',
    p_result->>'output_sha256',p_result->>'status',p_result->'failed_assertion_ids',p_request_hash,false
  );
  INSERT INTO app.idempotency_records VALUES(p_org,p_actor,'skill_candidate_evaluate',p_key_hash,p_request_hash,'skill_evaluation_result',p_evaluation,clock_timestamp());
  RETURN QUERY SELECT p_evaluation,p_result->>'status',false;
END; $$;

CREATE FUNCTION app.promote_skill_change_candidate(p_org uuid,p_actor uuid,p_candidate uuid,p_event uuid,p_expected_active_version text,p_expected_sequence bigint,p_reason text,p_manifest jsonb,p_request_hash text,p_key_hash text) RETURNS TABLE(activation_event_id uuid,activation_sequence bigint,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE prior app.idempotency_records%ROWTYPE; candidate app.skill_change_candidates%ROWTYPE; definition app.skill_definitions%ROWTYPE; base app.skill_versions%ROWTYPE; proposed app.skill_versions%ROWTYPE; evaluation app.skill_evaluation_results%ROWTYPE; active_event app.skill_activation_events%ROWTYPE; selected app.skill_activation_events%ROWTYPE; next_sequence bigint;
BEGIN
  PERFORM app.assert_m3b_context(p_org,p_actor,'advisor');
  SELECT * INTO prior FROM app.idempotency_records WHERE organization_id=p_org AND actor_id=p_actor AND operation='skill_candidate_promote' AND key_sha256=p_key_hash;
  IF FOUND THEN
    IF prior.request_sha256<>p_request_hash THEN RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='idempotency request mismatch'; END IF;
    SELECT * INTO selected FROM app.skill_activation_events WHERE organization_id=p_org AND id=prior.response_id;
    RETURN QUERY SELECT selected.id,selected.activation_sequence,true; RETURN;
  END IF;
  SELECT * INTO candidate FROM app.skill_change_candidates WHERE organization_id=p_org AND id=p_candidate;
  IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='Skill candidate unavailable'; END IF;
  SELECT * INTO definition FROM app.skill_definitions
   WHERE organization_id=p_org AND id=candidate.definition_id FOR UPDATE;
  IF definition.owner_actor_id<>p_actor THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='Skill candidate unavailable'; END IF;
  IF definition.binding_kind<>'planning_runtime' THEN RAISE EXCEPTION USING ERRCODE='NV015', MESSAGE='Skill version unavailable'; END IF;
  SELECT * INTO active_event FROM app.skill_activation_events
   WHERE organization_id=p_org AND definition_id=definition.id ORDER BY activation_sequence DESC LIMIT 1;
  SELECT * INTO base FROM app.skill_versions WHERE organization_id=p_org AND id=active_event.activated_version_id;
  IF NOT FOUND OR base.semantic_version<>p_expected_active_version OR active_event.activation_sequence<>p_expected_sequence OR candidate.base_version_id<>base.id THEN
    RAISE EXCEPTION USING ERRCODE='NV019', MESSAGE='Skill activation is stale';
  END IF;
  SELECT * INTO proposed FROM app.skill_versions WHERE organization_id=p_org AND id=candidate.proposed_version_id;
  IF proposed.manifest_projection<>p_manifest THEN RAISE EXCEPTION USING ERRCODE='NV015', MESSAGE='Skill version unavailable'; END IF;
  SELECT * INTO evaluation FROM app.skill_evaluation_results WHERE organization_id=p_org AND candidate_id=candidate.id;
  IF NOT FOUND OR evaluation.status<>'passed' THEN RAISE EXCEPTION USING ERRCODE='NV018', MESSAGE='Skill evaluation failed'; END IF;
  IF (split_part(proposed.semantic_version,'.',1)::integer,split_part(proposed.semantic_version,'.',2)::integer,split_part(proposed.semantic_version,'.',3)::integer)
       <= (split_part(base.semantic_version,'.',1)::integer,split_part(base.semantic_version,'.',2)::integer,split_part(base.semantic_version,'.',3)::integer) THEN
    RAISE EXCEPTION USING ERRCODE='NV016', MESSAGE='Skill candidate is stale';
  END IF;
  IF NOT (base.tool_ids @> proposed.tool_ids) OR NOT (base.data_scopes @> proposed.data_scopes)
     OR base.executor_id<>proposed.executor_id OR base.executor_version<>proposed.executor_version
     OR base.side_effect_level<>proposed.side_effect_level OR base.approval_policy<>proposed.approval_policy THEN
    RAISE EXCEPTION USING ERRCODE='NV020', MESSAGE='Skill scope expansion is forbidden';
  END IF;
  next_sequence := active_event.activation_sequence+1;
  INSERT INTO app.skill_activation_events(
    organization_id,id,definition_id,activated_version_id,previous_version_id,candidate_id,evaluation_id,
    event_kind,owner_actor_id,reason,request_sha256,activation_sequence
  ) VALUES(p_org,p_event,definition.id,proposed.id,base.id,candidate.id,evaluation.id,'promote',p_actor,p_reason,p_request_hash,next_sequence);
  INSERT INTO app.idempotency_records VALUES(p_org,p_actor,'skill_candidate_promote',p_key_hash,p_request_hash,'skill_activation_event',p_event,clock_timestamp());
  RETURN QUERY SELECT p_event,next_sequence,false;
END; $$;

CREATE FUNCTION app.rollback_skill_activation(p_org uuid,p_actor uuid,p_skill_key text,p_event uuid,p_target_version text,p_expected_active_version text,p_expected_sequence bigint,p_reason text,p_manifest jsonb,p_request_hash text,p_key_hash text) RETURNS TABLE(activation_event_id uuid,activation_sequence bigint,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE prior app.idempotency_records%ROWTYPE; definition app.skill_definitions%ROWTYPE; active_event app.skill_activation_events%ROWTYPE; active_version app.skill_versions%ROWTYPE; target app.skill_versions%ROWTYPE; selected app.skill_activation_events%ROWTYPE; next_sequence bigint;
BEGIN
  PERFORM app.assert_m3b_context(p_org,p_actor,'advisor');
  SELECT * INTO prior FROM app.idempotency_records WHERE organization_id=p_org AND actor_id=p_actor AND operation='skill_activation_rollback' AND key_sha256=p_key_hash;
  IF FOUND THEN
    IF prior.request_sha256<>p_request_hash THEN RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='idempotency request mismatch'; END IF;
    SELECT * INTO selected FROM app.skill_activation_events WHERE organization_id=p_org AND id=prior.response_id;
    RETURN QUERY SELECT selected.id,selected.activation_sequence,true; RETURN;
  END IF;
  SELECT * INTO definition FROM app.skill_definitions
   WHERE organization_id=p_org AND skill_key=p_skill_key FOR UPDATE;
  IF NOT FOUND OR definition.owner_actor_id<>p_actor OR definition.binding_kind<>'planning_runtime' THEN
    RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='Skill unavailable';
  END IF;
  SELECT * INTO active_event FROM app.skill_activation_events
   WHERE organization_id=p_org AND definition_id=definition.id ORDER BY activation_sequence DESC LIMIT 1;
  SELECT * INTO active_version FROM app.skill_versions WHERE organization_id=p_org AND id=active_event.activated_version_id;
  IF active_version.semantic_version<>p_expected_active_version OR active_event.activation_sequence<>p_expected_sequence THEN
    RAISE EXCEPTION USING ERRCODE='NV019', MESSAGE='Skill activation is stale';
  END IF;
  SELECT * INTO target FROM app.skill_versions
   WHERE organization_id=p_org AND definition_id=definition.id AND semantic_version=p_target_version;
  IF NOT FOUND OR target.manifest_projection<>p_manifest OR target.id=active_version.id
     OR NOT EXISTS (
       SELECT 1 FROM app.skill_activation_events e
       WHERE e.organization_id=p_org AND e.definition_id=definition.id AND e.activated_version_id=target.id
     ) THEN RAISE EXCEPTION USING ERRCODE='NV021', MESSAGE='Skill rollback target is unsupported'; END IF;
  next_sequence := active_event.activation_sequence+1;
  INSERT INTO app.skill_activation_events(
    organization_id,id,definition_id,activated_version_id,previous_version_id,event_kind,
    owner_actor_id,reason,request_sha256,activation_sequence
  ) VALUES(p_org,p_event,definition.id,target.id,active_version.id,'rollback',p_actor,p_reason,p_request_hash,next_sequence);
  INSERT INTO app.idempotency_records VALUES(p_org,p_actor,'skill_activation_rollback',p_key_hash,p_request_hash,'skill_activation_event',p_event,clock_timestamp());
  RETURN QUERY SELECT p_event,next_sequence,false;
END; $$;
"""

CANONICAL_DEMO_SKILL_SEED = r"""{"entries":[{"definition_id":"81000000-0000-0000-0000-000000000001","evaluation":{"assertions":[{"assertion_id":"student-profile-intake.cross-role-fact-rejected","observed_sha256":"3a60061947d350e063c1e5f3255de367587628dcd0a355766ec128b5b36c4d14","passed":true},{"assertion_id":"student-profile-intake.unconfirmed-remains-unconfirmed","observed_sha256":"e08ff4aec917544328b4ca2be4a23ce025a53e3083cb259f6aa696c0c5b616c1","passed":true},{"assertion_id":"student-profile-intake.unsafe-value-rejected","observed_sha256":"767b636f0f2b4aa07ff741ca1cbdd022b4422d1cdc53174eb9bb4c4f8e39dde7","passed":true}],"dataset_id":"night-voyager.student-profile-intake.eval","dataset_sha256":"7e21b3f465c94566fe123aa37ba677dc057dfbc19aacbf69ba4fb6d4554c9e1d","dataset_version":"1.0.0","evaluator_id":"night-voyager.deterministic-skill-evaluator","evaluator_version":"v1","failed_assertion_ids":[],"output_sha256":"5cd49da59fd1a4cac81903be2ffc68126e9613f8cb1cc93c61166c5d53520bf7","schema_version":1,"skill_key":"student-profile-intake","status":"passed","version":"1.0.0"},"evaluation_id":"83000000-0000-0000-0000-000000000001","is_seed":true,"manifest":{"approval_policy":"advisor_review_required","binding_kind":"catalog_only","content_sha256":"58227e5a092ebd6d25cdc3b69b13289cfca5e82fd81e4acabea860f503214298","data_scope_sha256":"26c3b176fb2a4b280d827ff6b4b6b49cf192d99f9220e451df7700a44d5d721a","data_scopes":["case_revision"],"evaluation_dataset_id":"night-voyager.student-profile-intake.eval","evaluation_dataset_sha256":"7e21b3f465c94566fe123aa37ba677dc057dfbc19aacbf69ba4fb6d4554c9e1d","evaluation_dataset_version":"1.0.0","input_contract_id":"night-voyager.profile-fact-proposal.v1","input_schema_sha256":"dd0bc42067b6a5a286325a0a82c487678c47300776df87cd074cf6052a8b4cd2","output_contract_id":"night-voyager.confirmed-fact.v1","output_schema_sha256":"289069df2d694b46458b34c499b9aabd910e5a1e0e1e973a0af6c86675d90e1a","policy_sha256":"deda90e6eaa9441f4c90b8dced5f8c1c314ecbec92074585bd631e5b183aa8ad","policy_version":"collaboration-fact-policy-v1","schema_version":1,"side_effect_level":"none","skill_key":"student-profile-intake","tool_allowlist_sha256":"458984997d21578af8abb66ba633ca4b697c2b053aeaef7a0405e2e2dec511b2","tool_ids":["collaboration_policy"],"version":"1.0.0"},"request_sha256":"69d13201acecf6404eb08d695f9fd3fc9175a2cfdd3d1a98bfdbb67216461790","version_id":"82000000-0000-0000-0000-000000000001"},{"activation_event_id":"84000000-0000-0000-0000-000000000001","definition_id":"81000000-0000-0000-0000-000000000002","evaluation":{"assertions":[{"assertion_id":"study-destination-compare.australia-conditional","observed_sha256":"6ef6a247b582ca5a927d354a65b5e2a147239987e53decf44371c894bbb1778f","passed":true},{"assertion_id":"study-destination-compare.baseline-hash-drift-failed","observed_sha256":"858deb262632750672bc90012ec863bf365a90144b3e36f19d6289a49f143607","passed":true},{"assertion_id":"study-destination-compare.budget-refusal-blocked","observed_sha256":"79ed3e370d74e2ad60877d9cea2b6ab6d90200dbac4f964e463e0959649ffb2f","passed":true},{"assertion_id":"study-destination-compare.malaysia-blocked","observed_sha256":"7ac04f1324f999fb4843f90aa78025667e49f89c59166b3705377f888bff8b4c","passed":true}],"dataset_id":"night-voyager.study-destination-compare.eval","dataset_sha256":"820e6730d5bf5a01edb6dd83273fa6b147dd2d284a7b397dcd783f874b81fd54","dataset_version":"1.0.0","evaluator_id":"night-voyager.deterministic-skill-evaluator","evaluator_version":"v1","failed_assertion_ids":[],"output_sha256":"648c11216bb16bd89de218b1bf52a66eb977de4200d27b68d951c66f16200115","schema_version":1,"skill_key":"study-destination-compare","status":"passed","version":"1.0.0"},"evaluation_id":"83000000-0000-0000-0000-000000000002","is_seed":true,"manifest":{"approval_policy":"advisor_review_required","binding_kind":"planning_runtime","content_sha256":"db3c04cc7a5826e9a68c671078e91fc8a4f9bf98f75c3be9af6c9af3a03c8444","data_scope_sha256":"9a0abf2a4dce893e29bb08ff3dcdd4fc580aee8134971fde76883488a18ca583","data_scopes":["accepted_evidence","case_revision"],"evaluation_dataset_id":"night-voyager.study-destination-compare.eval","evaluation_dataset_sha256":"820e6730d5bf5a01edb6dd83273fa6b147dd2d284a7b397dcd783f874b81fd54","evaluation_dataset_version":"1.0.0","executor_id":"planning_adapter_router","executor_version":"v1","input_contract_id":"night-voyager.planning-input.v1","input_schema_sha256":"0c3a8fc16ec800e79f78ae9e14622e7cdd89d2d9751fc655b12b356891ee9a0d","operation_bindings":[{"adapter_id":"deterministic_planning","adapter_version":"m4a-v1","operation":"generate_planning_run_v1"},{"adapter_id":"governed_mixed_planning","adapter_version":"dra-mixed-v1","operation":"generate_governed_mixed_planning_run_v1"}],"output_contract_id":"night-voyager.planning-result.v1","output_schema_sha256":"2e8f5dbdfd1f213ef4ca085f16b59162ec9f9ef8d58898bdc98487ddf3956135","policy_sha256":"4c1ad25a87b3127e24d7d53de7700633ce5a2b9d4af4a3547e2cf360affd4dbc","policy_version":"m3a-policy-v1","runtime_binding_sha256":"cd897b22d034c7aa1c841a3a5d67b70367a8556009cc665b4a27fa16e8170a29","schema_version":1,"side_effect_level":"bounded_product_write","skill_key":"study-destination-compare","tool_allowlist_sha256":"b77dc71a5e343a2cca9422937d3731c0260a2b97ee41c02aff60cc48345ac2b5","tool_ids":["planning_policy"],"version":"1.0.0"},"request_sha256":"c87908e87e74460dc002f48b8d1f79b99abfd8a9f0556ff765f55501b3d50d1f","version_id":"82000000-0000-0000-0000-000000000002"},{"definition_id":"81000000-0000-0000-0000-000000000003","evaluation":{"assertions":[{"assertion_id":"evidence-research.fallback-remains-untrusted","observed_sha256":"47bbda6ae3fbb948edf5264608e544c0b7f1ecd5e06ebf6fd2d40fc5fa21e386","passed":true},{"assertion_id":"evidence-research.terminal-invalid-not-promotable","observed_sha256":"c2dc6e9ce76280396ddd7c552ed44711deef802780accfab4f1933fd25205093","passed":true}],"dataset_id":"night-voyager.evidence-research.eval","dataset_sha256":"6fbcf98e66d33c6366b34e69220758e4ab50f09d45dc0db43bc22cdbdc1fb703","dataset_version":"1.0.0","evaluator_id":"night-voyager.deterministic-skill-evaluator","evaluator_version":"v1","failed_assertion_ids":[],"output_sha256":"2dfee7c078610d45fa090dccfacd143d637a0ec08d90f83d64eedfbe1c8e608b","schema_version":1,"skill_key":"evidence-research","status":"passed","version":"1.0.0"},"evaluation_id":"83000000-0000-0000-0000-000000000003","is_seed":true,"manifest":{"approval_policy":"advisor_review_required","binding_kind":"catalog_only","content_sha256":"dc9598c350c474864f5c202448dc2c007c0044bc99a59abb3ea8c4227f27b301","data_scope_sha256":"e8f4be5a2c0fae43ece3277ea783b7a01f2581f2dee1a83056b50e5dba2a3d72","data_scopes":["case_revision","source_manifest"],"evaluation_dataset_id":"night-voyager.evidence-research.eval","evaluation_dataset_sha256":"6fbcf98e66d33c6366b34e69220758e4ab50f09d45dc0db43bc22cdbdc1fb703","evaluation_dataset_version":"1.0.0","input_contract_id":"night-voyager.dra-readonly-request.v1","input_schema_sha256":"6b7ed3fc0d08833b22d84ffad1c4381a60f105bd0131c0b3fe4e228b1a10d71b","output_contract_id":"night-voyager.dra-candidate.v1","output_schema_sha256":"650d48138331a088696efa6720e456aed84e973d75ba831d09374e3f6493c883","policy_sha256":"9c060bf559e55d52b515faf4ffa369200bd5ea8b00c16d51005d70a282c0615b","policy_version":"dra-evidence-candidate-policy-v1","schema_version":1,"side_effect_level":"none","skill_key":"evidence-research","tool_allowlist_sha256":"ed7f870598c150ac0cb9139a5bca85db51676c9fa000ca127c0d3f82f5d818dd","tool_ids":["dra_readonly"],"version":"1.0.0"},"request_sha256":"4f576a9ad39011527d808f43d78d010661bc40bbd6392ccb3edf4481f4f00de4","version_id":"82000000-0000-0000-0000-000000000003"},{"definition_id":"81000000-0000-0000-0000-000000000004","evaluation":{"assertions":[{"assertion_id":"document-evidence-retrieval.active-no-match-not-evidence","observed_sha256":"7d1cc8108b0273cc3d48096bfbcb88852405cd28d944d1e581c383d6d742b12c","passed":true},{"assertion_id":"document-evidence-retrieval.no-match-not-sufficient","observed_sha256":"95b8de76812c625889a4bd6516af2222f7a02354f3897dd6e5ddca4fe038c124","passed":true}],"dataset_id":"night-voyager.document-evidence-retrieval.eval","dataset_sha256":"2a562e9383f08b0df16e8aa206ec22042c8cac5bbd523290bec564db400f867d","dataset_version":"1.0.0","evaluator_id":"night-voyager.deterministic-skill-evaluator","evaluator_version":"v1","failed_assertion_ids":[],"output_sha256":"4eb45a6415d180d3f132f9d20c573aeb0ce36e4b0586bd807613a5c07d524d22","schema_version":1,"skill_key":"document-evidence-retrieval","status":"passed","version":"1.0.0"},"evaluation_id":"83000000-0000-0000-0000-000000000004","is_seed":true,"manifest":{"approval_policy":"advisor_review_required","binding_kind":"catalog_only","content_sha256":"ebf3de87ecfcdf663ae9db520e3386a336f5f4ca4475f6d9fd71940c52750d19","data_scope_sha256":"bf3f623c66087281b021e01de18a1e9e886999865aa61aa1402589c96af5996f","data_scopes":["source_manifest"],"evaluation_dataset_id":"night-voyager.document-evidence-retrieval.eval","evaluation_dataset_sha256":"2a562e9383f08b0df16e8aa206ec22042c8cac5bbd523290bec564db400f867d","evaluation_dataset_version":"1.0.0","input_contract_id":"night-voyager.evidence-query.v1","input_schema_sha256":"bc60758e4a710009e574b4b885ab7171e2abd9254738727e9d7260dc26b0295a","output_contract_id":"night-voyager.candidate-evidence.v1","output_schema_sha256":"f4ee24b6e54470731560dfa9aaf4055ab3f4568e8dd5720eb44cb9f99666ddb1","policy_sha256":"a70105500b142360159e6ac7259c0c2b344d0db0f1ab2e146063efb24292dd32","policy_version":"mke-candidate-policy-v1","schema_version":1,"side_effect_level":"none","skill_key":"document-evidence-retrieval","tool_allowlist_sha256":"62c6422aac9c60293234bfde7786354e3c8c89a0492af706a048754f501c005a","tool_ids":["mke_readonly"],"version":"1.0.0"},"request_sha256":"6f1b01dca32ec5b788e412db713bc34288f37a1920df5e5dcd2dd64d5f34755a","version_id":"82000000-0000-0000-0000-000000000004"},{"definition_id":"81000000-0000-0000-0000-000000000005","evaluation":{"assertions":[{"assertion_id":"family-decision-brief.blocked-route-ineligible","observed_sha256":"d82b80927f6120a063c7a699ce4dfb8d469992479756e5554af7ee6167632353","passed":true},{"assertion_id":"family-decision-brief.unreviewed-run-rejected","observed_sha256":"6b891bc56d6aeb8940859d4945449ad18e6a6dc208f1f9dbf0f13fd91a7d7a20","passed":true}],"dataset_id":"night-voyager.family-decision-brief.eval","dataset_sha256":"c02721844a57bd3c056ac1bed0e751dede13f86dcba3781cf42133fe315a6282","dataset_version":"1.0.0","evaluator_id":"night-voyager.deterministic-skill-evaluator","evaluator_version":"v1","failed_assertion_ids":[],"output_sha256":"f7bee5a60553ab7aa292aa9748e28908bcbedcdbe2034b6f34819c35dd21bcf7","schema_version":1,"skill_key":"family-decision-brief","status":"passed","version":"1.0.0"},"evaluation_id":"83000000-0000-0000-0000-000000000005","is_seed":true,"manifest":{"approval_policy":"advisor_review_required","binding_kind":"catalog_only","content_sha256":"eef183ea6cf1ca1f11ceed5ceac11063c3a686971755ccde1f8b3113e34bc9d5","data_scope_sha256":"a4c08a3bb18c91d37d009260b4f5b72c9515994ad9a36dfc65b8e447f7df9d6f","data_scopes":["accepted_evidence","advisor_review","planning_run"],"evaluation_dataset_id":"night-voyager.family-decision-brief.eval","evaluation_dataset_sha256":"c02721844a57bd3c056ac1bed0e751dede13f86dcba3781cf42133fe315a6282","evaluation_dataset_version":"1.0.0","input_contract_id":"night-voyager.planning-result.v1","input_schema_sha256":"2e8f5dbdfd1f213ef4ca085f16b59162ec9f9ef8d58898bdc98487ddf3956135","output_contract_id":"night-voyager.decision-brief.v1","output_schema_sha256":"9d81741c99694bdc9453b2cb4c76ead02d7cda1a19118f0c04a117d9919f1b00","policy_sha256":"895a9e236bbc03a7af0634f4b24e0b693f24ef1f72c0a3ed0b66611e50997c31","policy_version":"decision-brief-policy-v1","schema_version":1,"side_effect_level":"bounded_product_write","skill_key":"family-decision-brief","tool_allowlist_sha256":"e15ebab2c0f681a449c59d70df576e056a68811552bb9578feb3a5f3b100bf04","tool_ids":["decision_policy"],"version":"1.0.0"},"request_sha256":"e810a4555f840427a966a9939061219c15358fd2354d689f8b3daaabdf7455d3","version_id":"82000000-0000-0000-0000-000000000005"},{"definition_id":"81000000-0000-0000-0000-000000000006","evaluation":{"assertions":[{"assertion_id":"application-timeline-guard.dates-deterministic","observed_sha256":"d4a663aeaba441b3d5613b8d7423a1ec2d2f732917e6debac2c6ba40d3df55d1","passed":true},{"assertion_id":"application-timeline-guard.no-decision-no-timeline","observed_sha256":"72b94cf8c22c06f023c800028890b0ba2fd107e26a41b5803a5d9d2fd9132eeb","passed":true}],"dataset_id":"night-voyager.application-timeline-guard.eval","dataset_sha256":"5082ef71a8e48873d4fc712d1d83cecc3d5d980cff0b1e8f7ea50c6afb442d59","dataset_version":"1.0.0","evaluator_id":"night-voyager.deterministic-skill-evaluator","evaluator_version":"v1","failed_assertion_ids":[],"output_sha256":"6197a698b8f4b1f0aa3b24237f8ac9161357d11bf40e9f44b594cd453fa22821","schema_version":1,"skill_key":"application-timeline-guard","status":"passed","version":"1.0.0"},"evaluation_id":"83000000-0000-0000-0000-000000000006","is_seed":true,"manifest":{"approval_policy":"family_decision_required","binding_kind":"catalog_only","content_sha256":"38a96b312bd9533a62b455b18c88c20f13a262ac714cded9c6db93e94fcaabd9","data_scope_sha256":"139ec4e7de759bf0ffb575e04f971c745d137d9c919fc91d71c6d0912382c2c2","data_scopes":["family_decision"],"evaluation_dataset_id":"night-voyager.application-timeline-guard.eval","evaluation_dataset_sha256":"5082ef71a8e48873d4fc712d1d83cecc3d5d980cff0b1e8f7ea50c6afb442d59","evaluation_dataset_version":"1.0.0","input_contract_id":"night-voyager.family-decision.v1","input_schema_sha256":"fc5251a81c49fd63e38c417f4d5a1f4e8b1dbf7aea20c2fcf92daa8d180f4f6f","output_contract_id":"night-voyager.timeline-plan.v1","output_schema_sha256":"ab02b68fc61106b36048a15ba96723efff20256e62a1d16e30c69c522f87d3ae","policy_sha256":"96b01540b4aa8ad365d63a32984c151693d60d6df29a8daf755d3ea45d8a2ab6","policy_version":"timeline-policy-v1","schema_version":1,"side_effect_level":"bounded_product_write","skill_key":"application-timeline-guard","tool_allowlist_sha256":"bc764295e02720f3ac130dd7c6141f8253261bcd0a0917b4a10c1708b650a508","tool_ids":["timeline_policy"],"version":"1.0.0"},"request_sha256":"7d1037eb6118e54862b2d8818cc52934e463b3f01bdeb349e0fdb4d5ee4ec4a8","version_id":"82000000-0000-0000-0000-000000000006"}],"evaluation_manifest_id":"night-voyager.skill-eval-manifest","evaluation_manifest_sha256":"280d68971e864fc5925cf0daafa489e3b274fe7263a0157afbaeb8aabcb7a393","evaluation_manifest_version":"1.0.0","runtime_manifest_id":"night-voyager.skill-runtime-manifest","runtime_manifest_sha256":"5e25b89af19a5bff6323e762c9986a7beec93d3e61a55cef18ea1cfc6e2e1e1f","runtime_manifest_version":"1.0.0","schema_version":1}"""

CANONICAL_DEMO_SKILL_SEED_B64 = base64.b64encode(
    CANONICAL_DEMO_SKILL_SEED.encode()
).decode("ascii")

SEED_SQL_TEMPLATE = r"""
CREATE FUNCTION app.seed_demo_skill_registry(p_org uuid,p_owner uuid,p_seed jsonb) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE canonical_seed jsonb := convert_from(decode('__CANONICAL_DEMO_SKILL_SEED_B64__','base64'),'UTF8')::jsonb; item jsonb; manifest jsonb; evaluation jsonb; definition app.skill_definitions%ROWTYPE; version app.skill_versions%ROWTYPE; evaluation_row app.skill_evaluation_results%ROWTYPE;
BEGIN
  IF p_seed IS DISTINCT FROM canonical_seed THEN
    RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid Skill seed projection';
  END IF;
  PERFORM set_config('night_voyager.organization_id',p_org::text,true);
  IF NOT EXISTS (
    SELECT 1 FROM app.memberships WHERE organization_id=p_org AND actor_id=p_owner AND role='advisor'
  ) THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='Skill seed owner unavailable'; END IF;
  FOR item IN SELECT value FROM jsonb_array_elements(p_seed->'entries')
  LOOP
    manifest := item->'manifest';
    evaluation := item->'evaluation';
    IF jsonb_typeof(manifest)<>'object'
       OR item->>'definition_id' IS NULL OR item->>'version_id' IS NULL
       OR manifest->>'skill_key' NOT IN (
         'student-profile-intake','study-destination-compare','evidence-research',
         'document-evidence-retrieval','family-decision-brief','application-timeline-guard'
       ) THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid Skill seed entry'; END IF;
    INSERT INTO app.skill_definitions(
      organization_id,id,skill_key,owner_actor_id,binding_kind
    ) VALUES(
      p_org,(item->>'definition_id')::uuid,manifest->>'skill_key',p_owner,manifest->>'binding_kind'
    ) ON CONFLICT (organization_id,skill_key) DO NOTHING;
    SELECT * INTO definition FROM app.skill_definitions
     WHERE organization_id=p_org AND skill_key=manifest->>'skill_key';
    IF definition.id<>(item->>'definition_id')::uuid OR definition.owner_actor_id<>p_owner
       OR definition.binding_kind<>manifest->>'binding_kind' THEN
      RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='Skill seed definition mismatch';
    END IF;
    INSERT INTO app.skill_versions(
      organization_id,id,definition_id,skill_key,semantic_version,binding_kind,
      executor_id,executor_version,input_contract_id,input_schema_sha256,
      output_contract_id,output_schema_sha256,content_sha256,tool_ids,tool_allowlist_sha256,
      data_scopes,data_scope_sha256,side_effect_level,approval_policy,policy_version,policy_sha256,
      evaluation_dataset_id,evaluation_dataset_version,evaluation_dataset_sha256,
      expected_evaluation_projection,
      runtime_manifest_id,runtime_manifest_version,runtime_manifest_sha256,
      operation_bindings,runtime_binding_sha256,manifest_projection,supersedes_version_id,is_seed
    ) VALUES(
      p_org,(item->>'version_id')::uuid,definition.id,manifest->>'skill_key',
      manifest->>'version',manifest->>'binding_kind',
      manifest->>'executor_id',manifest->>'executor_version',
      manifest->>'input_contract_id',manifest->>'input_schema_sha256',
      manifest->>'output_contract_id',manifest->>'output_schema_sha256',
      manifest->>'content_sha256',COALESCE(manifest->'tool_ids','[]'::jsonb),
      manifest->>'tool_allowlist_sha256',COALESCE(manifest->'data_scopes','[]'::jsonb),
      manifest->>'data_scope_sha256',manifest->>'side_effect_level',manifest->>'approval_policy',
      manifest->>'policy_version',manifest->>'policy_sha256',manifest->>'evaluation_dataset_id',
      manifest->>'evaluation_dataset_version',manifest->>'evaluation_dataset_sha256',
      evaluation,
      p_seed->>'runtime_manifest_id',p_seed->>'runtime_manifest_version',
      p_seed->>'runtime_manifest_sha256',manifest->'operation_bindings',
      NULLIF(manifest->>'runtime_binding_sha256',''),manifest,
      NULLIF(item->>'supersedes_version_id','')::uuid,COALESCE((item->>'is_seed')::boolean,false)
    ) ON CONFLICT (organization_id,definition_id,semantic_version) DO NOTHING;
    SELECT * INTO version FROM app.skill_versions
     WHERE organization_id=p_org AND definition_id=definition.id
       AND semantic_version=manifest->>'version';
    IF version.id<>(item->>'version_id')::uuid OR version.manifest_projection<>manifest
       OR version.expected_evaluation_projection<>evaluation
       OR version.is_seed<>COALESCE((item->>'is_seed')::boolean,false) THEN
      RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='Skill seed version mismatch';
    END IF;
    IF evaluation IS NOT NULL THEN
      INSERT INTO app.skill_evaluation_results(
        organization_id,id,definition_id,candidate_id,version_id,evaluator_id,evaluator_version,
        dataset_id,dataset_version,dataset_sha256,assertion_projection,output_sha256,status,
        failed_assertion_ids,request_sha256,is_seed
      ) VALUES(
        p_org,(item->>'evaluation_id')::uuid,definition.id,NULL,version.id,
        evaluation->>'evaluator_id',evaluation->>'evaluator_version',evaluation->>'dataset_id',
        evaluation->>'dataset_version',evaluation->>'dataset_sha256',evaluation->'assertions',
        evaluation->>'output_sha256',evaluation->>'status',evaluation->'failed_assertion_ids',
        item->>'request_sha256',true
      ) ON CONFLICT (organization_id,definition_id,version_id,evaluator_id,evaluator_version,dataset_id,dataset_version) DO NOTHING;
      SELECT * INTO evaluation_row FROM app.skill_evaluation_results
       WHERE organization_id=p_org AND definition_id=definition.id AND version_id=version.id
         AND evaluator_id=evaluation->>'evaluator_id' AND evaluator_version=evaluation->>'evaluator_version'
         AND dataset_id=evaluation->>'dataset_id' AND dataset_version=evaluation->>'dataset_version';
      IF NOT FOUND
         OR evaluation_row.id IS DISTINCT FROM (item->>'evaluation_id')::uuid
         OR evaluation_row.dataset_sha256 IS DISTINCT FROM evaluation->>'dataset_sha256'
         OR evaluation_row.assertion_projection IS DISTINCT FROM evaluation->'assertions'
         OR evaluation_row.output_sha256 IS DISTINCT FROM evaluation->>'output_sha256'
         OR evaluation_row.status IS DISTINCT FROM evaluation->>'status'
         OR evaluation_row.failed_assertion_ids
            IS DISTINCT FROM evaluation->'failed_assertion_ids'
         OR evaluation_row.request_sha256 IS DISTINCT FROM item->>'request_sha256'
         OR NOT evaluation_row.is_seed THEN
        RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='Skill seed evaluation mismatch';
      END IF;
      IF definition.skill_key='study-destination-compare' AND version.semantic_version='1.0.0' THEN
        INSERT INTO app.skill_activation_events(
          organization_id,id,definition_id,activated_version_id,previous_version_id,candidate_id,evaluation_id,
          event_kind,owner_actor_id,reason,request_sha256,activation_sequence
        ) VALUES(
          p_org,(item->>'activation_event_id')::uuid,definition.id,version.id,NULL,NULL,evaluation_row.id,
          'seed',p_owner,'canonical synthetic Skill seed',item->>'request_sha256',1
        ) ON CONFLICT (organization_id,definition_id,activation_sequence) DO NOTHING;
        IF NOT EXISTS (
          SELECT 1 FROM app.skill_activation_events
          WHERE organization_id=p_org AND definition_id=definition.id
            AND id=(item->>'activation_event_id')::uuid AND activated_version_id=version.id
            AND event_kind='seed' AND activation_sequence=1
        ) THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='Skill seed activation mismatch'; END IF;
      END IF;
    END IF;
  END LOOP;
  IF (SELECT count(*) FROM app.skill_definitions WHERE organization_id=p_org)<>6
     OR (SELECT count(*) FROM app.skill_versions
         WHERE organization_id=p_org AND is_seed)<>6
     OR (SELECT count(*) FROM app.skill_evaluation_results
         WHERE organization_id=p_org AND is_seed)<>6
     OR (SELECT count(*) FROM app.skill_activation_events
         WHERE organization_id=p_org AND event_kind='seed')<>1 THEN
    RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='Skill seed catalog mismatch';
  END IF;
END; $$;
"""

SEED_SQL = SEED_SQL_TEMPLATE.replace(
    "__CANONICAL_DEMO_SKILL_SEED_B64__", CANONICAL_DEMO_SKILL_SEED_B64
)

PINNED_DEMO_TASK_SEED_SQL = r"""
CREATE FUNCTION app.seed_demo_pinned_collaboration_task(p_org uuid,p_case uuid,p_task uuid,p_advisor uuid,p_expected_pin jsonb) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE definition app.skill_definitions%ROWTYPE; version app.skill_versions%ROWTYPE; activation app.skill_activation_events%ROWTYPE; source_pack app.source_packs%ROWTYPE; existing_task app.agent_tasks%ROWTYPE; existing_event app.agent_task_events%ROWTYPE; exact_pin jsonb; task_insert_count integer;
BEGIN
  IF p_org IS NULL OR p_case IS NULL OR p_task IS NULL OR p_advisor IS NULL
     OR p_expected_pin IS NULL OR jsonb_typeof(p_expected_pin)<>'object' THEN
    RAISE EXCEPTION USING ERRCODE='NV022', MESSAGE='Skill runtime pin is invalid';
  END IF;
  PERFORM set_config('night_voyager.organization_id',p_org::text,true);
  SELECT * INTO definition FROM app.skill_definitions
   WHERE organization_id=p_org AND skill_key='study-destination-compare'
     AND binding_kind='planning_runtime';
  IF NOT FOUND THEN
    RAISE EXCEPTION USING ERRCODE='NV015', MESSAGE='active Skill version unavailable';
  END IF;
  SELECT * INTO version FROM app.skill_versions
   WHERE organization_id=p_org AND definition_id=definition.id
     AND semantic_version='1.0.0' AND binding_kind='planning_runtime' AND is_seed;
  IF NOT FOUND OR version.runtime_binding_sha256 IS NULL THEN
    RAISE EXCEPTION USING ERRCODE='NV015', MESSAGE='active Skill version unavailable';
  END IF;
  SELECT * INTO activation FROM app.skill_activation_events
   WHERE organization_id=p_org AND definition_id=definition.id
     AND activated_version_id=version.id AND event_kind='seed'
     AND activation_sequence=1;
  IF NOT FOUND THEN
    RAISE EXCEPTION USING ERRCODE='NV015', MESSAGE='active Skill version unavailable';
  END IF;
  exact_pin := jsonb_build_object(
    'skill_definition_id',definition.id,
    'skill_version_id',version.id,
    'skill_activation_event_id',activation.id,
    'skill_activation_sequence',activation.activation_sequence,
    'runtime_binding_sha256',version.runtime_binding_sha256
  );
  IF p_expected_pin IS DISTINCT FROM exact_pin THEN
    RAISE EXCEPTION USING ERRCODE='NV022', MESSAGE='Skill runtime pin is invalid';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM app.student_cases selected_case
     WHERE selected_case.organization_id=p_org AND selected_case.id=p_case
       AND selected_case.state='planning' AND selected_case.current_revision=1
  ) OR NOT EXISTS (
    SELECT 1 FROM app.student_case_participants participant
     WHERE participant.organization_id=p_org AND participant.case_id=p_case
       AND participant.actor_id=p_advisor AND participant.role='advisor'
  ) OR NOT EXISTS (
    SELECT 1 FROM app.collaboration_threads thread
     WHERE thread.organization_id=p_org AND thread.case_id=p_case
  ) THEN
    RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='demo collaboration pinned task unavailable';
  END IF;
  SELECT * INTO source_pack FROM app.source_packs pack
   WHERE pack.organization_id=p_org ORDER BY pack.id,pack.version LIMIT 1;
  IF NOT FOUND OR source_pack.id IS NULL THEN
    RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='demo collaboration source pack is unavailable';
  END IF;
  INSERT INTO app.agent_tasks(
    organization_id,id,case_id,operation,case_revision,source_pack_id,
    source_pack_version,policy_version,request_sha256,created_by_actor_id,
    row_version,state,attempt_count,lease_generation,created_at,updated_at,
    skill_definition_id,skill_version_id,skill_activation_event_id,
    skill_activation_sequence,runtime_binding_sha256
  ) VALUES(
    p_org,p_task,p_case,'generate_planning_run_v1',1,source_pack.id,
    source_pack.version,'m3a-policy-v1',repeat('e',64),p_advisor,
    1,'waiting_review',0,0,timestamptz '2026-01-01 00:00:00+00',
    timestamptz '2026-01-01 00:00:00+00',definition.id,version.id,activation.id,
    activation.activation_sequence,version.runtime_binding_sha256
  ) ON CONFLICT (organization_id,id) DO NOTHING;
  GET DIAGNOSTICS task_insert_count = ROW_COUNT;
  SELECT * INTO existing_task FROM app.agent_tasks task
   WHERE task.organization_id=p_org AND task.id=p_task;
  IF NOT FOUND OR existing_task.case_id IS DISTINCT FROM p_case
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
     OR existing_task.lease_owner IS NOT NULL
     OR existing_task.lease_generation IS DISTINCT FROM 0
     OR existing_task.lease_expires_at IS NOT NULL
     OR existing_task.result_planning_run_id IS NOT NULL
     OR existing_task.terminal_code IS NOT NULL
     OR existing_task.skill_definition_id IS DISTINCT FROM definition.id
     OR existing_task.skill_version_id IS DISTINCT FROM version.id
     OR existing_task.skill_activation_event_id IS DISTINCT FROM activation.id
     OR existing_task.skill_activation_sequence IS DISTINCT FROM activation.activation_sequence
     OR existing_task.runtime_binding_sha256 IS DISTINCT FROM version.runtime_binding_sha256
     OR existing_task.created_at IS DISTINCT FROM timestamptz '2026-01-01 00:00:00+00'
     OR existing_task.updated_at IS DISTINCT FROM timestamptz '2026-01-01 00:00:00+00' THEN
    RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='demo collaboration pinned task mismatch';
  END IF;
  IF task_insert_count=1 THEN
    INSERT INTO app.agent_task_events(
      organization_id,task_id,event_sequence,event_code,public_status,
      public_code,attempt_no,result_planning_run_id,created_at
    ) VALUES(
      p_org,p_task,1,'waiting_review','needs_advisor_review',
      'review_required',0,NULL,timestamptz '2026-01-01 00:00:00+00'
    );
  END IF;
  SELECT * INTO existing_event FROM app.agent_task_events event
   WHERE event.organization_id=p_org AND event.task_id=p_task
     AND event.event_sequence=1;
  IF NOT FOUND OR existing_event.event_code IS DISTINCT FROM 'waiting_review'
     OR existing_event.public_status IS DISTINCT FROM 'needs_advisor_review'
     OR existing_event.public_code IS DISTINCT FROM 'review_required'
     OR existing_event.attempt_no IS DISTINCT FROM 0
     OR existing_event.result_planning_run_id IS NOT NULL
     OR existing_event.created_at IS DISTINCT FROM timestamptz '2026-01-01 00:00:00+00'
     OR EXISTS (
       SELECT 1 FROM app.agent_task_events event
        WHERE event.organization_id=p_org AND event.task_id=p_task
          AND event.event_sequence<>1
     )
     OR EXISTS (
       SELECT 1 FROM app.agent_executions execution
        WHERE execution.organization_id=p_org AND execution.task_id=p_task
     )
     OR EXISTS (
       SELECT 1 FROM internal.agent_task_dispatch dispatch
        WHERE dispatch.organization_id=p_org AND dispatch.task_id=p_task
     ) THEN
    RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='demo collaboration pinned task event mismatch';
  END IF;
END; $$;
"""

LEGACY_DEMO_TASK_SEED_SQL = r"""
CREATE FUNCTION app.seed_demo_collaboration(p_org uuid,p_case uuid,p_thread uuid,p_advisor uuid,p_subject uuid,p_message uuid,p_candidate uuid,p_task uuid,p_fixture_kind text) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE existing_task app.agent_tasks%ROWTYPE; existing_event app.agent_task_events%ROWTYPE; source_pack app.source_packs%ROWTYPE;
BEGIN
  PERFORM set_config('night_voyager.organization_id',p_org::text,true);
  IF p_fixture_kind='active_task' AND EXISTS (
    SELECT 1 FROM app.agent_tasks task
     WHERE task.organization_id=p_org AND task.id=p_task
  ) THEN
    SELECT * INTO source_pack FROM app.source_packs pack
     WHERE pack.organization_id=p_org ORDER BY pack.id,pack.version LIMIT 1;
    SELECT * INTO existing_task FROM app.agent_tasks task
     WHERE task.organization_id=p_org AND task.id=p_task;
    IF NOT FOUND OR source_pack.id IS NULL
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
       OR existing_task.lease_owner IS NOT NULL
       OR existing_task.lease_generation IS DISTINCT FROM 0
       OR existing_task.lease_expires_at IS NOT NULL
       OR existing_task.result_planning_run_id IS NOT NULL
       OR existing_task.terminal_code IS NOT NULL
       OR existing_task.skill_definition_id IS NOT NULL
       OR existing_task.skill_version_id IS NOT NULL
       OR existing_task.skill_activation_event_id IS NOT NULL
       OR existing_task.skill_activation_sequence IS NOT NULL
       OR existing_task.runtime_binding_sha256 IS NOT NULL
       OR existing_task.created_at IS DISTINCT FROM timestamptz '2026-01-01 00:00:00+00'
       OR existing_task.updated_at IS DISTINCT FROM timestamptz '2026-01-01 00:00:00+00' THEN
      RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='demo collaboration legacy task mismatch';
    END IF;
    SELECT * INTO existing_event FROM app.agent_task_events event
     WHERE event.organization_id=p_org AND event.task_id=p_task
       AND event.event_sequence=1;
    IF NOT FOUND OR existing_event.event_code IS DISTINCT FROM 'waiting_review'
       OR existing_event.public_status IS DISTINCT FROM 'needs_advisor_review'
       OR existing_event.public_code IS DISTINCT FROM 'review_required'
       OR existing_event.attempt_no IS DISTINCT FROM 0
       OR existing_event.result_planning_run_id IS NOT NULL
       OR existing_event.created_at IS DISTINCT FROM timestamptz '2026-01-01 00:00:00+00'
       OR (SELECT count(*) FROM app.agent_task_events event
            WHERE event.organization_id=p_org AND event.task_id=p_task)<>1
       OR EXISTS (
         SELECT 1 FROM app.agent_executions execution
          WHERE execution.organization_id=p_org AND execution.task_id=p_task
       )
       OR EXISTS (
         SELECT 1 FROM internal.agent_task_dispatch dispatch
          WHERE dispatch.organization_id=p_org AND dispatch.task_id=p_task
       ) THEN
      RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='demo collaboration legacy task event mismatch';
    END IF;
  END IF;
  PERFORM app.seed_demo_collaboration_0007(
    p_org,p_case,p_thread,p_advisor,p_subject,p_message,p_candidate,p_task,p_fixture_kind
  );
END; $$;
"""

DOWNGRADE_GUARD_SQL_TEMPLATE = r"""
DO $$
DECLARE
  canonical_seed jsonb := convert_from(decode('__CANONICAL_DEMO_SKILL_SEED_B64__','base64'),'UTF8')::jsonb;
  seed_org uuid;
  actual_seed jsonb;
BEGIN
  IF EXISTS (SELECT 1 FROM app.agent_tasks WHERE skill_definition_id IS NOT NULL)
     OR EXISTS (SELECT 1 FROM app.agent_executions WHERE skill_definition_id IS NOT NULL)
     OR EXISTS (SELECT 1 FROM app.skill_change_candidates)
     OR EXISTS (SELECT 1 FROM app.skill_evaluation_results WHERE NOT is_seed)
     OR EXISTS (SELECT 1 FROM app.skill_activation_events WHERE event_kind<>'seed')
     OR EXISTS (SELECT 1 FROM app.skill_versions WHERE NOT is_seed OR semantic_version<>'1.0.0') THEN
    RAISE EXCEPTION 'refusing downgrade: Skill governance or runtime pin history exists';
  END IF;

  IF NOT EXISTS (SELECT 1 FROM app.skill_definitions) AND (
       EXISTS (SELECT 1 FROM app.skill_versions)
       OR EXISTS (SELECT 1 FROM app.skill_evaluation_results)
       OR EXISTS (SELECT 1 FROM app.skill_activation_events)
     ) THEN
    RAISE EXCEPTION 'refusing downgrade: Skill governance or runtime pin history exists';
  END IF;

  FOR seed_org IN
    SELECT organization_id FROM app.skill_definitions GROUP BY organization_id
  LOOP
    IF (SELECT count(*) FROM app.skill_definitions WHERE organization_id=seed_org)<>6
       OR (SELECT count(DISTINCT skill_key) FROM app.skill_definitions WHERE organization_id=seed_org)<>6
       OR (SELECT count(DISTINCT owner_actor_id) FROM app.skill_definitions WHERE organization_id=seed_org)<>1
       OR (SELECT count(*) FROM app.skill_versions WHERE organization_id=seed_org)<>6
       OR (SELECT count(*) FROM app.skill_evaluation_results WHERE organization_id=seed_org)<>6
       OR (SELECT count(*) FROM app.skill_activation_events WHERE organization_id=seed_org)<>1 THEN
      RAISE EXCEPTION 'refusing downgrade: Skill governance or runtime pin history exists';
    END IF;

    SELECT jsonb_build_object(
      'schema_version',1,
      'runtime_manifest_id',canonical_seed->>'runtime_manifest_id',
      'runtime_manifest_version',canonical_seed->>'runtime_manifest_version',
      'runtime_manifest_sha256',canonical_seed->>'runtime_manifest_sha256',
      'evaluation_manifest_id',canonical_seed->>'evaluation_manifest_id',
      'evaluation_manifest_version',canonical_seed->>'evaluation_manifest_version',
      'evaluation_manifest_sha256',canonical_seed->>'evaluation_manifest_sha256',
      'entries',jsonb_agg(
        jsonb_strip_nulls(jsonb_build_object(
          'definition_id',definition.id,
          'version_id',version.id,
          'evaluation_id',evaluation.id,
          'activation_event_id',activation.id,
          'is_seed',(version.is_seed AND evaluation.is_seed),
          'manifest',version.manifest_projection,
          'evaluation',CASE WHEN evaluation.id IS NULL THEN NULL ELSE jsonb_build_object(
            'schema_version',1,
            'skill_key',definition.skill_key,
            'version',version.semantic_version,
            'evaluator_id',evaluation.evaluator_id,
            'evaluator_version',evaluation.evaluator_version,
            'dataset_id',evaluation.dataset_id,
            'dataset_version',evaluation.dataset_version,
            'dataset_sha256',evaluation.dataset_sha256,
            'assertions',evaluation.assertion_projection,
            'output_sha256',evaluation.output_sha256,
            'status',evaluation.status,
            'failed_assertion_ids',evaluation.failed_assertion_ids
          ) END,
          'request_sha256',evaluation.request_sha256
        )) ORDER BY expected.ordinality
      )
    ) INTO actual_seed
    FROM jsonb_array_elements(canonical_seed->'entries')
      WITH ORDINALITY AS expected(item,ordinality)
    LEFT JOIN app.skill_definitions definition
      ON definition.organization_id=seed_org
     AND definition.id=(expected.item->>'definition_id')::uuid
    LEFT JOIN app.skill_versions version
      ON version.organization_id=seed_org
     AND version.definition_id=definition.id
     AND version.id=(expected.item->>'version_id')::uuid
    LEFT JOIN app.skill_evaluation_results evaluation
      ON evaluation.organization_id=seed_org
     AND evaluation.definition_id=definition.id
     AND evaluation.version_id=version.id
     AND evaluation.id=(expected.item->>'evaluation_id')::uuid
    LEFT JOIN app.skill_activation_events activation
      ON activation.organization_id=seed_org
     AND activation.definition_id=definition.id
     AND activation.id=(expected.item->>'activation_event_id')::uuid;

    IF actual_seed IS DISTINCT FROM canonical_seed OR EXISTS (
      SELECT 1
      FROM app.skill_activation_events activation
      JOIN app.skill_definitions definition
        ON definition.organization_id=activation.organization_id
       AND definition.id=activation.definition_id
      JOIN app.skill_evaluation_results evaluation
        ON evaluation.organization_id=activation.organization_id
       AND evaluation.definition_id=activation.definition_id
       AND evaluation.id=activation.evaluation_id
      WHERE activation.organization_id=seed_org
        AND (
          activation.binding_kind<>'planning_runtime'
          OR activation.event_kind<>'seed'
          OR activation.previous_version_id IS NOT NULL
          OR activation.candidate_id IS NOT NULL
          OR activation.owner_actor_id<>definition.owner_actor_id
          OR activation.owner_role<>'advisor'
          OR activation.reason<>'canonical synthetic Skill seed'
          OR activation.request_sha256<>evaluation.request_sha256
          OR activation.activation_sequence<>1
        )
    ) THEN
      RAISE EXCEPTION 'refusing downgrade: Skill governance or runtime pin history exists';
    END IF;
  END LOOP;
END; $$;
"""

DOWNGRADE_GUARD_SQL = DOWNGRADE_GUARD_SQL_TEMPLATE.replace(
    "__CANONICAL_DEMO_SKILL_SEED_B64__", CANONICAL_DEMO_SKILL_SEED_B64
)

CREATE_TASK_SQL = r"""
CREATE FUNCTION app.create_agent_task(p_org uuid,p_actor uuid,p_case uuid,p_task uuid,p_operation text,p_revision integer,p_pack uuid,p_pack_version integer,p_policy text,p_skill_manifest jsonb,p_request_hash text,p_key_hash text) RETURNS TABLE(task_id uuid,row_version integer,state text,attempt_count integer,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE prior app.idempotency_records%ROWTYPE; selected app.agent_tasks%ROWTYPE; current_case app.student_cases%ROWTYPE; definition app.skill_definitions%ROWTYPE; activation app.skill_activation_events%ROWTYPE; version app.skill_versions%ROWTYPE;
BEGIN
  PERFORM app.assert_m3b_context(p_org,p_actor,'advisor');
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
   WHERE c.organization_id=p_org AND c.id=p_case FOR SHARE;
  IF NOT FOUND OR current_case.current_revision<>p_revision OR current_case.state<>'planning'
     OR NOT EXISTS (
       SELECT 1 FROM app.source_packs s
       WHERE s.organization_id=p_org AND s.id=p_pack AND s.version=p_pack_version
     ) THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='task input is stale'; END IF;
  IF p_operation='generate_governed_mixed_planning_run_v1' AND NOT EXISTS (
    SELECT 1 FROM app.external_evidence_verifications v
    WHERE v.organization_id=p_org AND v.case_id=p_case AND v.case_revision=p_revision
      AND v.decision='approve' AND v.claim='australia_program_fit' AND v.evidence_role='program_fit'
      AND v.baseline_source_pack_id=p_pack AND v.promoted_source_pack_version=p_pack_version
      AND v.baseline_source_pack_version=1
      AND v.baseline_manifest_sha256='84350ea5705d9681d3e6550e1bd06e3340a9fcf0e7e7bbed4478ed3403405f28'
      AND v.baseline_raw_manifest_sha256='5d455d2c409c322e093f3a116387f3cef0fb7ea0f7357fec5e76e9da5b3a2a25'
  ) THEN RAISE EXCEPTION USING ERRCODE='NV011', MESSAGE='governed mixed approval is unavailable'; END IF;
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
  INSERT INTO app.agent_tasks(
    organization_id,id,case_id,operation,case_revision,source_pack_id,source_pack_version,
    policy_version,request_sha256,created_by_actor_id,state,skill_definition_id,
    skill_version_id,skill_activation_event_id,skill_activation_sequence,runtime_binding_sha256
  ) VALUES(
    p_org,p_task,p_case,p_operation,p_revision,p_pack,p_pack_version,p_policy,p_request_hash,
    p_actor,'queued',definition.id,version.id,activation.id,activation.activation_sequence,
    version.runtime_binding_sha256
  );
  INSERT INTO internal.agent_task_dispatch(task_id,organization_id,available_at) VALUES(p_task,p_org,clock_timestamp());
  PERFORM app.append_agent_task_event(p_org,p_task,'queued','preparing','queued',0,NULL);
  INSERT INTO app.idempotency_records VALUES(p_org,p_actor,'agent_task_create',p_key_hash,p_request_hash,'agent_task',p_task,clock_timestamp());
  SELECT * INTO selected FROM app.agent_tasks WHERE organization_id=p_org AND id=p_task;
  RETURN QUERY SELECT selected.id,selected.row_version,selected.state,selected.attempt_count,false;
END; $$;
"""

CLAIM_TASK_SQL = r"""
CREATE FUNCTION app.claim_agent_task(p_worker text) RETURNS TABLE(task_id uuid,organization_id uuid,lease_generation bigint) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE candidate record; selected app.agent_tasks%ROWTYPE; reclaimed boolean := false; next_attempt integer; next_generation bigint; new_expiry timestamptz; selected_adapter text; selected_adapter_version text;
BEGIN
  IF NULLIF(btrim(p_worker),'') IS NULL OR length(p_worker)>200 THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid worker identity'; END IF;
  SELECT d.task_id,d.organization_id INTO candidate FROM internal.agent_task_dispatch d WHERE d.available_at<=clock_timestamp() ORDER BY d.available_at,d.task_id FOR UPDATE SKIP LOCKED LIMIT 1;
  IF NOT FOUND THEN RETURN; END IF;
  PERFORM set_config('night_voyager.organization_id',candidate.organization_id::text,true);
  SELECT * INTO selected FROM app.agent_tasks t WHERE t.organization_id=candidate.organization_id AND t.id=candidate.task_id FOR UPDATE;
  IF NOT FOUND OR selected.state IN ('waiting_review','succeeded','blocked','timed_out','failed','cancelled') THEN DELETE FROM internal.agent_task_dispatch d WHERE d.organization_id=candidate.organization_id AND d.task_id=candidate.task_id; RETURN; END IF;
  IF selected.skill_definition_id IS NULL OR selected.skill_version_id IS NULL
     OR selected.skill_activation_event_id IS NULL OR selected.skill_activation_sequence IS NULL
     OR selected.runtime_binding_sha256 IS NULL OR NOT EXISTS (
       SELECT 1 FROM app.skill_versions v
       JOIN app.skill_activation_events a
         ON a.organization_id=v.organization_id AND a.definition_id=v.definition_id
        AND a.activated_version_id=v.id AND a.id=selected.skill_activation_event_id
        AND a.activation_sequence=selected.skill_activation_sequence
       WHERE v.organization_id=selected.organization_id AND v.definition_id=selected.skill_definition_id
         AND v.id=selected.skill_version_id AND v.runtime_binding_sha256=selected.runtime_binding_sha256
         AND v.binding_kind='planning_runtime'
     ) THEN
    UPDATE app.agent_tasks SET state='failed',row_version=row_version+1,lease_owner=NULL,
      lease_expires_at=NULL,terminal_code='skill_pin_invalid',updated_at=clock_timestamp()
      WHERE organization_id=selected.organization_id AND id=selected.id;
    DELETE FROM internal.agent_task_dispatch WHERE organization_id=selected.organization_id AND task_id=selected.id;
    PERFORM app.append_agent_task_event(selected.organization_id,selected.id,'failed','failed','skill_pin_invalid',selected.attempt_count,NULL);
    RETURN;
  END IF;
  IF selected.state IN ('leased','running') THEN
    IF selected.lease_expires_at>clock_timestamp() THEN UPDATE internal.agent_task_dispatch d SET available_at=selected.lease_expires_at WHERE d.organization_id=candidate.organization_id AND d.task_id=candidate.task_id; RETURN; END IF;
    reclaimed := true;
    IF selected.attempt_count>=3 THEN
      UPDATE app.agent_executions e SET status='failed',retryable=false,public_code='lease_expired',duration_ms=GREATEST(0,floor(extract(epoch FROM (clock_timestamp()-COALESCE(e.started_at,e.created_at)))*1000)::integer),finished_at=clock_timestamp() WHERE e.organization_id=selected.organization_id AND e.task_id=selected.id AND e.lease_generation=selected.lease_generation AND e.status IN ('leased','running');
      UPDATE app.agent_tasks t SET state='failed',row_version=t.row_version+1,lease_owner=NULL,lease_expires_at=NULL,terminal_code='lease_expired',updated_at=clock_timestamp() WHERE t.organization_id=selected.organization_id AND t.id=selected.id;
      DELETE FROM internal.agent_task_dispatch d WHERE d.organization_id=selected.organization_id AND d.task_id=selected.id;
      PERFORM app.append_agent_task_event(selected.organization_id,selected.id,'failed','failed','lease_expired',selected.attempt_count,NULL); RETURN;
    END IF;
    UPDATE app.agent_executions e SET status='retry_scheduled',retryable=true,public_code='lease_expired',duration_ms=GREATEST(0,floor(extract(epoch FROM (clock_timestamp()-COALESCE(e.started_at,e.created_at)))*1000)::integer),finished_at=clock_timestamp() WHERE e.organization_id=selected.organization_id AND e.task_id=selected.id AND e.lease_generation=selected.lease_generation AND e.status IN ('leased','running');
  ELSIF selected.state<>'queued' THEN RETURN; END IF;
  next_attempt := selected.attempt_count+1; next_generation := selected.lease_generation+1; new_expiry := clock_timestamp()+interval '60 seconds';
  selected_adapter := CASE selected.operation WHEN 'generate_planning_run_v1' THEN 'deterministic_planning' WHEN 'generate_governed_mixed_planning_run_v1' THEN 'governed_mixed_planning' ELSE NULL END;
  selected_adapter_version := CASE selected.operation WHEN 'generate_planning_run_v1' THEN 'm4a-v1' WHEN 'generate_governed_mixed_planning_run_v1' THEN 'dra-mixed-v1' ELSE NULL END;
  IF selected_adapter IS NULL THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid task operation'; END IF;
  UPDATE app.agent_tasks t SET state='leased',row_version=t.row_version+1,attempt_count=next_attempt,lease_owner=p_worker,lease_generation=next_generation,lease_expires_at=new_expiry,terminal_code=NULL,updated_at=clock_timestamp() WHERE t.organization_id=selected.organization_id AND t.id=selected.id;
  UPDATE internal.agent_task_dispatch d SET available_at=new_expiry WHERE d.organization_id=selected.organization_id AND d.task_id=selected.id;
  INSERT INTO app.agent_executions(
    organization_id,id,task_id,attempt_no,lease_generation,adapter_id,adapter_version,status,cost_status,
    skill_definition_id,skill_version_id,skill_activation_event_id,skill_activation_sequence,runtime_binding_sha256
  ) VALUES(
    selected.organization_id,gen_random_uuid(),selected.id,next_attempt,next_generation,
    selected_adapter,selected_adapter_version,'leased','not_applicable',selected.skill_definition_id,
    selected.skill_version_id,selected.skill_activation_event_id,selected.skill_activation_sequence,
    selected.runtime_binding_sha256
  );
  IF reclaimed THEN PERFORM app.append_agent_task_event(selected.organization_id,selected.id,'lease_reclaimed','preparing','lease_expired',next_attempt,NULL); END IF;
  PERFORM app.append_agent_task_event(selected.organization_id,selected.id,'lease_acquired','preparing','lease_acquired',next_attempt,NULL);
  RETURN QUERY SELECT selected.id,selected.organization_id,next_generation;
END; $$;
"""

PIN_GUARD_SQL = r"""
CREATE FUNCTION app.guard_agent_skill_pin() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  IF NEW.skill_definition_id IS DISTINCT FROM OLD.skill_definition_id
     OR NEW.skill_version_id IS DISTINCT FROM OLD.skill_version_id
     OR NEW.skill_activation_event_id IS DISTINCT FROM OLD.skill_activation_event_id
     OR NEW.skill_activation_sequence IS DISTINCT FROM OLD.skill_activation_sequence
     OR NEW.runtime_binding_sha256 IS DISTINCT FROM OLD.runtime_binding_sha256 THEN
    RAISE EXCEPTION USING ERRCODE='NV022', MESSAGE='Skill runtime pin is immutable';
  END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER agent_tasks_skill_pin_immutable BEFORE UPDATE ON app.agent_tasks FOR EACH ROW EXECUTE FUNCTION app.guard_agent_skill_pin();
CREATE TRIGGER agent_executions_skill_pin_immutable BEFORE UPDATE ON app.agent_executions FOR EACH ROW EXECUTE FUNCTION app.guard_agent_skill_pin();
"""

PRIVILEGE_SQL = r"""
REVOKE ALL ON TABLE app.skill_definitions FROM PUBLIC;
REVOKE ALL ON TABLE app.skill_definitions FROM night_voyager_api;
REVOKE ALL ON TABLE app.skill_definitions FROM night_voyager_worker;
REVOKE ALL ON TABLE app.skill_versions FROM PUBLIC;
REVOKE ALL ON TABLE app.skill_versions FROM night_voyager_api;
REVOKE ALL ON TABLE app.skill_versions FROM night_voyager_worker;
REVOKE ALL ON TABLE app.skill_change_candidates FROM PUBLIC;
REVOKE ALL ON TABLE app.skill_change_candidates FROM night_voyager_api;
REVOKE ALL ON TABLE app.skill_change_candidates FROM night_voyager_worker;
REVOKE ALL ON TABLE app.skill_evaluation_results FROM PUBLIC;
REVOKE ALL ON TABLE app.skill_evaluation_results FROM night_voyager_api;
REVOKE ALL ON TABLE app.skill_evaluation_results FROM night_voyager_worker;
REVOKE ALL ON TABLE app.skill_activation_events FROM PUBLIC;
REVOKE ALL ON TABLE app.skill_activation_events FROM night_voyager_api;
REVOKE ALL ON TABLE app.skill_activation_events FROM night_voyager_worker;

REVOKE ALL ON FUNCTION app.create_skill_change_candidate(uuid,uuid,text,uuid,text,text,text,text,jsonb,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.record_skill_candidate_evaluation(uuid,uuid,uuid,uuid,jsonb,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.promote_skill_change_candidate(uuid,uuid,uuid,uuid,text,bigint,text,jsonb,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.rollback_skill_activation(uuid,uuid,text,uuid,text,text,bigint,text,jsonb,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.seed_demo_skill_registry(uuid,uuid,jsonb) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.seed_demo_collaboration(uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.seed_demo_collaboration(uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,text) FROM night_voyager_api;
REVOKE ALL ON FUNCTION app.seed_demo_collaboration(uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,text) FROM night_voyager_worker;
REVOKE ALL ON FUNCTION app.seed_demo_collaboration_0007(uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.seed_demo_collaboration_0007(uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,text) FROM night_voyager_api;
REVOKE ALL ON FUNCTION app.seed_demo_collaboration_0007(uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,text) FROM night_voyager_worker;
REVOKE ALL ON FUNCTION app.seed_demo_pinned_collaboration_task(uuid,uuid,uuid,uuid,jsonb) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.seed_demo_pinned_collaboration_task(uuid,uuid,uuid,uuid,jsonb) FROM night_voyager_api;
REVOKE ALL ON FUNCTION app.seed_demo_pinned_collaboration_task(uuid,uuid,uuid,uuid,jsonb) FROM night_voyager_worker;
REVOKE ALL ON FUNCTION app.list_skill_catalog(uuid,uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.get_skill_catalog_item(uuid,uuid,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.load_skill_candidate_context(uuid,uuid,uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.inspect_planning_skill(uuid,uuid,uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.load_agent_task_skill_pin(uuid,uuid,bigint) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.load_persisted_synthetic_planning_snapshot(uuid,uuid,integer,uuid,integer,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.create_agent_task(uuid,uuid,uuid,uuid,text,integer,uuid,integer,text,jsonb,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.claim_agent_task(text) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION app.create_skill_change_candidate(uuid,uuid,text,uuid,text,text,text,text,jsonb,text,text) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.record_skill_candidate_evaluation(uuid,uuid,uuid,uuid,jsonb,text,text) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.promote_skill_change_candidate(uuid,uuid,uuid,uuid,text,bigint,text,jsonb,text,text) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.rollback_skill_activation(uuid,uuid,text,uuid,text,text,bigint,text,jsonb,text,text) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.list_skill_catalog(uuid,uuid) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.get_skill_catalog_item(uuid,uuid,text) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.load_skill_candidate_context(uuid,uuid,uuid) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.inspect_planning_skill(uuid,uuid,uuid) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.load_agent_task_skill_pin(uuid,uuid,bigint) TO night_voyager_worker;
GRANT EXECUTE ON FUNCTION app.load_persisted_synthetic_planning_snapshot(uuid,uuid,integer,uuid,integer,text) TO night_voyager_worker;
GRANT EXECUTE ON FUNCTION app.create_agent_task(uuid,uuid,uuid,uuid,text,integer,uuid,integer,text,jsonb,text,text) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION app.claim_agent_task(text) TO night_voyager_worker;
"""

# Exact 0007 authority restored by downgrade.
_0007_CREATE_TASK_SQL = r"""
CREATE FUNCTION app.create_agent_task(p_org uuid,p_actor uuid,p_case uuid,p_task uuid,p_operation text,p_revision integer,p_pack uuid,p_pack_version integer,p_policy text,p_request_hash text,p_key_hash text) RETURNS TABLE(task_id uuid,row_version integer,state text,attempt_count integer,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE prior app.idempotency_records%ROWTYPE; selected app.agent_tasks%ROWTYPE; current_case app.student_cases%ROWTYPE;
BEGIN
  PERFORM app.assert_m3b_context(p_org,p_actor,'advisor');
  SELECT * INTO prior FROM app.idempotency_records WHERE organization_id=p_org AND actor_id=p_actor AND operation='agent_task_create' AND key_sha256=p_key_hash;
  IF FOUND THEN
    IF prior.request_sha256<>p_request_hash THEN RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='idempotency request mismatch'; END IF;
    SELECT * INTO selected FROM app.agent_tasks WHERE organization_id=p_org AND id=prior.response_id;
    IF selected.operation<>p_operation THEN RAISE EXCEPTION USING ERRCODE='NV008', MESSAGE='idempotency operation mismatch'; END IF;
    RETURN QUERY SELECT selected.id,selected.row_version,selected.state,selected.attempt_count,true;
    RETURN;
  END IF;
  IF p_operation NOT IN ('generate_planning_run_v1','generate_governed_mixed_planning_run_v1') OR p_policy<>'m3a-policy-v1' OR p_revision<=0 OR p_pack_version<=0 OR p_request_hash !~ '^[0-9a-f]{64}$' OR p_key_hash !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid task pins'; END IF;
  IF NOT EXISTS (SELECT 1 FROM app.student_case_participants WHERE organization_id=p_org AND case_id=p_case AND actor_id=p_actor AND role='advisor') THEN RAISE EXCEPTION USING ERRCODE='NV007', MESSAGE='participant not assigned'; END IF;
  SELECT * INTO current_case FROM app.student_cases c WHERE c.organization_id=p_org AND c.id=p_case FOR SHARE;
  IF NOT FOUND OR current_case.current_revision<>p_revision OR current_case.state<>'planning' OR NOT EXISTS (SELECT 1 FROM app.source_packs s WHERE s.organization_id=p_org AND s.id=p_pack AND s.version=p_pack_version) THEN RAISE EXCEPTION USING ERRCODE='NV003', MESSAGE='task input is stale'; END IF;
  IF p_operation='generate_governed_mixed_planning_run_v1' AND NOT EXISTS (
    SELECT 1 FROM app.external_evidence_verifications v
    WHERE v.organization_id=p_org AND v.case_id=p_case AND v.case_revision=p_revision
      AND v.decision='approve' AND v.claim='australia_program_fit' AND v.evidence_role='program_fit'
      AND v.baseline_source_pack_id=p_pack AND v.promoted_source_pack_version=p_pack_version
      AND v.baseline_source_pack_version=1
      AND v.baseline_manifest_sha256='84350ea5705d9681d3e6550e1bd06e3340a9fcf0e7e7bbed4478ed3403405f28'
      AND v.baseline_raw_manifest_sha256='5d455d2c409c322e093f3a116387f3cef0fb7ea0f7357fec5e76e9da5b3a2a25'
  ) THEN RAISE EXCEPTION USING ERRCODE='NV011', MESSAGE='governed mixed approval is unavailable'; END IF;
  IF EXISTS (SELECT 1 FROM app.agent_tasks t WHERE t.organization_id=p_org AND t.case_id=p_case AND t.operation=p_operation AND t.case_revision=p_revision AND t.source_pack_id=p_pack AND t.source_pack_version=p_pack_version AND t.policy_version=p_policy AND t.state IN ('queued','leased','running','waiting_review','succeeded')) THEN RAISE EXCEPTION USING ERRCODE='NV009', MESSAGE='effective task already exists'; END IF;
  INSERT INTO app.agent_tasks(organization_id,id,case_id,operation,case_revision,source_pack_id,source_pack_version,policy_version,request_sha256,created_by_actor_id,state) VALUES(p_org,p_task,p_case,p_operation,p_revision,p_pack,p_pack_version,p_policy,p_request_hash,p_actor,'queued');
  INSERT INTO internal.agent_task_dispatch(task_id,organization_id,available_at) VALUES(p_task,p_org,clock_timestamp());
  PERFORM app.append_agent_task_event(p_org,p_task,'queued','preparing','queued',0,NULL);
  INSERT INTO app.idempotency_records VALUES(p_org,p_actor,'agent_task_create',p_key_hash,p_request_hash,'agent_task',p_task,clock_timestamp());
  SELECT * INTO selected FROM app.agent_tasks WHERE organization_id=p_org AND id=p_task;
  RETURN QUERY SELECT selected.id,selected.row_version,selected.state,selected.attempt_count,false;
END; $$;
"""

_0007_CLAIM_TASK_SQL = r"""
CREATE FUNCTION app.claim_agent_task(p_worker text) RETURNS TABLE(task_id uuid,organization_id uuid,lease_generation bigint) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE candidate record; selected app.agent_tasks%ROWTYPE; reclaimed boolean := false; next_attempt integer; next_generation bigint; new_expiry timestamptz; selected_adapter text; selected_adapter_version text;
BEGIN
  IF NULLIF(btrim(p_worker),'') IS NULL OR length(p_worker)>200 THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid worker identity'; END IF;
  SELECT d.task_id,d.organization_id INTO candidate FROM internal.agent_task_dispatch d WHERE d.available_at<=clock_timestamp() ORDER BY d.available_at,d.task_id FOR UPDATE SKIP LOCKED LIMIT 1;
  IF NOT FOUND THEN RETURN; END IF;
  PERFORM set_config('night_voyager.organization_id',candidate.organization_id::text,true);
  SELECT * INTO selected FROM app.agent_tasks t WHERE t.organization_id=candidate.organization_id AND t.id=candidate.task_id FOR UPDATE;
  IF NOT FOUND OR selected.state IN ('waiting_review','succeeded','blocked','timed_out','failed','cancelled') THEN DELETE FROM internal.agent_task_dispatch d WHERE d.organization_id=candidate.organization_id AND d.task_id=candidate.task_id; RETURN; END IF;
  IF selected.state IN ('leased','running') THEN
    IF selected.lease_expires_at>clock_timestamp() THEN UPDATE internal.agent_task_dispatch d SET available_at=selected.lease_expires_at WHERE d.organization_id=candidate.organization_id AND d.task_id=candidate.task_id; RETURN; END IF;
    reclaimed := true;
    IF selected.attempt_count>=3 THEN
      UPDATE app.agent_executions e SET status='failed',retryable=false,public_code='lease_expired',duration_ms=GREATEST(0,floor(extract(epoch FROM (clock_timestamp()-COALESCE(e.started_at,e.created_at)))*1000)::integer),finished_at=clock_timestamp() WHERE e.organization_id=selected.organization_id AND e.task_id=selected.id AND e.lease_generation=selected.lease_generation AND e.status IN ('leased','running');
      UPDATE app.agent_tasks t SET state='failed',row_version=t.row_version+1,lease_owner=NULL,lease_expires_at=NULL,terminal_code='lease_expired',updated_at=clock_timestamp() WHERE t.organization_id=selected.organization_id AND t.id=selected.id;
      DELETE FROM internal.agent_task_dispatch d WHERE d.organization_id=selected.organization_id AND d.task_id=selected.id;
      PERFORM app.append_agent_task_event(selected.organization_id,selected.id,'failed','failed','lease_expired',selected.attempt_count,NULL); RETURN;
    END IF;
    UPDATE app.agent_executions e SET status='retry_scheduled',retryable=true,public_code='lease_expired',duration_ms=GREATEST(0,floor(extract(epoch FROM (clock_timestamp()-COALESCE(e.started_at,e.created_at)))*1000)::integer),finished_at=clock_timestamp() WHERE e.organization_id=selected.organization_id AND e.task_id=selected.id AND e.lease_generation=selected.lease_generation AND e.status IN ('leased','running');
  ELSIF selected.state<>'queued' THEN RETURN; END IF;
  next_attempt := selected.attempt_count+1; next_generation := selected.lease_generation+1; new_expiry := clock_timestamp()+interval '60 seconds';
  selected_adapter := CASE selected.operation WHEN 'generate_planning_run_v1' THEN 'deterministic_planning' WHEN 'generate_governed_mixed_planning_run_v1' THEN 'governed_mixed_planning' ELSE NULL END;
  selected_adapter_version := CASE selected.operation WHEN 'generate_planning_run_v1' THEN 'm4a-v1' WHEN 'generate_governed_mixed_planning_run_v1' THEN 'dra-mixed-v1' ELSE NULL END;
  IF selected_adapter IS NULL THEN RAISE EXCEPTION USING ERRCODE='NV006', MESSAGE='invalid task operation'; END IF;
  UPDATE app.agent_tasks t SET state='leased',row_version=t.row_version+1,attempt_count=next_attempt,lease_owner=p_worker,lease_generation=next_generation,lease_expires_at=new_expiry,terminal_code=NULL,updated_at=clock_timestamp() WHERE t.organization_id=selected.organization_id AND t.id=selected.id;
  UPDATE internal.agent_task_dispatch d SET available_at=new_expiry WHERE d.organization_id=selected.organization_id AND d.task_id=selected.id;
  INSERT INTO app.agent_executions(organization_id,id,task_id,attempt_no,lease_generation,adapter_id,adapter_version,status,cost_status) VALUES(selected.organization_id,gen_random_uuid(),selected.id,next_attempt,next_generation,selected_adapter,selected_adapter_version,'leased','not_applicable');
  IF reclaimed THEN PERFORM app.append_agent_task_event(selected.organization_id,selected.id,'lease_reclaimed','preparing','lease_expired',next_attempt,NULL); END IF;
  PERFORM app.append_agent_task_event(selected.organization_id,selected.id,'lease_acquired','preparing','lease_acquired',next_attempt,NULL);
  RETURN QUERY SELECT selected.id,selected.organization_id,next_generation;
END; $$;
"""


def upgrade() -> None:
    _execute_statements(SCHEMA_SQL)
    _execute_statements(PIN_SQL)
    op.execute("ALTER TABLE app.agent_tasks NO FORCE ROW LEVEL SECURITY")
    _execute_statements(LEGACY_UPGRADE_SQL)
    op.execute("ALTER TABLE app.agent_tasks FORCE ROW LEVEL SECURITY")
    op.execute(
        "ALTER FUNCTION app.seed_demo_collaboration(uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,text) "
        "RENAME TO seed_demo_collaboration_0007"
    )
    _execute_statements(LEGACY_DEMO_TASK_SEED_SQL)
    op.execute(
        "DROP FUNCTION app.create_agent_task(uuid,uuid,uuid,uuid,text,integer,uuid,integer,text,text,text)"
    )
    op.execute("DROP FUNCTION app.claim_agent_task(text)")
    _execute_statements(MUTATION_SQL)
    _execute_statements(SEED_SQL)
    _execute_statements(PINNED_DEMO_TASK_SEED_SQL)
    _execute_statements(READ_SQL)
    _execute_statements(CREATE_TASK_SQL)
    _execute_statements(CLAIM_TASK_SQL)
    _execute_statements(PIN_GUARD_SQL)
    _execute_statements(PRIVILEGE_SQL)


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE app.{table} NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE app.agent_tasks NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE app.agent_executions NO FORCE ROW LEVEL SECURITY")

    op.execute(DOWNGRADE_GUARD_SQL)
    op.execute("ALTER TABLE app.agent_tasks FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE app.agent_executions FORCE ROW LEVEL SECURITY")

    op.execute(
        "DROP FUNCTION app.seed_demo_collaboration(uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,text)"
    )
    op.execute(
        "ALTER FUNCTION app.seed_demo_collaboration_0007(uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,text) "
        "RENAME TO seed_demo_collaboration"
    )

    op.execute(
        "DROP FUNCTION app.create_agent_task(uuid,uuid,uuid,uuid,text,integer,uuid,integer,text,jsonb,text,text)"
    )
    op.execute("DROP FUNCTION app.claim_agent_task(text)")
    op.execute("DROP FUNCTION app.load_persisted_synthetic_planning_snapshot(uuid,uuid,integer,uuid,integer,text)")
    op.execute("DROP FUNCTION app.load_agent_task_skill_pin(uuid,uuid,bigint)")
    op.execute("DROP FUNCTION app.inspect_planning_skill(uuid,uuid,uuid)")
    op.execute("DROP FUNCTION app.load_skill_candidate_context(uuid,uuid,uuid)")
    op.execute("DROP FUNCTION app.get_skill_catalog_item(uuid,uuid,text)")
    op.execute("DROP FUNCTION app.list_skill_catalog(uuid,uuid)")
    op.execute("DROP FUNCTION app.seed_demo_skill_registry(uuid,uuid,jsonb)")
    op.execute(
        "DROP FUNCTION app.seed_demo_pinned_collaboration_task(uuid,uuid,uuid,uuid,jsonb)"
    )
    op.execute(
        "DROP FUNCTION app.rollback_skill_activation(uuid,uuid,text,uuid,text,text,bigint,text,jsonb,text,text)"
    )
    op.execute(
        "DROP FUNCTION app.promote_skill_change_candidate(uuid,uuid,uuid,uuid,text,bigint,text,jsonb,text,text)"
    )
    op.execute(
        "DROP FUNCTION app.record_skill_candidate_evaluation(uuid,uuid,uuid,uuid,jsonb,text,text)"
    )
    op.execute(
        "DROP FUNCTION app.create_skill_change_candidate(uuid,uuid,text,uuid,text,text,text,text,jsonb,text,text)"
    )

    op.execute("DROP TRIGGER agent_executions_skill_pin_immutable ON app.agent_executions")
    op.execute("DROP TRIGGER agent_tasks_skill_pin_immutable ON app.agent_tasks")
    op.execute("DROP FUNCTION app.guard_agent_skill_pin()")
    op.execute("DROP INDEX app.agent_tasks_one_effective_operation")
    op.execute("ALTER TABLE app.agent_executions DROP CONSTRAINT agent_executions_task_skill_pin_fk")
    op.execute("ALTER TABLE app.agent_executions DROP CONSTRAINT agent_executions_skill_pin_all_or_none")
    op.execute("ALTER TABLE app.agent_executions DROP COLUMN runtime_binding_sha256")
    op.execute("ALTER TABLE app.agent_executions DROP COLUMN skill_activation_sequence")
    op.execute("ALTER TABLE app.agent_executions DROP COLUMN skill_activation_event_id")
    op.execute("ALTER TABLE app.agent_executions DROP COLUMN skill_version_id")
    op.execute("ALTER TABLE app.agent_executions DROP COLUMN skill_definition_id")
    op.execute("ALTER TABLE app.agent_tasks DROP CONSTRAINT agent_tasks_skill_pin_identity_unique")
    op.execute("ALTER TABLE app.agent_tasks DROP CONSTRAINT agent_tasks_skill_activation_fk")
    op.execute("ALTER TABLE app.agent_tasks DROP CONSTRAINT agent_tasks_skill_version_fk")
    op.execute("ALTER TABLE app.agent_tasks DROP CONSTRAINT agent_tasks_skill_pin_all_or_none")
    op.execute("ALTER TABLE app.agent_tasks DROP COLUMN runtime_binding_sha256")
    op.execute("ALTER TABLE app.agent_tasks DROP COLUMN skill_activation_sequence")
    op.execute("ALTER TABLE app.agent_tasks DROP COLUMN skill_activation_event_id")
    op.execute("ALTER TABLE app.agent_tasks DROP COLUMN skill_version_id")
    op.execute("ALTER TABLE app.agent_tasks DROP COLUMN skill_definition_id")
    op.execute(
        "CREATE UNIQUE INDEX agent_tasks_one_effective_operation ON app.agent_tasks(organization_id,case_id,operation,case_revision,source_pack_id,source_pack_version,policy_version) WHERE state IN ('queued','leased','running','waiting_review','succeeded')"
    )

    op.execute("DROP TABLE app.skill_activation_events")
    op.execute("DROP TABLE app.skill_evaluation_results")
    op.execute("DROP TABLE app.skill_change_candidates")
    op.execute("DROP TABLE app.skill_versions")
    op.execute("DROP TABLE app.skill_definitions")
    op.execute("DROP FUNCTION app.reject_skill_authority_mutation()")

    _execute_statements(_0007_CREATE_TASK_SQL)
    _execute_statements(_0007_CLAIM_TASK_SQL)
    op.execute(
        "REVOKE ALL ON FUNCTION app.create_agent_task(uuid,uuid,uuid,uuid,text,integer,uuid,integer,text,text,text) FROM PUBLIC"
    )
    op.execute("REVOKE ALL ON FUNCTION app.claim_agent_task(text) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION app.create_agent_task(uuid,uuid,uuid,uuid,text,integer,uuid,integer,text,text,text) TO night_voyager_api"
    )
    op.execute("GRANT EXECUTE ON FUNCTION app.claim_agent_task(text) TO night_voyager_worker")
