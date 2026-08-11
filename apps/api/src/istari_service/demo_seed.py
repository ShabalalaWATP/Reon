"""Synthetic identities available only in local and test environments."""

from __future__ import annotations

from dataclasses import dataclass, replace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.auth_service import PasswordHasher
from istari_service.demo_membership_seed import seed_demo_memberships
from istari_service.demo_workspace_fixtures import (
    DELIVERY_IDENTITY_FIXTURES,
    SSG_IDENTITY_FIXTURES,
    ROUTING_IDENTITY_FIXTURES,
)
from istari_service.management_seed import seed_management_grants
from istari_service.models import User, UserRole
from istari_service.organisation_seed import seed_organisation_units
from istari_service.team_models import WorkspacePosition


@dataclass(frozen=True, slots=True)
class DemoIdentity:
    username: str
    display_name: str
    role: UserRole
    scope: str
    active: bool = True
    legacy_username: str | None = None
    unit_codes: tuple[str, ...] = ()
    workspace_position: WorkspacePosition = WorkspacePosition.MEMBER


def _identity(
    display_name: str,
    role: UserRole,
    scope: str,
    *,
    legacy: str | None = None,
    units: tuple[str, ...] = (),
    manager: bool = False,
    active: bool = True,
) -> DemoIdentity:
    return DemoIdentity(
        "",
        display_name,
        role,
        scope,
        active,
        legacy,
        units,
        WorkspacePosition.MANAGER if manager else WorkspacePosition.MEMBER,
    )


_BASE_IDENTITIES = (
    _identity(
        "Andy Robertson",
        UserRole.PLATFORM_ADMIN,
        "Platform support",
        legacy="platform.admin@example.test",
    ),
    _identity(
        "John McGinn",
        UserRole.REQUESTER,
        "Customer",
        legacy="requester.1@example.test",
    ),
    _identity(
        "Billy Gilmour",
        UserRole.REQUESTER,
        "Customer",
        legacy="requester.2@example.test",
    ),
    _identity(
        "Scott McTominay",
        UserRole.INTAKE_TRIAGE,
        "CRIOC",
        legacy="triage.1@example.test",
        units=("CRIOC",),
        manager=True,
    ),
    _identity(
        "Callum McGregor",
        UserRole.SERVICE_COORDINATION,
        "Shared request coordination",
        legacy="coordination.2@example.test",
        units=("JOCK", "SYGOC", "MYGOC"),
        manager=True,
    ),
    _identity(
        "Kieran Tierney",
        UserRole.OPERATIONS_ALLOCATION,
        "Shared Ops routing",
        legacy="allocation.1@example.test",
        units=(
            "ACSA_B_OPS",
            "AURORA_OPS",
            "VERTEX_OPS",
            "NIMBUS_OPS",
            "PARALLAX_OPS",
        ),
        manager=True,
    ),
    _identity(
        "Ryan Christie",
        UserRole.INTAKE_TRIAGE,
        "CRIOC",
        legacy="triage.2@example.test",
        units=("CRIOC",),
    ),
    _identity(
        "Grant Hanley",
        UserRole.DELIVERY_TEAM_LEAD,
        "SSG Team",
        legacy="delivery.lead.1@example.test",
        units=("SSG_TEAM",),
        manager=True,
    ),
    _identity(
        "Kenny McLean",
        UserRole.DELIVERY_TEAM_LEAD,
        "SSG Team",
        legacy="delivery.lead.2@example.test",
        units=("SSG_TEAM",),
        manager=True,
    ),
    _identity(
        "Craig Gordon",
        UserRole.OPERATIONS_ALLOCATION,
        "Shared Ops routing",
        legacy="allocation.2@example.test",
        units=("HORIZON_OPS", "MERIDIAN_OPS", "SOLSTICE_OPS", "FRONTIER_OPS"),
    ),
    _identity(
        "Lewis Ferguson",
        UserRole.DELIVERY_SPECIALIST,
        "SSG Team",
        legacy="specialist.1@example.test",
        units=("SSG_TEAM",),
    ),
    _identity(
        "Nathan Patterson",
        UserRole.DELIVERY_SPECIALIST,
        "SSG Team",
        legacy="specialist.2@example.test",
        units=("SSG_TEAM",),
    ),
    _identity(
        "Ben Doak",
        UserRole.DELIVERY_SPECIALIST,
        "SSG Team",
        legacy="specialist.3@example.test",
        units=("SSG_TEAM",),
    ),
    _identity(
        "Che Adams",
        UserRole.DELIVERY_SPECIALIST,
        "SSG Team",
        legacy="specialist.4@example.test",
        units=("SSG_TEAM",),
    ),
    _identity(
        "Angus Gunn",
        UserRole.QUALITY_RELEASE,
        "Shared QC",
        legacy="quality.1@example.test",
    ),
    _identity(
        "James Forrest",
        UserRole.REQUESTER,
        "Customer",
        legacy="requester.disabled@example.test",
        active=False,
    ),
)

