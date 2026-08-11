"""Authenticated self-profile HTTP boundary."""

from fastapi import APIRouter

from istari_service.dependencies import CurrentActor, DatabaseSession, MutationActor
from istari_service.repositories.profiles import SqlAlchemyProfileRepository
from istari_service.schemas.profiles import ProfileUpdate, ProfileView
from istari_service.services.profile_service import ProfileService

router = APIRouter(prefix="/profile", tags=["profile"])


def _service(session: DatabaseSession) -> ProfileService:
    return ProfileService(SqlAlchemyProfileRepository(session))


@router.get("", response_model=ProfileView)
async def get_profile(actor: CurrentActor, session: DatabaseSession) -> ProfileView:
    return await _service(session).get(actor)


@router.patch("", response_model=ProfileView)
async def update_profile(
    command: ProfileUpdate,
    actor: MutationActor,
    session: DatabaseSession,
) -> ProfileView:
    return await _service(session).update(actor, command)
