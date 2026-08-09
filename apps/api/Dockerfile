# syntax=docker/dockerfile:1.7

FROM ghcr.io/astral-sh/uv:0.11.26@sha256:3d868e555f8f1dbc324afa005066cd11e1053fc4743b9808ca8025283e65efa5 AS uv

FROM python:3.12-alpine3.23@sha256:601d3d3797e90e2534782e69c85fafb7971b43f24c7b1b079b7e48dd435e458d AS build

ENV PATH="/app/.venv/bin:$PATH" \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY --from=uv /uv /uvx /bin/
COPY apps/api/pyproject.toml apps/api/uv.lock apps/api/README.md ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-group dev --no-group test

COPY apps/api/alembic.ini ./
COPY apps/api/alembic ./alembic
COPY apps/api/src ./src

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-group dev --no-group test

FROM python:3.12-alpine3.23@sha256:601d3d3797e90e2534782e69c85fafb7971b43f24c7b1b079b7e48dd435e458d AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --gid 10001 app \
    && adduser --uid 10001 --ingroup app --disabled-password --no-create-home app \
    && rm -rf /usr/local/lib/python3.12/site-packages/pip \
        /usr/local/lib/python3.12/site-packages/pip-*.dist-info \
        /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.12

COPY --from=build --chown=10001:10001 /app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "istari_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
