"""Management-scope and content-free analytics foundation evidence."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import func, select

from conftest import ApiHarness
from mist_service.admin_audit import verify_admin_audit_integrity
from mist_service.errors import (
    AdministrationAccessDenied,
    InvalidAdministrationChange,
    StaleVersion,
)
from mist_service.management_models import (
    ManagementAction,
    ManagementGrant,
    ManagementGrantAction,
    OrganisationClosure,
)
from mist_service.management_seed import management_grant_id
from mist_service.models import User
from mist_service.organisation_models import OrganisationUnit
from mist_service.repositories.management import (
    rebuild_organisation_closure,
    resolve_management_scope,
    scoped_unit_ids,
)
from mist_service.repositories.management_grants import (
    GrantDefinition,
    create_management_grant,
    revoke_management_grant,
    supersede_management_grant,
)


async def _user_and_unit(
    harness: ApiHarness,
    username: str,
    unit_code: str,
) -> tuple[UUID, UUID]:
    return await harness.user_id(username), await harness.unit_id(unit_code)


async def test_seeded_closure_and_grants_match_exact_management_authority(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    async with harness.sessions() as session:
        self_rows = await session.scalar(
            select(func.count())
            .select_from(OrganisationClosure)
            .where(OrganisationClosure.depth == 0)
        )
        ssg_id = await harness.unit_id("SSG_TEAM")
        crioc_id = await harness.unit_id("CRIOC")
        ncgi_id = await harness.unit_id("ACSA_B_OPS")
        depths = dict(
            (
                await session.execute(
                    select(OrganisationClosure.ancestor_id, OrganisationClosure.depth)
                    .where(OrganisationClosure.descendant_id == ssg_id)
                    .order_by(OrganisationClosure.depth)
                )
            ).all()
        )
        # Closure retains the non-routing Combined QC Team identity as well as
        # the 40 currently configured routing units.
        assert self_rows == 41
        assert depths[ssg_id] == 0
        assert depths[ncgi_id] == 1
        assert depths[crioc_id] == 3
        assert await session.scalar(select(func.count(ManagementGrant.id))) == 78

        qc_grant = await session.get(
            ManagementGrant,
            management_grant_id("admin15", "CRIOC"),
        )
        assert qc_grant is not None
        assert qc_grant.subject_user_id == await harness.user_id("admin15")
        assert qc_grant.root_unit_id == crioc_id
        assert qc_grant.include_descendants is True
        qc_actions = set(
            await session.scalars(
                select(ManagementGrantAction.action).where(
                    ManagementGrantAction.grant_id == qc_grant.id
                )
            )
        )
        assert qc_actions == {ManagementAction.STATISTICS}

        manager_id = await harness.user_id("admin8")
        manager_grant_id = management_grant_id("admin8", "SSG_TEAM")
        actions = set(
            await session.scalars(
                select(ManagementGrantAction.action).where(
                    ManagementGrantAction.grant_id == manager_grant_id
                )
            )
        )
        assert actions == set(ManagementAction)
        exact = await resolve_management_scope(
            session,
            subject_user_id=manager_id,
            grant_id=manager_grant_id,
            target_unit_id=ssg_id,
            action=ManagementAction.ROSTER,
        )
        assert exact is not None
        assert await scoped_unit_ids(session, exact) == (ssg_id,)


async def test_management_scope_denies_ancestor_sibling_action_and_inactive_grants(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    admin5_id, jock_id = await _user_and_unit(harness, "admin5", "JOCK")
    grant_id = management_grant_id("admin5", "JOCK")
    ssg_id = await harness.unit_id("SSG_TEAM")
    syogc_id = await harness.unit_id("SYGOC")
    crioc_id = await harness.unit_id("CRIOC")
    async with harness.sessions() as session, session.begin():
        root_scope = await resolve_management_scope(
            session,
            subject_user_id=admin5_id,
            grant_id=grant_id,
            target_unit_id=jock_id,
            action=ManagementAction.STATISTICS,
        )
        assert root_scope is not None
        assert ssg_id in await scoped_unit_ids(session, root_scope)
        assert (
            await resolve_management_scope(
                session,
                subject_user_id=admin5_id,
                grant_id=grant_id,
                target_unit_id=ssg_id,
                action=ManagementAction.STATISTICS,
            )
            is not None
        )
        for target, action in (
            (syogc_id, ManagementAction.STATISTICS),
            (crioc_id, ManagementAction.STATISTICS),
            (ssg_id, ManagementAction.ROSTER),
        ):
            assert (
                await resolve_management_scope(
                    session,
                    subject_user_id=admin5_id,
                    grant_id=grant_id,
                    target_unit_id=target,
                    action=action,
                )
                is None
            )
        user = await session.get(User, admin5_id)
        assert user is not None
        user.is_active = False
        await session.flush()
        assert (
            await resolve_management_scope(
                session,
                subject_user_id=admin5_id,
                grant_id=grant_id,
                target_unit_id=ssg_id,
                action=ManagementAction.STATISTICS,
            )
            is None
        )


async def test_expired_revoked_and_cycle_cases_fail_closed(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    subject_id = await harness.user_id("admin6")
    target_id = await harness.unit_id("SSG_TEAM")
    grant_id = management_grant_id("admin6", "ACSA_B_OPS")
    now = datetime.now(UTC)
    async with harness.sessions() as session, session.begin():
        grant = await session.get(ManagementGrant, grant_id)
        assert grant is not None
        grant.effective_until = now - timedelta(seconds=1)
        assert (
            await resolve_management_scope(
                session,
                subject_user_id=subject_id,
                grant_id=grant_id,
                target_unit_id=target_id,
                action=ManagementAction.STATISTICS,
                at=now,
            )
            is None
        )
    async with harness.sessions() as session, session.begin():
        jock = await session.scalar(
            select(OrganisationUnit).where(OrganisationUnit.code == "JOCK")
        )
        ncgi = await session.scalar(
            select(OrganisationUnit).where(OrganisationUnit.code == "ACSA_B_OPS")
        )
        assert jock is not None and ncgi is not None
        jock.parent_id = ncgi.id
        with pytest.raises(ValueError, match="cycle"):
            await rebuild_organisation_closure(session)


async def test_grant_lifecycle_requires_admin_version_reason_and_audit(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    administrator_id = await harness.user_id("admin1")
    subject_id = await harness.user_id("admin4")
    analyst_id = await harness.user_id("admin11")
    unit_id = await harness.unit_id("ACSA_B_OPS")
    definition = GrantDefinition(
        subject_user_id=subject_id,
        root_unit_id=unit_id,
        include_descendants=True,
        actions=frozenset({ManagementAction.BOARD}),
        effective_from=datetime.now(UTC) - timedelta(minutes=1),
        effective_until=datetime.now(UTC) + timedelta(days=7),
        reason="Temporary synthetic operational oversight.",
    )
    async with harness.sessions() as session, session.begin():
        with pytest.raises(AdministrationAccessDenied):
            await create_management_grant(
                session,
                actor_user_id=analyst_id,
                definition=definition,
            )
        grant = await create_management_grant(
            session,
            actor_user_id=administrator_id,
            definition=definition,
        )
        with pytest.raises(StaleVersion):
            await revoke_management_grant(
                session,
                actor_user_id=administrator_id,
                grant_id=grant.id,
                expected_version=99,
                reason="Authority is no longer required.",
            )
        with pytest.raises(InvalidAdministrationChange, match="reason"):
            await revoke_management_grant(
                session,
                actor_user_id=administrator_id,
                grant_id=grant.id,
                expected_version=grant.version,
                reason="short",
            )
        replacement = await supersede_management_grant(
            session,
            actor_user_id=administrator_id,
            grant_id=grant.id,
            expected_version=grant.version,
            definition=replace(
                definition,
                actions=frozenset({ManagementAction.CAPACITY}),
                reason="Authority adjusted for capacity oversight only.",
            ),
        )
        assert replacement.supersedes_grant_id == grant.id
        assert replacement.version == 2
        assert grant.revoked_at is not None and grant.version == 2
        assert await verify_admin_audit_integrity(session)
