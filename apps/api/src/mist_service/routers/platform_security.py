"""Public marking read and elevated Platform Administrator mutation."""

from fastapi import APIRouter

from mist_service.dependencies import DatabaseSession, ElevatedMutationActor
from mist_service.platform_security_composition import platform_security_service
from mist_service.schemas.platform_security import (
    PlatformClassificationUpdate,
    PlatformClassificationView,
)
from mist_service.services.platform_security_service import PlatformSecurityService

router = APIRouter(tags=["platform-security"])


def _service(session: DatabaseSession) -> PlatformSecurityService:
    return platform_security_service(session)


@router.get(
    "/platform/classification",
    response_model=PlatformClassificationView,
)
async def classification(session: DatabaseSession) -> PlatformClassificationView:
    return await _service(session).classification()


@router.patch(
    "/admin/platform/classification",
    response_model=PlatformClassificationView,
)
async def update_classification(
    command: PlatformClassificationUpdate,
    actor: ElevatedMutationActor,
    session: DatabaseSession,
) -> PlatformClassificationView:
    return await _service(session).update_classification(actor, command)
