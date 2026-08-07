"""Synthetic identities available only in local and test environments."""

from __future__ import annotations

from dataclasses import dataclass, replace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.auth_service import PasswordHasher
from istari_service.management_seed import seed_management_grants
from istari_service.models import User, UserRole
from istari_service.organisation_models import (
    OrganisationKind,
    OrganisationUnit,
    UserOrganisationMembership,
)
from istari_service.organisation_seed import seed_organisation_units
from istari_service.team_membership_seed import seed_team_membership_history


@dataclass(frozen=True, slots=True)
class DemoIdentity:
    username: str
    display_name: str
    role: UserRole
    scope: str
    active: bool = True
    legacy_username: str | None = None
    unit_codes: tuple[str, ...] = ()


def _identity(
    display_name: str,
    role: UserRole,
    scope: str,
    *,
    legacy: str | None = None,
    units: tuple[str, ...] = (),
    active: bool = True,
) -> DemoIdentity:
    return DemoIdentity("", display_name, role, scope, active, legacy, units)


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
        "Requesting Area A",
        legacy="requester.1@example.test",
    ),
    _identity(
        "Billy Gilmour",
        UserRole.REQUESTER,
        "Requesting Area B",
        legacy="requester.2@example.test",
    ),
    _identity(
        "Scott McTominay",
        UserRole.INTAKE_TRIAGE,
        "JIOC",
        legacy="triage.1@example.test",
        units=("JIOC",),
    ),
    _identity(
        "Callum McGregor",
        UserRole.SERVICE_COORDINATION,
        "Shared command routing",
        legacy="coordination.2@example.test",
        units=("DIGOC", "SYGOC", "MYGOC"),
    ),
    _identity(
        "Kieran Tierney",
        UserRole.OPERATIONS_ALLOCATION,
        "Shared Ops routing",
        legacy="allocation.1@example.test",
    ),
    _identity(
        "Ryan Christie",
        UserRole.INTAKE_TRIAGE,
        "JIOC",
        legacy="triage.2@example.test",
        units=("JIOC",),
    ),
    _identity(
        "Grant Hanley",
        UserRole.DELIVERY_TEAM_LEAD,
        "OSG Team",
        legacy="delivery.lead.1@example.test",
        units=("OSG_TEAM",),
    ),
    _identity(
        "Kenny McLean",
        UserRole.DELIVERY_TEAM_LEAD,
        "OSG Team",
        legacy="delivery.lead.2@example.test",
        units=("OSG_TEAM",),
    ),
    _identity(
        "Craig Gordon",
        UserRole.OPERATIONS_ALLOCATION,
        "Shared Ops routing",
        legacy="allocation.2@example.test",
    ),
    _identity(
        "Lewis Ferguson",
        UserRole.DELIVERY_SPECIALIST,
        "OSG Team",
        legacy="specialist.1@example.test",
        units=("OSG_TEAM",),
    ),
    _identity(
        "Nathan Patterson",
        UserRole.DELIVERY_SPECIALIST,
        "OSG Team",
        legacy="specialist.2@example.test",
        units=("OSG_TEAM",),
    ),
    _identity(
        "Ben Doak",
        UserRole.DELIVERY_SPECIALIST,
        "OSG Team",
        legacy="specialist.3@example.test",
        units=("OSG_TEAM",),
    ),
    _identity(
        "Che Adams",
        UserRole.DELIVERY_SPECIALIST,
        "OSG Team",
        legacy="specialist.4@example.test",
        units=("OSG_TEAM",),
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
        "Requesting Area A",
        legacy="requester.disabled@example.test",
        active=False,
    ),
)

_ADDITIONAL_OSG_STAFF = (
    _identity(
        "Lawrence Shankland",
        UserRole.DELIVERY_TEAM_LEAD,
        "OSG Team",
        units=("OSG_TEAM",),
    ),
    _identity(
        "Tommy Conway",
        UserRole.DELIVERY_SPECIALIST,
        "OSG Team",
        units=("OSG_TEAM",),
    ),
    _identity(
        "Steve Clarke",
        UserRole.DELIVERY_SPECIALIST,
        "OSG Team",
        units=("OSG_TEAM",),
    ),
    _identity(
        "Derek McInnes",
        UserRole.DELIVERY_SPECIALIST,
        "OSG Team",
        units=("OSG_TEAM",),
    ),
)

