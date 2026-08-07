#!/usr/bin/env bash
set -Eeuo pipefail

image="postgres:17.9-bookworm@sha256:47f917f7409eacd22fc5dfb1dee634e1b55cf0c01d1a7eb701be2227a03e0641"
suffix="${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-0}-$$"
container_name="istari-postgres-component-${suffix}"

cleanup() {
  docker rm --force --volumes "$container_name" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker create \
  --name "$container_name" \
  --env POSTGRES_USER=postgres \
  --env POSTGRES_PASSWORD=validation-admin-password \
  --env POSTGRES_DB=postgres \
  --env APP_DATABASE_NAME=app_validation \
  --env APP_DATABASE_USER=app_validation_owner \
  --env APP_DATABASE_PASSWORD=validation-app-password \
  --env APP_RUNTIME_DATABASE_USER=app_validation \
  --env APP_RUNTIME_DATABASE_PASSWORD=validation-runtime-password \
  --env APP_BACKUP_DATABASE_USER=app_validation_backup \
  --env APP_BACKUP_DATABASE_PASSWORD=validation-backup-password \
  --env CAMUNDA_DATABASE_NAME=camunda_validation \
  --env CAMUNDA_DATABASE_USER=camunda_validation \
  --env CAMUNDA_DATABASE_PASSWORD=validation-camunda-password \
  "$image" >/dev/null
docker cp \
  infra/postgres/init-databases.sh \
  "${container_name}:/docker-entrypoint-initdb.d/10-init-databases.sh"
docker start "$container_name" >/dev/null

ready=false
for _ in $(seq 1 60); do
  if docker exec "$container_name" \
    pg_isready --host 127.0.0.1 --username postgres --dbname postgres \
    >/dev/null 2>&1; then
    ready=true
    break
  fi
  if [[ "$(docker inspect --format '{{.State.Status}}' "$container_name")" == "exited" ]]; then
    break
  fi
  sleep 1
done
if [[ "$ready" != true ]]; then
  docker logs "$container_name"
  echo "PostgreSQL component did not become ready." >&2
  exit 1
fi

role_result="$(docker exec \
  --env PGPASSWORD=validation-admin-password \
  "$container_name" psql \
  --host 127.0.0.1 --username postgres --dbname postgres \
  --tuples-only --no-align \
  --command "SELECT rolname || ':' || rolcanlogin || ':' || rolsuper || ':' || rolcreatedb || ':' || rolcreaterole || ':' || rolreplication FROM pg_roles WHERE rolname IN ('app_validation_owner', 'app_validation', 'app_validation_backup', 'camunda_validation') ORDER BY rolname")"
expected_roles=$'app_validation:true:false:false:false:false\napp_validation_backup:true:false:false:false:false\napp_validation_owner:true:false:false:false:false\ncamunda_validation:true:false:false:false:false'
if [[ "$role_result" != "$expected_roles" ]]; then
  printf 'Unexpected service roles:\n%s\n' "$role_result" >&2
  exit 1
fi

database_result="$(docker exec \
  --env PGPASSWORD=validation-admin-password \
  "$container_name" psql \
  --host 127.0.0.1 --username postgres --dbname postgres \
  --tuples-only --no-align \
  --command "SELECT datname || ':' || pg_get_userbyid(datdba) FROM pg_database WHERE datname IN ('app_validation', 'camunda_validation') ORDER BY datname")"
expected_databases=$'app_validation:app_validation_owner\ncamunda_validation:camunda_validation'
if [[ "$database_result" != "$expected_databases" ]]; then
  printf 'Unexpected service databases:\n%s\n' "$database_result" >&2
  exit 1
fi

if docker exec --env PGPASSWORD=validation-runtime-password "$container_name" \
  psql --host 127.0.0.1 --username app_validation \
  --dbname camunda_validation --command "SELECT 1" >/dev/null 2>&1; then
  echo "Application role unexpectedly connected to Camunda storage." >&2
  exit 1
fi

docker exec --env PGPASSWORD=validation-app-password "$container_name" \
  psql --host 127.0.0.1 --username app_validation_owner \
  --dbname app_validation --set=ON_ERROR_STOP=1 \
  --command "CREATE TABLE privilege_probe (id integer PRIMARY KEY);" >/dev/null
docker exec --env PGPASSWORD=validation-runtime-password "$container_name" \
  psql --host 127.0.0.1 --username app_validation \
  --dbname app_validation --set=ON_ERROR_STOP=1 \
  --command "INSERT INTO privilege_probe VALUES (1); UPDATE privilege_probe SET id = 2; DELETE FROM privilege_probe;" >/dev/null
docker exec --env PGPASSWORD=validation-backup-password "$container_name" \
  psql --host 127.0.0.1 --username app_validation_backup \
  --dbname app_validation --set=ON_ERROR_STOP=1 \
  --command "SELECT count(*) FROM privilege_probe;" >/dev/null
if docker exec --env PGPASSWORD=validation-backup-password "$container_name" \
  psql --host 127.0.0.1 --username app_validation_backup \
  --dbname app_validation --command "INSERT INTO privilege_probe VALUES (3)" \
  >/dev/null 2>&1; then
  echo "Backup role unexpectedly wrote application data." >&2
  exit 1
fi
if docker exec --env PGPASSWORD=validation-camunda-password "$container_name" \
  psql --host 127.0.0.1 --username camunda_validation \
  --dbname app_validation --command "SELECT 1" >/dev/null 2>&1; then
  echo "Camunda role unexpectedly connected to application storage." >&2
  exit 1
fi

echo "PostgreSQL bootstrap component validation passed."