_APPROVER_SCOPE = "Platform configuration approval"


DEMO_IDENTITIES = tuple(
    replace(identity, username=f"admin{index}")
    for index, identity in enumerate(
        (
            *_BASE_IDENTITIES,
            *(
                _identity(
                    fixture.display_name,
                    fixture.role,
                    fixture.scope,
                    units=(fixture.unit_code,),
                    manager=fixture.manager,
                )
                for fixture in SSG_IDENTITY_FIXTURES
            ),
            *(
                _identity(
                    fixture.display_name,
                    fixture.role,
                    fixture.scope,
                    units=(fixture.unit_code,),
                    manager=fixture.manager,
                )
                for fixture in DELIVERY_IDENTITY_FIXTURES
            ),
            _identity("Jim Leighton", UserRole.PLATFORM_ADMIN, _APPROVER_SCOPE),
            *(
                _identity(
                    fixture.display_name,
                    fixture.role,
                    fixture.scope,
                    units=(fixture.unit_code,),
                    manager=fixture.manager,
                )
                for fixture in ROUTING_IDENTITY_FIXTURES
            ),
        ),
        start=1,
    )
)


async def seed_demo_users(
    session: AsyncSession,
    password_hasher: PasswordHasher,
    *,
    environment: str,
    enabled: bool,
    shared_password: str | None,
    ensure_organisation: bool = True,
) -> int:
    """Insert fixtures or migrate legacy usernames without overwriting admin edits."""
    if not enabled:
        return 0
    if environment not in {"local", "test"}:
        raise RuntimeError("demo users are forbidden outside local and test")
    # The literal is a public placeholder marker, never an accepted credential.
    if not shared_password or shared_password == "CHANGE_ME":  # noqa: S105  # nosec B105
        raise RuntimeError("a non-placeholder demo password is required")
    if ensure_organisation:
        await seed_organisation_units(session)
    recognised_usernames = {
        username
        for identity in DEMO_IDENTITIES
        for username in (identity.username, identity.legacy_username)
        if username is not None
    }
    stored_by_username = {
        user.username: user
        for user in (
            await session.scalars(
                select(User).where(User.username.in_(recognised_usernames))
            )
        ).all()
    }
    password_hash = password_hasher.hash(shared_password)
    users: dict[str, User] = {}
    managed_usernames: set[str] = set()
    created = 0
    for identity in DEMO_IDENTITIES:
        user = stored_by_username.get(identity.username)
        legacy_user = stored_by_username.get(identity.legacy_username or "")
        if user is not None and legacy_user is not None and user.id != legacy_user.id:
            raise RuntimeError(
                f"both current and legacy demo users exist for {identity.username}"
            )
        if user is None:
            user = legacy_user
        if user is None:
            user = User(username=identity.username)
            session.add(user)
            created += 1
        else:
            user.username = identity.username
        if identity.username not in stored_by_username or not user.email:
            user.email = f"{identity.username}@istari.example.test"
        if identity.username not in stored_by_username:
            user.display_name = identity.display_name
            user.password_hash = password_hash
            user.role = identity.role
            user.scope = identity.scope
            user.is_active = identity.active
            managed_usernames.add(identity.username)
        users[identity.username] = user
    await session.flush()
    await seed_demo_memberships(
        session,
        users,
        managed_usernames,
        DEMO_IDENTITIES,
    )
    await seed_management_grants(session)
    return created
