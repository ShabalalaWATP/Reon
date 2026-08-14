"""Effective-dated route recipient snapshots for request conversations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, update

from api_helpers import reach_delivery_work
from conftest import ApiHarness
from istari_service.conversation_models import RequestConversationDelivery
from istari_service.team_models import TeamMembership


async def test_route_snapshots_exclude_scheduled_and_expired_members(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    request_id = await reach_delivery_work(harness)
    expired_member_id = await harness.user_id("admin7")
    scheduled_member_id = await harness.user_id("admin75")
    await harness.login("admin11")
    workspace = await harness.client.get(f"/api/v1/requests/{request_id}/conversations")
    assert workspace.status_code == 200
    crioc = next(
        target
        for target in workspace.json()["allowedTargets"]
        if target["type"] == "ROUTE_UNIT" and target["label"] == "CRIOC"
    )
    now = datetime.now(UTC)
    async with harness.sessions() as session, session.begin():
        await session.execute(
            update(TeamMembership)
            .where(
                TeamMembership.user_id == expired_member_id,
                TeamMembership.team_id == UUID(crioc["unitId"]),
                TeamMembership.effective_until.is_(None),
            )
            .values(effective_until=now)
        )
        await session.execute(
            update(TeamMembership)
            .where(
                TeamMembership.user_id == scheduled_member_id,
                TeamMembership.team_id == UUID(crioc["unitId"]),
                TeamMembership.effective_until.is_(None),
            )
            .values(effective_from=now + timedelta(days=1))
        )

    created = await harness.client.post(
        f"/api/v1/requests/{request_id}/conversations/messages",
        json={
            "body": "Only current CRIOC members may receive this synthetic note.",
            "clientMutationId": str(uuid4()),
            "targetType": "ROUTE_UNIT",
            "targetUnitId": crioc["unitId"],
        },
        headers=harness.mutation_headers(),
    )
    assert created.status_code == 200, created.text
    message_id = UUID(created.json()["conversation"]["messages"][0]["id"])
    async with harness.sessions() as session:
        recipient_ids = set(
            await session.scalars(
                select(RequestConversationDelivery.recipient_user_id).where(
                    RequestConversationDelivery.message_id == message_id
                )
            )
        )
    assert recipient_ids
    assert expired_member_id not in recipient_ids
    assert scheduled_member_id not in recipient_ids
