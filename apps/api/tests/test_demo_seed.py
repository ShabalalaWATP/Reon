from __future__ import annotations

from collections import Counter
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from istari_service.auth_service import PasswordHasher
from istari_service.demo_seed import DEMO_IDENTITIES, seed_demo_users
from istari_service.models import Base, User, UserRole
from istari_service.organisation_models import (
    OrganisationKind,
    OrganisationUnit,
    StaffingStatus,
    UserOrganisationMembership,
)
from istari_service.organisation_seed import UNIT_DEFINITIONS, seed_organisation_units

TEST_SHARED_PASSWORD = "admin"  # nosec B105


class RecordingHasher(PasswordHasher):
    def __init__(self) -> None:
        self.hash_calls: list[str] = []

    def hash(self, password: str) -> str:
        self.hash_calls.append(password)
        return "synthetic-password-hash"


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def test_demo_identity_contract_covers_every_team() -> None:
    assert len(DEMO_IDENTITIES) == 73
    assert [identity.username for identity in DEMO_IDENTITIES] == [
        f"admin{number}" for number in range(1, 74)
    ]
    assert len({identity.display_name for identity in DEMO_IDENTITIES}) == 73
    assert Counter(identity.role for identity in DEMO_IDENTITIES) == {
        UserRole.PLATFORM_ADMIN: 2,
        UserRole.REQUESTER: 3,
        UserRole.INTAKE_TRIAGE: 2,
        UserRole.SERVICE_COORDINATION: 1,
        UserRole.OPERATIONS_ALLOCATION: 2,
        UserRole.DELIVERY_TEAM_LEAD: 29,
        UserRole.DELIVERY_SPECIALIST: 33,
        UserRole.QUALITY_RELEASE: 1,
    }
    disabled = [identity for identity in DEMO_IDENTITIES if not identity.active]
    assert [(identity.username, identity.display_name) for identity in disabled] == [
        ("admin16", "James Forrest")
    ]
    team_codes = {
        definition.code
        for definition in UNIT_DEFINITIONS
        if definition.kind is OrganisationKind.TEAM
    }
    for team_code in team_codes:
        team_staff = [
            identity for identity in DEMO_IDENTITIES if team_code in identity.unit_codes
        ]
        assert any(
            identity.role is UserRole.DELIVERY_TEAM_LEAD for identity in team_staff
        )
        assert any(
            identity.role is UserRole.DELIVERY_SPECIALIST for identity in team_staff
        )
    osg_staff = [
        identity for identity in DEMO_IDENTITIES if "OSG_TEAM" in identity.unit_codes
    ]
    assert Counter(identity.role for identity in osg_staff) == {
        UserRole.DELIVERY_TEAM_LEAD: 3,
        UserRole.DELIVERY_SPECIALIST: 7,
    }


@pytest.mark.asyncio
async def test_seeding_disabled_returns_without_validating_environment(
    db_session: AsyncSession,
) -> None:
    hasher = RecordingHasher()
    result = await seed_demo_users(
        db_session,
        hasher,
        environment="prod",
        enabled=False,
        shared_password=None,
    )
    assert result == 0
    assert hasher.hash_calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("environment", ["prod", "staging", "development"])
