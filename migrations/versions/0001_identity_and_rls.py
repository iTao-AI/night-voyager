# ruff: noqa: E501
"""Create the M2 identity and row-security boundary."""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = r"""
CREATE SCHEMA app AUTHORIZATION night_voyager_migrator;
CREATE SCHEMA auth AUTHORIZATION night_voyager_migrator;
REVOKE ALL ON SCHEMA auth FROM PUBLIC;
GRANT USAGE ON SCHEMA app TO night_voyager_api, night_voyager_worker;
GRANT USAGE ON SCHEMA auth TO night_voyager_api;

CREATE TABLE app.organizations (
  id uuid PRIMARY KEY, name text NOT NULL UNIQUE,
  is_synthetic boolean NOT NULL DEFAULT true
);
CREATE TABLE app.actors (
  id uuid PRIMARY KEY, organization_id uuid NOT NULL,
  display_name text NOT NULL, is_synthetic boolean NOT NULL DEFAULT true,
  UNIQUE (organization_id, id),
  FOREIGN KEY (organization_id) REFERENCES app.organizations(id) ON DELETE CASCADE
);
CREATE TABLE app.memberships (
  id uuid PRIMARY KEY, organization_id uuid NOT NULL, actor_id uuid NOT NULL,
  role text NOT NULL CHECK (role IN ('advisor', 'student', 'parent')),
  UNIQUE (organization_id, actor_id, role),
  FOREIGN KEY (organization_id, actor_id)
    REFERENCES app.actors(organization_id, id) ON DELETE CASCADE
);
CREATE TABLE auth.demo_principals (
  demo_key text PRIMARY KEY CHECK (demo_key IN ('advisor', 'student', 'parent')),
  organization_id uuid NOT NULL, actor_id uuid NOT NULL,
  role text NOT NULL CHECK (role IN ('advisor', 'student', 'parent')),
  FOREIGN KEY (organization_id, actor_id, role)
    REFERENCES app.memberships(organization_id, actor_id, role) ON DELETE CASCADE
);
CREATE TABLE auth.demo_sessions (
  id uuid PRIMARY KEY, organization_id uuid NOT NULL, actor_id uuid NOT NULL,
  role text NOT NULL CHECK (role IN ('advisor', 'student', 'parent')),
  session_digest bytea NOT NULL UNIQUE, csrf_digest bytea NOT NULL,
  expires_at timestamptz NOT NULL, revoked_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  FOREIGN KEY (organization_id, actor_id, role)
    REFERENCES app.memberships(organization_id, actor_id, role) ON DELETE CASCADE
);

ALTER TABLE app.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.organizations FORCE ROW LEVEL SECURITY;
CREATE POLICY organizations_tenant_isolation ON app.organizations
  USING (id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid)
  WITH CHECK (id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid);
ALTER TABLE app.actors ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.actors FORCE ROW LEVEL SECURITY;
CREATE POLICY actors_tenant_isolation ON app.actors
  USING (organization_id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid)
  WITH CHECK (organization_id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid);
ALTER TABLE app.memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.memberships FORCE ROW LEVEL SECURITY;
CREATE POLICY memberships_tenant_isolation ON app.memberships
  USING (organization_id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid)
  WITH CHECK (organization_id = NULLIF(current_setting('night_voyager.organization_id', true), '')::uuid);
GRANT SELECT ON app.organizations, app.actors, app.memberships
  TO night_voyager_api, night_voyager_worker;

CREATE FUNCTION auth.mint_demo_session(
  p_demo_key text, p_session_id uuid, p_session_digest bytea,
  p_csrf_digest bytea, p_expires_at timestamptz
) RETURNS TABLE (organization_id uuid, actor_id uuid, role text, session_id uuid)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  IF p_expires_at <= clock_timestamp() THEN RAISE EXCEPTION 'invalid session expiry'; END IF;
  RETURN QUERY
  WITH principal AS (
    SELECT p.organization_id, p.actor_id, p.role
    FROM auth.demo_principals AS p WHERE p.demo_key = p_demo_key
  ), inserted AS (
    INSERT INTO auth.demo_sessions
      (id, organization_id, actor_id, role, session_digest, csrf_digest, expires_at)
    SELECT p_session_id, p.organization_id, p.actor_id, p.role,
           p_session_digest, p_csrf_digest, p_expires_at FROM principal AS p
    RETURNING auth.demo_sessions.organization_id, auth.demo_sessions.actor_id,
              auth.demo_sessions.role, auth.demo_sessions.id
  )
  SELECT inserted.organization_id, inserted.actor_id, inserted.role, inserted.id FROM inserted;
  IF NOT FOUND THEN RAISE EXCEPTION 'unknown demo principal'; END IF;
END; $$;

CREATE FUNCTION auth.resolve_demo_session(p_session_digest bytea)
RETURNS TABLE (organization_id uuid, actor_id uuid, role text, session_id uuid)
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
  SELECT s.organization_id, s.actor_id, s.role, s.id FROM auth.demo_sessions AS s
  WHERE s.session_digest = p_session_digest AND s.revoked_at IS NULL
    AND s.expires_at > clock_timestamp()
$$;

CREATE FUNCTION auth.rotate_demo_session(
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

CREATE FUNCTION auth.revoke_demo_session(
  p_session_digest bytea, p_csrf_digest bytea
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  UPDATE auth.demo_sessions SET revoked_at = clock_timestamp()
  WHERE session_digest = p_session_digest AND csrf_digest = p_csrf_digest
    AND revoked_at IS NULL;
  RETURN FOUND;
END; $$;

REVOKE ALL ON FUNCTION auth.mint_demo_session(text, uuid, bytea, bytea, timestamptz) FROM PUBLIC;
REVOKE ALL ON FUNCTION auth.resolve_demo_session(bytea) FROM PUBLIC;
REVOKE ALL ON FUNCTION auth.rotate_demo_session(bytea, bytea, text, uuid, bytea, bytea, timestamptz) FROM PUBLIC;
REVOKE ALL ON FUNCTION auth.revoke_demo_session(bytea, bytea) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION auth.mint_demo_session(text, uuid, bytea, bytea, timestamptz) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION auth.resolve_demo_session(bytea) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION auth.rotate_demo_session(bytea, bytea, text, uuid, bytea, bytea, timestamptz) TO night_voyager_api;
GRANT EXECUTE ON FUNCTION auth.revoke_demo_session(bytea, bytea) TO night_voyager_api;
"""


def upgrade() -> None:
    for statement in _split_statements(UPGRADE_SQL):
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP SCHEMA auth CASCADE")
    op.execute("DROP SCHEMA app CASCADE")


def _split_statements(sql: str) -> list[str]:
    """Split top-level SQL while preserving dollar-quoted function bodies."""
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
    remainder = "".join(buffer).strip()
    if remainder:
        statements.append(remainder)
    return statements
