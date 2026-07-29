# ruff: noqa: E501
"""Bind closed plan-execution demo principals to same-scenario rotation."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROTATE_SIGNATURE = (
    "auth.rotate_demo_session(bytea, bytea, text, uuid, bytea, bytea, timestamptz)"
)

ROTATE_0015_SQL = r"""
CREATE OR REPLACE FUNCTION auth.rotate_demo_session(
  p_old_digest bytea, p_old_csrf_digest bytea, p_demo_key text,
  p_session_id uuid, p_session_digest bytea,
  p_csrf_digest bytea, p_expires_at timestamptz
) RETURNS TABLE (organization_id uuid, actor_id uuid, role text, session_id uuid)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
  selected_old_principal auth.demo_principals%ROWTYPE;
  selected_new_principal auth.demo_principals%ROWTYPE;
  selected_session auth.demo_sessions%ROWTYPE;
  old_scope text;
  new_scope text;
BEGIN
  SELECT * INTO selected_session FROM auth.demo_sessions AS s
  WHERE s.session_digest = p_old_digest AND s.revoked_at IS NULL
    AND s.expires_at > clock_timestamp() FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION USING ERRCODE = 'NV001', MESSAGE = 'inactive session';
  END IF;
  IF selected_session.csrf_digest <> p_old_csrf_digest THEN
    RAISE EXCEPTION USING ERRCODE = 'NV002', MESSAGE = 'credential mismatch';
  END IF;

  SELECT * INTO selected_old_principal FROM auth.demo_principals AS p
  WHERE (p.organization_id,p.actor_id,p.role)=(
    selected_session.organization_id,selected_session.actor_id,selected_session.role
  );
  SELECT * INTO selected_new_principal FROM auth.demo_principals AS p
  WHERE p.demo_key = p_demo_key;
  IF selected_old_principal.demo_key IS NULL
     OR selected_new_principal.demo_key IS NULL
  THEN
    RAISE EXCEPTION USING ERRCODE = 'NV002', MESSAGE = 'credential mismatch';
  END IF;

  old_scope := CASE
    WHEN selected_old_principal.demo_key IN ('advisor','student','parent')
      THEN 'generic'
    WHEN selected_old_principal.demo_key IN (
      'plan_execution_happy_advisor',
      'plan_execution_happy_student',
      'plan_execution_happy_parent'
    ) THEN 'happy'
    WHEN selected_old_principal.demo_key IN (
      'plan_execution_blocked_advisor',
      'plan_execution_blocked_student',
      'plan_execution_blocked_parent'
    ) THEN 'blocked'
  END;
  new_scope := CASE
    WHEN selected_new_principal.demo_key IN ('advisor','student','parent')
      THEN 'generic'
    WHEN selected_new_principal.demo_key IN (
      'plan_execution_happy_advisor',
      'plan_execution_happy_student',
      'plan_execution_happy_parent'
    ) THEN 'happy'
    WHEN selected_new_principal.demo_key IN (
      'plan_execution_blocked_advisor',
      'plan_execution_blocked_student',
      'plan_execution_blocked_parent'
    ) THEN 'blocked'
  END;
  IF old_scope IS NULL
     OR new_scope IS NULL
     OR old_scope IS DISTINCT FROM new_scope
  THEN
    RAISE EXCEPTION USING ERRCODE = 'NV002', MESSAGE = 'credential mismatch';
  END IF;

  UPDATE auth.demo_sessions SET revoked_at = clock_timestamp()
  WHERE session_digest = p_old_digest;
  INSERT INTO auth.demo_sessions
    (id, organization_id, actor_id, role, session_digest, csrf_digest, expires_at)
  VALUES (
    p_session_id, selected_new_principal.organization_id,
    selected_new_principal.actor_id, selected_new_principal.role,
    p_session_digest, p_csrf_digest, p_expires_at
  );
  RETURN QUERY SELECT
    selected_new_principal.organization_id,
    selected_new_principal.actor_id,
    selected_new_principal.role,
    p_session_id;
END; $$;
"""

ROTATE_0014_SQL = r"""
CREATE OR REPLACE FUNCTION auth.rotate_demo_session(
  p_old_digest bytea, p_old_csrf_digest bytea, p_demo_key text,
  p_session_id uuid, p_session_digest bytea,
  p_csrf_digest bytea, p_expires_at timestamptz
) RETURNS TABLE (organization_id uuid, actor_id uuid, role text, session_id uuid)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
  selected_principal auth.demo_principals%ROWTYPE;
  selected_session auth.demo_sessions%ROWTYPE;
