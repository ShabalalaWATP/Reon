"""Authenticated self-profile HTTP boundary."""

from fastapi import APIRouter

from istari_service.dependencies import CurrentActor, DatabaseSession, MutationActor
from istari_service.profile_composition import build_profile_service
from istari_service.schemas.profiles import ProfileUpdate, ProfileView

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=ProfileView)
async def get_profile(actor: CurrentActor, session: DatabaseSession) -> ProfileView:
    return await build_profile_service(session).get(actor)


@router.patch("", response_model=ProfileView)
async def update_profile(
    command: ProfileUpdate,
    actor: MutationActor,
    session: DatabaseSession,
) -> ProfileView:
    return await build_profile_service(session).update(actor, command)