async def test_seeding_is_forbidden_outside_local_and_test(
    db_session: AsyncSession,
    environment: str,
) -> None:
    with pytest.raises(RuntimeError, match="forbidden outside local and test"):
        await seed_demo_users(
            db_session,
            RecordingHasher(),
            environment=environment,
            enabled=True,
            shared_password=TEST_SHARED_PASSWORD,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("shared_password", [None, "", "CHANGE_ME"])
async def test_seeding_rejects_missing_or_placeholder_password(
    db_session: AsyncSession,
    shared_password: str | None,
) -> None:
    with pytest.raises(RuntimeError, match="non-placeholder demo password"):
        await seed_demo_users(
            db_session,
            RecordingHasher(),
            environment="local",
            enabled=True,
            shared_password=shared_password,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("environment", ["local", "test"])
async def test_seeding_inserts_fixture_and_is_idempotent(
    db_session: AsyncSession,
    environment: str,
) -> None:
    hasher = RecordingHasher()
    first = await seed_demo_users(
        db_session,
        hasher,
        environment=environment,
        enabled=True,
        shared_password=TEST_SHARED_PASSWORD,
    )
    second = await seed_demo_users(
        db_session,
        hasher,
        environment=environment,
        enabled=True,
        shared_password=TEST_SHARED_PASSWORD,
    )
    stored = list((await db_session.scalars(select(User))).all())

    assert (first, second) == (73, 0)
    assert len(stored) == 73
    assert {user.username for user in stored} == {
        identity.username for identity in DEMO_IDENTITIES
    }
    assert all(user.password_hash == "synthetic-password-hash" for user in stored)
    assert [user.username for user in stored if not user.is_active] == ["admin16"]
    assert hasher.hash_calls == [TEST_SHARED_PASSWORD, TEST_SHARED_PASSWORD]


@pytest.mark.asyncio
async def test_seeded_memberships_staff_every_team_correctly(
    db_session: AsyncSession,
) -> None:
    await seed_demo_users(
        db_session,
        RecordingHasher(),
        environment="test",
        enabled=True,
        shared_password=TEST_SHARED_PASSWORD,
    )
    rows = (
        await db_session.execute(
            select(OrganisationUnit.code, User.role)
            .join(
                UserOrganisationMembership,
                UserOrganisationMembership.unit_id == OrganisationUnit.id,
            )
            .join(User, User.id == UserOrganisationMembership.user_id)
            .where(OrganisationUnit.kind == OrganisationKind.TEAM)
        )
    ).all()
    by_team: dict[str, Counter[UserRole]] = {}
    for team_code, role in rows:
        by_team.setdefault(team_code, Counter())[role] += 1
    assert len(by_team) == 27
    assert by_team["OSG_TEAM"] == Counter(
        {UserRole.DELIVERY_TEAM_LEAD: 3, UserRole.DELIVERY_SPECIALIST: 7}
    )
    for team_code, role_counts in by_team.items():
        if team_code != "OSG_TEAM":
            assert role_counts == Counter(
                {UserRole.DELIVERY_TEAM_LEAD: 1, UserRole.DELIVERY_SPECIALIST: 1}
            )


@pytest.mark.asyncio
async def test_legacy_username_is_renamed_without_changing_user_id(
    db_session: AsyncSession,
) -> None:
    legacy = User(
        username="platform.admin@example.test",
        display_name="Legacy profile",
        password_hash="legacy-hash",
        role=UserRole.REQUESTER,
        scope="Legacy scope",
        is_active=False,
    )
    db_session.add(legacy)
    await db_session.flush()
    legacy_id = legacy.id

    created = await seed_demo_users(
        db_session,
        RecordingHasher(),
        environment="test",
        enabled=True,
        shared_password=TEST_SHARED_PASSWORD,
    )

    migrated = await db_session.scalar(select(User).where(User.username == "admin1"))
    assert created == 72
    assert migrated is not None
    assert migrated.id == legacy_id
    assert (migrated.display_name, migrated.role, migrated.is_active) == (
        "Andy Robertson",
        UserRole.PLATFORM_ADMIN,
        True,
    )
    assert (
        await db_session.scalar(
            select(User).where(User.username == "platform.admin@example.test")
        )
        is None
    )


@pytest.mark.asyncio
async def test_reseeding_preserves_administrator_user_and_membership_edits(
    db_session: AsyncSession,
) -> None:
    hasher = RecordingHasher()
    await seed_demo_users(
        db_session,
        hasher,
        environment="test",
        enabled=True,
        shared_password=TEST_SHARED_PASSWORD,
    )
    user = await db_session.scalar(select(User).where(User.username == "admin8"))
    cedar = await db_session.scalar(
        select(OrganisationUnit).where(OrganisationUnit.code == "CEDAR_TEAM")
    )
    assert user is not None and cedar is not None
    memberships = list(
        (
            await db_session.scalars(
                select(UserOrganisationMembership).where(
                    UserOrganisationMembership.user_id == user.id
                )
            )
        ).all()
    )
    for membership in memberships:
        await db_session.delete(membership)
    db_session.add(UserOrganisationMembership(user_id=user.id, unit_id=cedar.id))
    user.display_name = "Administrator edited name"
    user.role = UserRole.REQUESTER
    user.scope = "Administrator edited scope"
    user.is_active = False
    user.password_hash = "administrator-managed-hash"
    await db_session.flush()

    await seed_demo_users(
        db_session,
        hasher,
        environment="test",
        enabled=True,
        shared_password=TEST_SHARED_PASSWORD,
    )
    await db_session.refresh(user)
    stored_unit_ids = set(
        (
            await db_session.scalars(
                select(UserOrganisationMembership.unit_id).where(
                    UserOrganisationMembership.user_id == user.id
                )
            )
        ).all()
    )
    assert (user.display_name, user.role, user.scope, user.is_active) == (
        "Administrator edited name",
        UserRole.REQUESTER,
        "Administrator edited scope",
        False,
    )
    assert user.password_hash == "administrator-managed-hash"
    assert stored_unit_ids == {cedar.id}


@pytest.mark.asyncio
async def test_organisation_reseed_preserves_admin_name_and_staffing_edits(
    db_session: AsyncSession,
) -> None:
    await seed_organisation_units(db_session)
    cedar = await db_session.scalar(
        select(OrganisationUnit).where(OrganisationUnit.code == "CEDAR_TEAM")
    )
    assert cedar is not None
    assert cedar.staffing_status is StaffingStatus.STAFFED
    cedar.name = "Administrator renamed team"
    cedar.staffing_status = StaffingStatus.UNSTAFFED
    await db_session.flush()

    await seed_organisation_units(db_session)
    await db_session.refresh(cedar)
    team_statuses = set(
        (
            await db_session.scalars(
                select(OrganisationUnit.staffing_status).where(
                    OrganisationUnit.kind == OrganisationKind.TEAM
                )
            )
        ).all()
    )
    assert cedar.name == "Administrator renamed team"
    assert cedar.staffing_status is StaffingStatus.UNSTAFFED
    assert team_statuses == {StaffingStatus.STAFFED, StaffingStatus.UNSTAFFED}
