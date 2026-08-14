"""Authenticated release-capability discovery for graceful frontend rollback."""

from __future__ import annotations

from fastapi import APIRouter, Request
from starlette.routing import NoMatchFound

from istari_service.dependencies import AppSettings, CurrentSession
from istari_service.product_runtime import ProductRuntime
from istari_service.schemas.auth import ClientCapabilities

router = APIRouter(prefix="/me", tags=["capabilities"])


def _route_available(
    request: Request,
    name: str,
    **path_parameters: str,
) -> bool:
    """Report only capabilities implemented by this application composition."""
    try:
        request.app.url_path_for(name, **path_parameters)
    except NoMatchFound:
        return False
    return True


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
        conversation_reads=_route_available(
            request,
            "get_conversations",
            request_id="00000000-0000-0000-0000-000000000000",
        ),
        conversation_writes=_route_available(
            request,
            "post_conversation_message",
            request_id="00000000-0000-0000-0000-000000000000",
        ),
        context_switching=_route_available(
            request,
            "switch_context",
        ),
    )