BEGIN
  SELECT * INTO selected_session FROM auth.demo_sessions AS s
  WHERE s.session_digest = p_old_digest AND s.revoked_at IS NULL
    AND s.expires_at > clock_timestamp() FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION USING ERRCODE = 'NV001', MESSAGE = 'inactive session';
  END IF;
  IF selected_session.csrf_digest <> p_old_csrf_digest THEN
    RAISE EXCEPTION USING ERRCODE = 'NV002', MESSAGE = 'credential mismatch';
  END IF;
  SELECT * INTO selected_principal FROM auth.demo_principals AS p WHERE p.demo_key = p_demo_key;
  IF NOT FOUND THEN RAISE EXCEPTION 'unknown demo principal'; END IF;
  UPDATE auth.demo_sessions SET revoked_at = clock_timestamp()
    WHERE session_digest = p_old_digest;
  INSERT INTO auth.demo_sessions
    (id, organization_id, actor_id, role, session_digest, csrf_digest, expires_at)
  VALUES (p_session_id, selected_principal.organization_id, selected_principal.actor_id,
          selected_principal.role, p_session_digest, p_csrf_digest, p_expires_at);
  RETURN QUERY SELECT selected_principal.organization_id, selected_principal.actor_id,
                      selected_principal.role, p_session_id;
END; $$;
"""

PRIVILEGE_SQL = (
    f"REVOKE ALL ON FUNCTION {ROTATE_SIGNATURE} FROM PUBLIC",
    f"GRANT EXECUTE ON FUNCTION {ROTATE_SIGNATURE} TO night_voyager_api",
)


def upgrade() -> None:
    op.execute("LOCK TABLE auth.demo_principals IN ACCESS EXCLUSIVE MODE")
    op.execute(
        "ALTER TABLE auth.demo_principals "
        "DROP CONSTRAINT demo_principals_demo_key_check"
    )
    op.execute(
        "ALTER TABLE auth.demo_principals "
        "ADD CONSTRAINT demo_principals_demo_key_check CHECK (demo_key IN ("
        "'advisor','student','parent',"
        "'plan_execution_happy_advisor',"
        "'plan_execution_happy_student',"
        "'plan_execution_happy_parent',"
        "'plan_execution_blocked_advisor',"
        "'plan_execution_blocked_student',"
        "'plan_execution_blocked_parent'))"
    )
    op.execute(
        "ALTER TABLE auth.demo_principals "
        "ADD CONSTRAINT demo_principals_identity_unique "
        "UNIQUE (organization_id,actor_id,role)"
    )
    op.execute(ROTATE_0015_SQL)
    for statement in PRIVILEGE_SQL:
        op.execute(statement)


def downgrade() -> None:
    op.execute("LOCK TABLE auth.demo_principals IN ACCESS EXCLUSIVE MODE")
    op.execute("LOCK TABLE auth.demo_sessions IN ACCESS EXCLUSIVE MODE")
    bind = op.get_bind()
    has_0015_identity = bool(
        bind.exec_driver_sql(
            "SELECT EXISTS("
            "SELECT 1 FROM auth.demo_principals "
            "WHERE demo_key NOT IN ('advisor','student','parent')"
            ") OR EXISTS("
            "SELECT 1 FROM auth.demo_sessions session_row "
            "WHERE NOT EXISTS("
            "SELECT 1 FROM auth.demo_principals principal "
            "WHERE principal.demo_key IN ('advisor','student','parent') "
            "AND (principal.organization_id,principal.actor_id,principal.role)="
            "(session_row.organization_id,session_row.actor_id,session_row.role)"
            "))"
        ).scalar_one()
    )
    if has_0015_identity:
        raise RuntimeError(
            "refusing downgrade: 0015 plan execution demo identity exists"
        )
    op.execute(ROTATE_0014_SQL)
    for statement in PRIVILEGE_SQL:
        op.execute(statement)
    op.execute(
        "ALTER TABLE auth.demo_principals "
        "DROP CONSTRAINT demo_principals_identity_unique"
    )
    op.execute(
        "ALTER TABLE auth.demo_principals "
        "DROP CONSTRAINT demo_principals_demo_key_check"
    )
    op.execute(
        "ALTER TABLE auth.demo_principals "
        "ADD CONSTRAINT demo_principals_demo_key_check "
        "CHECK (demo_key IN ('advisor','student','parent'))"
    )
