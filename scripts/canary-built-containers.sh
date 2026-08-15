#!/usr/bin/env sh
set -eu

suffix="$$"
network="mist-canary-$suffix"
api_container="mist-canary-api-$suffix"
web_container="mist-canary-web-$suffix"

cleanup() {
    docker rm --force "$web_container" "$api_container" >/dev/null 2>&1 || true
    docker network rm "$network" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

assert_non_root() {
    image="$1"
    user="$(docker image inspect "$image" --format '{{.Config.User}}')"
    case "$user" in
        ''|'0'|'0:0'|'root')
            echo "Built image runs as a root identity: $image" >&2
            exit 1
            ;;
    esac
}

api_command="$(docker image inspect mist-service-local-api --format '{{json .Config.Cmd}}')"
printf '%s' "$api_command" | grep -F -- '"--no-access-log"' >/dev/null
docker run --rm --network none --entrypoint sh mist-service-local-web \
    -c 'test "$(grep -c "access_log off;" /etc/nginx/conf.d/default.conf)" -eq 2'
docker run --rm --network none --entrypoint postgres \
    mist/postgres-local:17.10-pgvector0.8.1-alpine3.23 --version
docker run --rm --network none --entrypoint java \
    mist/camunda-local:8.9.14 -version
docker run --rm --network none --entrypoint clamscan \
    mist/clamav-local:1.5.3 --version

for image in \
    mist-service-local-api \
    mist-service-local-web \
    mist/postgres-local:17.10-pgvector0.8.1-alpine3.23 \
    mist/camunda-local:8.9.14 \
    mist/clamav-local:1.5.3
do
    assert_non_root "$image"
done

# Run the built API middleware behind the built Nginx proxy. The deliberately
# unmatched request carries independent markers in every raw access-log field.
# Only the fixed route classification may reach the API telemetry event.
docker network create --internal "$network" >/dev/null
docker run --detach --name "$api_container" --network "$network" \
    --network-alias api --read-only --tmpfs /tmp:mode=1777 \
    --entrypoint python mist-service-local-api -c \
    "import logging; logging.basicConfig(level=logging.INFO, format='%(message)s'); from starlette.applications import Starlette; from mist_service.telemetry import OperationalTelemetryMiddleware; import uvicorn; app=OperationalTelemetryMiddleware(Starlette()); uvicorn.run(app, host='0.0.0.0', port=8000, access_log=False)" \
    >/dev/null
docker run --detach --name "$web_container" --network "$network" \
    --read-only --tmpfs /tmp:uid=101,gid=101,mode=1777 \
    mist-service-local-web >/dev/null

attempt=0
until docker exec "$web_container" wget --quiet --spider http://127.0.0.1:8080/; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 30 ]; then
        echo 'Built web container did not become ready within 30 seconds.' >&2
        docker logs "$web_container" >&2 || true
        docker logs "$api_container" >&2 || true
        exit 1
    fi
    sleep 1
done

path_marker="canary-path-$suffix"
query_marker="canary-query-$suffix"
agent_marker="canary-agent-$suffix"
docker exec "$web_container" wget --quiet --output-document=/dev/null \
    --user-agent="$agent_marker" \
    "http://127.0.0.1:8080/api/$path_marker?probe=$query_marker" || true

attempt=0
api_logs=''
until api_logs="$(docker logs "$api_container" 2>&1)" && \
    printf '%s' "$api_logs" | grep -F '"event":"http_request"' >/dev/null; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 10 ]; then
        echo 'The built API emitted no minimised telemetry event.' >&2
        exit 1
    fi
    sleep 1
done
web_logs="$(docker logs "$web_container" 2>&1)"
combined_logs="$api_logs
$web_logs"
for marker in "$path_marker" "$query_marker" "$agent_marker"; do
    if printf '%s' "$combined_logs" | grep -F "$marker" >/dev/null; then
        echo "Raw request marker leaked into built-container logs: $marker" >&2
        exit 1
    fi
done
printf '%s' "$api_logs" | grep -F '"route":"unmatched"' >/dev/null
printf '%s' "$api_logs" | grep -F '"status":404' >/dev/null

echo 'Built-container canaries passed.'
