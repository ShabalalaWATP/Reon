"""Authenticated release-capability discovery for graceful frontend rollback."""

from __future__ import annotations

from fastapi import APIRouter, Request

from istari_service.dependencies import AppSettings, CurrentSession
from istari_service.product_runtime import ProductRuntime
from istari_service.schemas.auth import ClientCapabilities

router = APIRouter(prefix="/me", tags=["capabilities"])


@router.get("/capabilities", response_model=ClientCapabilities)
async def capabilities(
    request: Request,
    _session: CurrentSession,
    settings: AppSettings,
) -> ClientCapabilities:
    runtime = getattr(request.app.state, "product_runtime", None)
    return ClientCapabilities(
        my_work=settings.action_workspace_enabled,
        notifications=settings.notifications_enabled,
        configuration=settings.configuration_admin_enabled,
        products=settings.managed_products_enabled,
        managed_file_uploads=(
            isinstance(runtime, ProductRuntime) and runtime.managed_file_uploads_enabled
        ),
        planning=settings.planning_evolution_enabled,
        statistics=settings.statistics_evolution_enabled,
    )
