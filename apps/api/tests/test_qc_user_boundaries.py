"""QC User review access stops before QC Manager release accountability."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

from conftest import ApiHarness
from in_memory_product_storage import InMemoryPrivateObjectStorage
from mist_service.action_notification_models import (
    NotificationAccessKind,
    NotificationEventGroup,
)
from mist_service.models import RequestStatus, ServiceRequest, User
from mist_service.product_errors import ProductNotFound
from mist_service.qc_membership import QC_TEAM_ID
from mist_service.repositories.actions import SqlAlchemyActionRepository
from mist_service.repositories.auth import actor_from_user_with_memberships
from mist_service.repositories.event_store import append_request_event
from mist_service.repositories.notification_projection import (
    RecipientRule,
    SqlAlchemyNotificationProjectionRepository,
)
from mist_service.repositories.notifications import SqlAlchemyNotificationRepository
from mist_service.repositories.products import SqlAlchemyProductRepository
from mist_service.request_notification_projection import recipient_rules_for
from mist_service.schemas.actions import ActionFilters
from mist_service.team_models import WorkspacePosition
from product_test_support import (
    RecordingAudit,
    add_claimed_quality_review_task,
    create_product_request,
    product_actors,
    product_service,
)


async def test_qc_user_can_inspect_review_package_but_not_release_package(
    api_harness: ApiHarness,
) -> None:
    requester, _other, _manager, analyst, _qc_manager = await product_actors(
        api_harness
    )
    request_id = await create_product_request(api_harness, requester, analyst)
    async with api_harness.sessions() as session, session.begin():
        user = await session.scalar(select(User).where(User.username == "admin102"))
        request = await session.get(ServiceRequest, request_id)
        assert user is not None and request is not None
        qc_user = await actor_from_user_with_memberships(session, user)
        repository = SqlAlchemyProductRepository(session)
        package = await repository.create_package(request_id, analyst.id, uuid4())
        request.status = RequestStatus.QUALITY_REVIEW
        await add_claimed_quality_review_task(session, request_id, qc_user.id)
        await session.flush()

        review_package = await product_service(
            session, InMemoryPrivateObjectStorage(), RecordingAudit()
        ).get_package(qc_user, package.id)
        assert review_package.id == package.id

        request.status = RequestStatus.READY_FOR_RELEASE
        await session.flush()
        with pytest.raises(ProductNotFound):
            await product_service(
                session, InMemoryPrivateObjectStorage(), RecordingAudit()
            ).get_package(qc_user, package.id)

        request.status = RequestStatus.COMPLETED
        await session.flush()
        with pytest.raises(ProductNotFound):
            await product_service(
                session, InMemoryPrivateObjectStorage(), RecordingAudit()
            ).get_package(qc_user, package.id)


async def test_qc_user_action_scope_stops_at_quality_review(
    api_harness: ApiHarness,
) -> None:
    requester, _other, _manager, analyst, _qc_manager = await product_actors(
        api_harness
    )
    request_id = await create_product_request(api_harness, requester, analyst)
    async with api_harness.sessions() as session, session.begin():
        user = await session.scalar(select(User).where(User.username == "admin102"))
        manager = await session.scalar(select(User).where(User.username == "admin15"))
        request = await session.get(ServiceRequest, request_id)
        assert user is not None and manager is not None and request is not None
        qc_user = await actor_from_user_with_memberships(session, user)
        qc_manager = await actor_from_user_with_memberships(session, manager)
        prior = request.status
        request.status = RequestStatus.QUALITY_REVIEW
        request.current_owner = "QC User or QC Manager"
        request.version += 1
        await append_request_event(
            session,
            request_id=request.id,
            actor_id=None,
            event_type="workflow_approve",
            message="Product sent for quality review.",
            prior_status=prior,
            next_status=request.status,
        )
        quality_actions, _ = await SqlAlchemyActionRepository(session).list_actions(
            qc_user, ActionFilters(), limit=20, cursor=None
        )
        assert {action.action_type for action in quality_actions} == {"QC_REVIEW"}

        prior = request.status
        request.status = RequestStatus.READY_FOR_RELEASE
        request.current_owner = "QC Manager"
        request.version += 1
        await append_request_event(
            session,
            request_id=request.id,
            actor_id=None,
            event_type="workflow_approve",
            message="Product approved for release.",
            prior_status=prior,
            next_status=request.status,
        )
        release_user_actions, _ = await SqlAlchemyActionRepository(
            session
        ).list_actions(qc_user, ActionFilters(), limit=20, cursor=None)
        release_manager_actions, _ = await SqlAlchemyActionRepository(
            session
        ).list_actions(qc_manager, ActionFilters(), limit=20, cursor=None)
        assert release_user_actions == []
        assert {action.action_type for action in release_manager_actions} == {
            "DISSEMINATE_PRODUCT"
        }


async def test_qc_notification_rules_distinguish_review_from_release(
    api_harness: ApiHarness,
) -> None:
    requester, _other, _manager, analyst, _qc_manager = await product_actors(
        api_harness
    )
    request_id = await create_product_request(api_harness, requester, analyst)
    async with api_harness.sessions() as session, session.begin():
        request = await session.get(ServiceRequest, request_id)
        assert request is not None
        request.status = RequestStatus.QUALITY_REVIEW
        review_rules = await recipient_rules_for(session, "TASK_ASSIGNED", request)
        assert len(review_rules) == 10
        assert all(
            rule.access_kind is NotificationAccessKind.ROUTE_MEMBER
            for rule in review_rules
        )
        assert all(rule.required_workspace_position is None for rule in review_rules)

        request.status = RequestStatus.READY_FOR_RELEASE
        release_rules = await recipient_rules_for(session, "TASK_ASSIGNED", request)
        assert len(release_rules) == 3
        assert all(
            rule.required_workspace_position is WorkspacePosition.MANAGER
            for rule in release_rules
        )


async def test_qc_user_receives_review_notification_but_not_manager_release_notice(
    api_harness: ApiHarness,
) -> None:
    requester, _other, _manager, analyst, _qc_manager = await product_actors(
        api_harness
    )
    request_id = await create_product_request(api_harness, requester, analyst)
    now = datetime.now(UTC)
    async with api_harness.sessions() as session, session.begin():
        user = await session.scalar(select(User).where(User.username == "admin102"))
        request = await session.get(ServiceRequest, request_id)
        assert user is not None and request is not None
        qc_user = await actor_from_user_with_memberships(session, user)
        request.status = RequestStatus.QUALITY_REVIEW
        projection = SqlAlchemyNotificationProjectionRepository(session)
        reads = SqlAlchemyNotificationRepository(session)

        review_event = await projection.publish_event(
            stable_key=f"qc-user-review:{request_id}",
            event_type="TASK_ASSIGNED",
            event_group=NotificationEventGroup.ASSIGNMENT,
            source_version=1,
            request_id=request_id,
            safe_subject="A synthetic QC review is ready.",
            deep_link=f"/requests/{request_id}",
            audience=[],
            occurred_at=now,
        )
        review_rule = RecipientRule(
            qc_user.id,
            NotificationAccessKind.ROUTE_MEMBER,
            qc_user.role,
            organisation_unit_id=QC_TEAM_ID,
        )
        assert (
            len(
                await projection.project_event(
                    review_event.id, [review_rule], projected_at=now
                )
            )
            == 1
        )
        visible, _ = await reads.list_notifications(
            qc_user,
            states=[],
            event_types=[],
            from_date=None,
            to_date=None,
            limit=20,
            cursor=None,
        )
        assert [event.id for _recipient, event in visible] == [review_event.id]

        release_event = await projection.publish_event(
            stable_key=f"qc-manager-release:{request_id}",
            event_type="TASK_ASSIGNED",
            event_group=NotificationEventGroup.RELEASE,
            source_version=2,
            request_id=request_id,
            safe_subject="A synthetic release is ready.",
            deep_link=f"/requests/{request_id}",
            audience=[],
            occurred_at=now,
        )
        manager_rule = RecipientRule(
            qc_user.id,
            NotificationAccessKind.ROUTE_MEMBER,
            qc_user.role,
            organisation_unit_id=QC_TEAM_ID,
            required_workspace_position=WorkspacePosition.MANAGER,
        )
        assert (
            await projection.project_event(
                release_event.id, [manager_rule], projected_at=now
            )
            == []
        )
