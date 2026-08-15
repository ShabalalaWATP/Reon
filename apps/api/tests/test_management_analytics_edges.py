"""Fail-closed edge cases for management authority and projection sources."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select

from api_helpers import submit_request
from conftest import ApiHarness
from mist_service.analytics_projection import project_request_analytics
from mist_service.errors import InvalidAdministrationChange, ObjectNotFound
from mist_service.management_models import ManagementAction
from mist_service.management_seed import seed_management_grants
from mist_service.models import User
from mist_service.organisation_models import (
    OrganisationKind,
    OrganisationUnit,
    RequestRouteSelection,
    StaffingStatus,
)
from mist_service.repositories.management import (
    rebuild_organisation_closure,
    resolve_management_scope,
)
from mist_service.repositories.management_grants import (
    GrantDefinition,
    create_management_grant,
    revoke_management_grant,
)


async def test_projection_rejects_missing_request_and_route(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    with pytest.raises(LookupError, match="source does not exist"):
        async with harness.sessions() as session:
            await project_request_analytics(session, uuid4())
    request_id = UUID(await submit_request(harness))
    async with harness.sessions() as session, session.begin():
        await session.execute(
            delete(RequestRouteSelection).where(
                RequestRouteSelection.request_id == request_id
            )
        )
        with pytest.raises(RuntimeError, match="no root"):
            await project_request_analytics(session, request_id)


async def test_closure_rejects_a_missing_parent(api_harness: ApiHarness) -> None:
    async with api_harness.sessions() as session, session.begin():
        session.add(
            OrganisationUnit(
                code="BROKEN_OPS",
                name="Broken Ops",
                kind=OrganisationKind.OPS_GROUP,
                parent_id=uuid4(),
                staffing_status=StaffingStatus.ROUTING_POOL,
                routing_candidate_group="broken-ops-routing",
                manager_candidate_group=None,
                analyst_candidate_group=None,
            )
        )
        with pytest.raises(ValueError, match="missing parent"):
            await rebuild_organisation_closure(session)


async def test_seed_skips_missing_or_inactive_named_managers(
    api_harness: ApiHarness,
) -> None:
    async with api_harness.sessions() as session, session.begin():
        administrator = await session.scalar(
            select(User).where(User.username == "admin1")
        )
        named_manager = await session.scalar(
            select(User).where(User.username == "admin6")
        )
        assert administrator is not None and named_manager is not None
        named_manager.is_active = False
        await session.flush()
        assert await seed_management_grants(session) == 0
        administrator.username = "renamed-admin"
        await session.flush()
        assert await seed_management_grants(session) == 0


async def test_grant_validation_and_exact_scope_fail_closed(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    administrator_id = await harness.user_id("admin1")
    subject_id = await harness.user_id("admin4")
    root_id = await harness.unit_id("ACSA_B_OPS")
    child_id = await harness.unit_id("SSG_TEAM")
    base = GrantDefinition(
        subject_user_id=subject_id,
        root_unit_id=root_id,
        include_descendants=False,
        actions=frozenset({ManagementAction.STATISTICS}),
        effective_from=datetime.now(UTC),
        effective_until=datetime.now(UTC) + timedelta(days=1),
        reason="Synthetic exact-unit reporting authority.",
    )
    async with harness.sessions() as session, session.begin():
        for invalid in (
            replace(base, actions=frozenset()),
            replace(base, effective_from=datetime.now()),  # noqa: DTZ005
            replace(base, effective_until=base.effective_from),
            replace(base, subject_user_id=uuid4()),
        ):
            with pytest.raises(InvalidAdministrationChange):
                await create_management_grant(
                    session,
                    actor_user_id=administrator_id,
                    definition=invalid,
                )
        grant = await create_management_grant(
            session,
            actor_user_id=administrator_id,
            definition=base,
        )
        assert (
            await resolve_management_scope(
                session,
                subject_user_id=subject_id,
                grant_id=grant.id,
                target_unit_id=child_id,
                action=ManagementAction.STATISTICS,
                lock=True,
            )
            is None
        )
        with pytest.raises(ObjectNotFound):
            await revoke_management_grant(
                session,
                actor_user_id=administrator_id,
                grant_id=uuid4(),
                expected_version=1,
                reason="Synthetic authority was not found.",
            )
        revoked = await revoke_management_grant(
            session,
            actor_user_id=administrator_id,
            grant_id=grant.id,
            expected_version=grant.version,
            reason="Synthetic exact authority is no longer required.",
        )
        with pytest.raises(InvalidAdministrationChange, match="already inactive"):
            await revoke_management_grant(
                session,
                actor_user_id=administrator_id,
                grant_id=grant.id,
                expected_version=revoked.version,
                reason="Synthetic authority remains inactive.",
            )
