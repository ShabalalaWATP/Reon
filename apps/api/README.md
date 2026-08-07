# ISTARI Service API

This package is the browser-facing FastAPI boundary for the synthetic ISTARI
service-request demonstration. PostgreSQL owns product data and the stable status
projection. Camunda owns process position and human user-task lifecycle.

## Local development

From the repository root, install every API dependency group:

```powershell
uv sync --project apps/api --all-groups
```

Copy the repository `.env.example` to `.env`, replace its placeholder values, and
then run migrations from this directory:

```powershell
uv run --directory apps/api --env-file ../../.env alembic upgrade head
```

Start only the API when its PostgreSQL and Camunda dependencies are already
available:

```powershell
uv run --directory apps/api --env-file ../../.env uvicorn istari_service.main:app --reload
```

The normal full-stack entry point is `docker compose up --build` from the
repository root.

The image migrates before starting Uvicorn for this single-instance local stack.
A replicated deployment must run Alembic once as a release or init job instead of
letting application replicas race the same schema upgrade.

## Quality checks

```powershell
uv run --directory apps/api pytest
uv run --directory apps/api ruff check .
uv run --directory apps/api ruff format --check .
uv run --directory apps/api mypy
uv run --directory apps/api bandit -c pyproject.toml -r src alembic
uv run --directory apps/api pip-audit
```

Pytest enforces at least 95 per cent coverage with branch measurement enabled.
Migrations require an explicit `DATABASE_URL`; no database credential is stored
in this package.