_TEAM_STAFF_NAMES = (
    ("CEDAR_TEAM", "Cedar Team", "Kenny Dalglish", "Denis Law"),
    ("QUARTZ_TEAM", "Quartz Team", "Graeme Souness", "Alan Hansen"),
    ("LANTERN_TEAM", "Lantern Team", "Gordon Strachan", "Ally McCoist"),
    ("MOSAIC_TEAM", "Mosaic Team", "Darren Fletcher", "James McFadden"),
    ("COMPASS_TEAM", "Compass Team", "Barry Ferguson", "Paul McStay"),
    ("EMBER_TEAM", "Ember Team", "Gary McAllister", "John Collins"),
    ("ATLAS_TEAM", "Atlas Team", "Kevin Gallacher", "Colin Hendry"),
    ("HARBOUR_TEAM", "Harbour Team", "Alex McLeish", "Willie Miller"),
    ("BEACON_TEAM", "Beacon Team", "Joe Jordan", "Archie Gemmill"),
    ("SLATE_TEAM", "Slate Team", "Dave Mackay", "Billy Bremner"),
    ("ORCHARD_TEAM", "Orchard Team", "Jim Baxter", "Danny McGrain"),
    ("LUMEN_TEAM", "Lumen Team", "Jimmy Johnstone", "Bobby Lennox"),
    ("NORTHSTAR_TEAM", "Northstar Team", "John Greig", "Sandy Jardine"),
    ("COPPER_TEAM", "Copper Team", "Maurice Johnston", "Gordon Durie"),
    ("ROWAN_TEAM", "Rowan Team", "Stuart McCall", "Neil McCann"),
    ("VELA_TEAM", "Vela Team", "Don Hutchison", "Christian Dailly"),
    ("KEEL_TEAM", "Keel Team", "Gary Naysmith", "Lee McCulloch"),
    ("FLINT_TEAM", "Flint Team", "Steven Naismith", "Charlie Adam"),
    ("THISTLE_TEAM", "Thistle Team", "Robert Snodgrass", "Steven Fletcher"),
    ("GRANITE_TEAM", "Granite Team", "James Morrison", "Shaun Maloney"),
    ("KESTREL_TEAM", "Kestrel Team", "Barry Bannan", "David Marshall"),
    ("JUNIPER_TEAM", "Juniper Team", "Allan McGregor", "Stephen O'Donnell"),
    ("VALE_TEAM", "Vale Team", "Lyndon Dykes", "Ryan Porteous"),
    ("TIDAL_TEAM", "Tidal Team", "Jack Hendry", "Aaron Hickey"),
    ("GROVE_TEAM", "Grove Team", "Scott McKenna", "Greg Taylor"),
    ("PRISM_TEAM", "Prism Team", "Ryan Jack", "Stuart Armstrong"),
)


def _team_identities() -> tuple[DemoIdentity, ...]:
    identities: list[DemoIdentity] = []
    for code, name, manager, analyst in _TEAM_STAFF_NAMES:
        units = (code,)
        identities.extend(
            (
                _identity(manager, UserRole.DELIVERY_TEAM_LEAD, name, units=units),
                _identity(analyst, UserRole.DELIVERY_SPECIALIST, name, units=units),
            )
        )
    return tuple(identities)


_APPROVER_SCOPE = "Platform configuration approval"
DEMO_IDENTITIES = tuple(
    replace(identity, username=f"admin{index}")
    for index, identity in enumerate(
        (
            *_BASE_IDENTITIES,
            *_ADDITIONAL_OSG_STAFF,
            *_team_identities(),
            _identity("Jim Leighton", UserRole.PLATFORM_ADMIN, _APPROVER_SCOPE),
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
        if identity.username not in stored_by_username:
            user.display_name = identity.display_name
            user.password_hash = password_hash
            user.role = identity.role
            user.scope = identity.scope
            user.is_active = identity.active
            managed_usernames.add(identity.username)
        users[identity.username] = user
    await session.flush()
    await _seed_memberships(session, users, managed_usernames)
    await seed_management_grants(session)
    return created


async def _seed_memberships(
    session: AsyncSession,
    users: dict[str, User],
    managed_usernames: set[str],
) -> None:
    if not managed_usernames:
        return
    units = (
        await session.scalars(
            select(OrganisationUnit).where(OrganisationUnit.is_configured.is_(True))
        )
    ).all()
    unit_by_code = {unit.code: unit for unit in units}
    ops_codes = tuple(
        unit.code for unit in units if unit.kind is OrganisationKind.OPS_GROUP
    )
    desired_codes = {
        identity.username: (
            ops_codes
            if identity.role is UserRole.OPERATIONS_ALLOCATION
            else identity.unit_codes
        )
        for identity in DEMO_IDENTITIES
        if identity.username in managed_usernames
    }
    managed_user_ids = {users[username].id for username in managed_usernames}
    memberships = (
        await session.scalars(
            select(UserOrganisationMembership).where(
                UserOrganisationMembership.user_id.in_(managed_user_ids)
            )
        )
    ).all()
    existing = {(item.user_id, item.unit_id): item for item in memberships}
    desired = {
        (users[username].id, unit_by_code[code].id)
        for username, codes in desired_codes.items()
        for code in codes
    }
    for key in desired - existing.keys():
        session.add(UserOrganisationMembership(user_id=key[0], unit_id=key[1]))
    for key in existing.keys() - desired:
        await session.delete(existing[key])
    await session.flush()
    team_ids = {unit.id for unit in units if unit.kind is OrganisationKind.TEAM}
    await seed_team_membership_history(session, desired, team_ids)
