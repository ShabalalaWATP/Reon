"""Public marking read and elevated Platform Administrator mutation."""

from fastapi import APIRouter

from istari_service.dependencies import DatabaseSession, ElevatedMutationActor
from istari_service.repositories.platform_security import (
    SqlAlchemyPlatformSecurityRepository,
)
from istari_service.schemas.platform_security import (
    PlatformClassificationUpdate,
    PlatformClassificationView,
)
from istari_service.services.platform_security_service import PlatformSecurityService

router = APIRouter(tags=["platform-security"])


def _service(session: DatabaseSession) -> PlatformSecurityService:
    return PlatformSecurityService(SqlAlchemyPlatformSecurityRepository(session))


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
