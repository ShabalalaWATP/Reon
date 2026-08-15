"""Translate official Camunda SDK failures into the workflow port errors."""

from __future__ import annotations

from collections.abc import Awaitable

import httpx
from camunda_orchestration_sdk import errors

from mist_service.workflow.errors import (
    WorkflowConflict,
    WorkflowContractError,
    WorkflowEngineUnavailable,
    WorkflowRequestRejected,
    WorkflowTaskNotFound,
)


async def call_camunda[T](operation: str, request: Awaitable[T]) -> T:
    try:
        return await request
    except errors.ConflictError as exc:
        raise WorkflowConflict(operation, exc.status_code) from exc
    except errors.NotFoundError as exc:
        raise WorkflowTaskNotFound(operation, exc.status_code) from exc
    except errors.ApiError as exc:
        if exc.status_code == 429 or exc.status_code >= 500:
            raise WorkflowEngineUnavailable(
                f"workflow operation {operation!r} is unavailable"
            ) from exc
        raise WorkflowRequestRejected(operation, exc.status_code) from exc
    except httpx.HTTPError as exc:
        raise WorkflowEngineUnavailable(
            f"workflow operation {operation!r} is unavailable"
        ) from exc
    except (KeyError, TypeError, ValueError) as exc:
        raise WorkflowContractError(
            f"workflow operation {operation!r} returned an invalid response"
        ) from exc
