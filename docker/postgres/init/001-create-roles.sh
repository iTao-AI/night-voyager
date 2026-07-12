#!/bin/sh
set -eu

: "${NIGHT_VOYAGER_MIGRATOR_PASSWORD:=migrator-local-only}"
: "${NIGHT_VOYAGER_API_PASSWORD:=api-local-only}"
: "${NIGHT_VOYAGER_WORKER_PASSWORD:=worker-local-only}"

psql --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=migrator_password="$NIGHT_VOYAGER_MIGRATOR_PASSWORD" \
  --set=api_password="$NIGHT_VOYAGER_API_PASSWORD" \
  --set=worker_password="$NIGHT_VOYAGER_WORKER_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE night_voyager_migrator LOGIN PASSWORD %L', :'migrator_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'night_voyager_migrator') \gexec
SELECT format('CREATE ROLE night_voyager_api LOGIN PASSWORD %L', :'api_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'night_voyager_api') \gexec
SELECT format('CREATE ROLE night_voyager_worker LOGIN PASSWORD %L', :'worker_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'night_voyager_worker') \gexec

ALTER ROLE night_voyager_migrator PASSWORD :'migrator_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
ALTER ROLE night_voyager_api PASSWORD :'api_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
ALTER ROLE night_voyager_worker PASSWORD :'worker_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
SELECT format('ALTER DATABASE %I OWNER TO night_voyager_migrator', current_database()) \gexec
SELECT format(
  'GRANT CONNECT ON DATABASE %I TO night_voyager_api, night_voyager_worker',
  current_database()
) \gexec
SQL
