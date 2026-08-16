"""QC Users review; only QC Managers hold release accountability."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from conftest import ApiHarness
from mist_service.demo_seed import DEMO_IDENTITIES
from mist_service.models import RequestStatus, ServiceRequest, User, UserRole
from mist_service.qc_membership import (
    is_live_qc_manager,
    live_qc_manager_condition,
    live_qc_membership_condition,
)
from mist_service.repositories.auth import actor_from_user_with_memberships
from mist_service.repositories.work import SqlAlchemyWorkRepository
from mist_service.team_models import WorkspacePosition
from product_test_support import (
    add_claimed_quality_review_task,
    add_claimed_release_task,
    create_product_request,
    product_actors,
)

QC_USER = "admin102"
QC_MANAGER = "admin15"


def test_seed_provides_three_qc_managers_and_seven_qc_users() -> None:
    qc = [i for i in DEMO_IDENTITIES if i.role is UserRole.QUALITY_RELEASE]
    positions = [i.workspace_position for i in qc]
    assert positions.count(WorkspacePosition.MANAGER) == 3
    assert positions.count(WorkspacePosition.MEMBER) == 7
    assert all(i.unit_codes == ("QC_TEAM",) for i in qc)


async def test_qc_user_reviews_but_cannot_see_release_work(
    api_harness: ApiHarness,
) -> None:
    requester, _other, _manager, analyst, _qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    async with api_harness.sessions() as session, session.begin():
        user_row = await session.scalar(select(User).where(User.username == QC_USER))
        assert user_row is not None
        qc_user = await actor_from_user_with_memberships(session, user_row)
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        now = datetime.now(UTC)
        assert await session.scalar(
            select(live_qc_membership_condition(user_row.id, now))
        )
        assert not await session.scalar(
            select(live_qc_manager_condition(user_row.id, now))
        )
        assert not await is_live_qc_manager(session, user_row.id, at=now)
        work = SqlAlchemyWorkRepository(session, managed_products_enabled=True)

        request.status = RequestStatus.QUALITY_REVIEW
        await add_claimed_quality_review_task(session, request_id, qc_user.id)
        await session.flush()
        review_items = await work.list_for_actor(qc_user)
        assert [item.record.request.id for item in review_items] == [request_id]

        request.status = RequestStatus.READY_FOR_RELEASE
        await add_claimed_release_task(session, request_id, qc_user.id)
        await session.flush()
        release_items = await work.list_for_actor(qc_user)
        assert release_items == []


async def test_qc_manager_sees_both_review_and_release_work(
    api_harness: ApiHarness,
) -> None:
    requester, _other, _manager, analyst, _qc = await product_actors(api_harness)
    request_id = await create_product_request(api_harness, requester, analyst)
    async with api_harness.sessions() as session, session.begin():
        user_row = await session.scalar(select(User).where(User.username == QC_MANAGER))
        assert user_row is not None
        qc_manager = await actor_from_user_with_memberships(session, user_row)
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        assert await is_live_qc_manager(session, user_row.id, at=datetime.now(UTC))
        work = SqlAlchemyWorkRepository(session, managed_products_enabled=True)

        request.status = RequestStatus.QUALITY_REVIEW
        await add_claimed_quality_review_task(session, request_id, qc_manager.id)
        await session.flush()
        assert [i.record.request.id for i in await work.list_for_actor(qc_manager)] == [
            request_id
        ]

        request.status = RequestStatus.READY_FOR_RELEASE
        await add_claimed_release_task(session, request_id, qc_manager.id)
        await session.flush()
        assert [i.record.request.id for i in await work.list_for_actor(qc_manager)] == [
            request_id
        ]
