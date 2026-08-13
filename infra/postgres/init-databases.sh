#!/usr/bin/env bash
set -Eeuo pipefail

required_variables=(
  POSTGRES_PASSWORD
  APP_DATABASE_NAME
  APP_DATABASE_USER
  APP_DATABASE_PASSWORD
  APP_RUNTIME_DATABASE_USER
  APP_RUNTIME_DATABASE_PASSWORD
  APP_BACKUP_DATABASE_USER
  APP_BACKUP_DATABASE_PASSWORD
  APP_MAINTENANCE_DATABASE_USER
  APP_MAINTENANCE_DATABASE_PASSWORD
  CAMUNDA_DATABASE_NAME
  CAMUNDA_DATABASE_USER
  CAMUNDA_DATABASE_PASSWORD
)

for variable_name in "${required_variables[@]}"; do
  if [[ -z "${!variable_name:-}" || "${!variable_name}" == "CHANGE_ME" ]]; then
    echo "Required database setting ${variable_name} is empty or a placeholder." >&2
    exit 1
  fi
done

identifiers=(
  "$APP_DATABASE_NAME"
  "$APP_DATABASE_USER"
  "$APP_RUNTIME_DATABASE_USER"
  "$APP_BACKUP_DATABASE_USER"
  "$APP_MAINTENANCE_DATABASE_USER"
  "$CAMUNDA_DATABASE_NAME"
  "$CAMUNDA_DATABASE_USER"
)
for identifier in "${identifiers[@]}"; do
  if [[ ! "$identifier" =~ ^[a-z][a-z0-9_]{0,62}$ ]]; then
    echo "Database names and users must use lower-case PostgreSQL identifiers." >&2
    exit 1
  fi
done

service_users=(
  "$APP_DATABASE_USER"
  "$APP_RUNTIME_DATABASE_USER"
  "$APP_BACKUP_DATABASE_USER"
  "$APP_MAINTENANCE_DATABASE_USER"
  "$CAMUNDA_DATABASE_USER"
)
if [[ "$(printf '%s\n' "${service_users[@]}" | sort -u | wc -l)" -ne 5 ]]; then
  echo "Migration, runtime, backup, maintenance and Camunda users must differ." >&2
  exit 1
fi
for service_user in "${service_users[@]}"; do
  if [[ "$service_user" == "$POSTGRES_USER" ]]; then
    echo "Service database users must not be the bootstrap superuser." >&2
    exit 1
  fi
done

passwords=(
  "$POSTGRES_PASSWORD"
  "$APP_DATABASE_PASSWORD"
  "$APP_RUNTIME_DATABASE_PASSWORD"
  "$APP_BACKUP_DATABASE_PASSWORD"
  "$APP_MAINTENANCE_DATABASE_PASSWORD"
  "$CAMUNDA_DATABASE_PASSWORD"
)
if [[ "$(printf '%s\n' "${passwords[@]}" | sort -u | wc -l)" -ne 6 ]]; then
  echo "Every database identity must use a distinct password." >&2
  exit 1
fi

if [[ "$APP_DATABASE_NAME" == "$CAMUNDA_DATABASE_NAME" ]]; then
  echo "Application and Camunda database names must differ." >&2
  exit 1
fi
if [[ "$APP_DATABASE_NAME" == "$POSTGRES_DB" || "$CAMUNDA_DATABASE_NAME" == "$POSTGRES_DB" ]]; then
  echo "Service databases must not reuse the bootstrap database." >&2
  exit 1
fi

psql \
  --set=ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set=app_database="$APP_DATABASE_NAME" \
  --set=app_user="$APP_DATABASE_USER" \
  --set=app_password="$APP_DATABASE_PASSWORD" \
  --set=runtime_user="$APP_RUNTIME_DATABASE_USER" \
  --set=runtime_password="$APP_RUNTIME_DATABASE_PASSWORD" \
  --set=backup_user="$APP_BACKUP_DATABASE_USER" \
  --set=backup_password="$APP_BACKUP_DATABASE_PASSWORD" \
  --set=maintenance_user="$APP_MAINTENANCE_DATABASE_USER" \
  --set=maintenance_password="$APP_MAINTENANCE_DATABASE_PASSWORD" \
  --set=camunda_database="$CAMUNDA_DATABASE_NAME" \
  --set=camunda_user="$CAMUNDA_DATABASE_USER" \
  --set=camunda_password="$CAMUNDA_DATABASE_PASSWORD" <<'SQL'
SELECT format(
  'CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION',
  role_name,
  role_password
)
FROM (
  VALUES
    (:'app_user', :'app_password'),
    (:'runtime_user', :'runtime_password'),
    (:'backup_user', :'backup_password'),
    (:'maintenance_user', :'maintenance_password'),
    (:'camunda_user', :'camunda_password')
) AS roles(role_name, role_password)
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = role_name) \gexec

SELECT format(
  'CREATE DATABASE %I OWNER %I ENCODING %L TEMPLATE template0',
  database_name,
  owner_name,
  'UTF8'
)
FROM (
  VALUES
    (:'app_database', :'app_user'),
    (:'camunda_database', :'camunda_user')
) AS databases(database_name, owner_name)
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = database_name) \gexec

SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', :'app_database') \gexec
SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', :'camunda_database') \gexec
SELECT format('GRANT CONNECT, TEMPORARY ON DATABASE %I TO %I', :'app_database', :'app_user') \gexec
SELECT format('GRANT CONNECT, TEMPORARY ON DATABASE %I TO %I', :'app_database', :'runtime_user') \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', :'app_database', :'backup_user') \gexec
SELECT format('GRANT CONNECT, TEMPORARY ON DATABASE %I TO %I', :'camunda_database', :'camunda_user') \gexec
SQL

psql \
  --set=ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$APP_DATABASE_NAME" \
  --set=app_user="$APP_DATABASE_USER" \
  --set=runtime_user="$APP_RUNTIME_DATABASE_USER" \
  --set=backup_user="$APP_BACKUP_DATABASE_USER" <<'SQL'
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO :"runtime_user", :"backup_user";
ALTER DEFAULT PRIVILEGES FOR ROLE :"app_user" IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"runtime_user";
ALTER DEFAULT PRIVILEGES FOR ROLE :"app_user" IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO :"runtime_user";
ALTER DEFAULT PRIVILEGES FOR ROLE :"app_user" IN SCHEMA public
  GRANT SELECT ON TABLES TO :"backup_user";
ALTER DEFAULT PRIVILEGES FOR ROLE :"app_user" IN SCHEMA public
  GRANT SELECT ON SEQUENCES TO :"backup_user";
SQL
