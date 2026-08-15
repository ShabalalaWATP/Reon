"""Seed deterministic, non-sensitive data for the agreed local load rehearsal."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from secrets import token_urlsafe
from uuid import NAMESPACE_URL, UUID, uuid5

from performance_request_fixture import seed_request_feeds
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.auth_service import PasswordHasher
from mist_service.board_models import (
    WorkPackage,
    WorkPackageActivity,
    WorkPackageActivityType,
    WorkPackagePriority,
    WorkPackageStatus,
)
from mist_service.calendar_models import (
    CalendarCategory,
    CalendarEvent,
    CalendarEventKind,
    CalendarEventStatus,
    CalendarVisibility,
    CommitmentStatus,
    RecurrenceFrequency,
)
from mist_service.database import session_scope
from mist_service.models import User, UserRole
from mist_service.organisation_models import OrganisationUnit
from mist_service.team_models import TeamMembership

FIXTURE_NAMESPACE = "https://mist.example/performance/"
SSG_CODE = "SSG_TEAM"


def fixture_id(kind: str, sequence: int) -> UUID:
    return uuid5(NAMESPACE_URL, f"{FIXTURE_NAMESPACE}{kind}/{sequence}")


async def seed_active_users(session: AsyncSession, target: int) -> int:
    active_count = await session.scalar(
        select(func.count()).select_from(User).where(User.is_active.is_(True))
    )
    needed = max(0, target - int(active_count or 0))
    if not needed:
        return 0
    inaccessible_hash = PasswordHasher().hash(token_urlsafe(48))
    session.add_all(
        User(
            id=fixture_id("user", sequence),
            username=f"performance-fixture-{sequence:03d}",
            display_name=f"Performance Fixture {sequence:03d}",
            password_hash=inaccessible_hash,
            role=UserRole.REQUESTER,
            scope="Performance rehearsal fixture",
            is_active=True,
        )
        for sequence in range(1, needed + 1)
    )
    await session.flush()
    return needed


async def ssg_staff(session: AsyncSession) -> tuple[UUID, UUID, list[UUID]]:
    rows = (
        await session.execute(
            select(OrganisationUnit.id, User.id, User.role)
            .join(TeamMembership, TeamMembership.team_id == OrganisationUnit.id)
            .join(User, User.id == TeamMembership.user_id)
            .where(
                OrganisationUnit.code == SSG_CODE,
                TeamMembership.effective_until.is_(None),
                User.is_active.is_(True),
            )
            .order_by(User.username)
        )
    ).all()
    managers = [
        user_id for _, user_id, role in rows if role == UserRole.DELIVERY_TEAM_LEAD
    ]
    analysts = [
        user_id for _, user_id, role in rows if role == UserRole.DELIVERY_SPECIALIST
    ]
    if not rows or not managers or not analysts:
        raise RuntimeError("SSG Team requires at least one active Manager and Analyst")
    return rows[0][0], managers[0], analysts


async def existing_ids(
    session: AsyncSession,
    model: type[WorkPackage | CalendarEvent],
    ids: list[UUID],
) -> set[UUID]:
    found: set[UUID] = set()
    for offset in range(0, len(ids), 500):
        found.update(
            (
                await session.scalars(
                    select(model.id).where(model.id.in_(ids[offset : offset + 500]))
                )
            ).all()
        )
    return found


async def seed_packages(
    session: AsyncSession,
    *,
    target: int,
    team_id: UUID,
    manager_id: UUID,
    analysts: list[UUID],
) -> int:
    ids = [fixture_id("package", sequence) for sequence in range(1, target + 1)]
    found = await existing_ids(session, WorkPackage, ids)
    added = 0
    for sequence, package_id in enumerate(ids, start=1):
        if package_id in found:
            continue
        owner_id = analysts[(sequence - 1) % len(analysts)]
        session.add(
            WorkPackage(
                id=package_id,
                team_id=team_id,
                linked_request_id=None,
                iteration_id=None,
                title=f"Performance rehearsal package {sequence:04d}",
                description=(
                    "Synthetic package used only for bounded local load evidence."
                ),
                owner_user_id=owner_id,
                estimate_points=(sequence % 13) + 1,
                remaining_effort_minutes=(sequence % 16) * 30,
                due_on=date(2026, 8, 1) + timedelta(days=sequence % 30),
                priority=list(WorkPackagePriority)[sequence % 4],
                status=list(WorkPackageStatus)[sequence % 5],
                blockers="None recorded.",
                acceptance_criteria=(
                    "The bounded read returns an authorised projection."
                ),
                created_by_user_id=manager_id,
            )
        )
        session.add(
            WorkPackageActivity(
                id=fixture_id("package-activity", sequence),
                package_id=package_id,
                team_id=team_id,
                actor_user_id=manager_id,
                type=WorkPackageActivityType.CREATED,
                summary="Created for the performance rehearsal.",
                details={"fixture": True},
            )
        )
        added += 1
    await session.flush()
    return added


async def seed_calendar(
    session: AsyncSession,
    *,
    target: int,
    team_id: UUID,
    manager_id: UUID,
    analysts: list[UUID],
) -> int:
    ids = [fixture_id("calendar", sequence) for sequence in range(1, target + 1)]
    found = await existing_ids(session, CalendarEvent, ids)
    added = 0
    start = datetime(2026, 8, 1, 8, tzinfo=UTC)
    for sequence, event_id in enumerate(ids, start=1):
        if event_id in found:
            continue
        starts_at = start + timedelta(days=sequence % 13, minutes=sequence % 480)
        session.add(
            CalendarEvent(
                id=event_id,
                subject_user_id=analysts[(sequence - 1) % len(analysts)],
                team_id=team_id,
                created_by_user_id=manager_id,
                kind=CalendarEventKind.TEAM,
                category=CalendarCategory.SERVICE_WORK,
                visibility=CalendarVisibility.TEAM_DETAIL,
                title=f"Performance rehearsal calendar entry {sequence:04d}",
                notes="Synthetic calendar data for bounded local load evidence.",
                starts_at=starts_at,
                ends_at=starts_at + timedelta(minutes=30),
                time_zone="Europe/London",
                all_day=False,
                recurrence=RecurrenceFrequency.NONE,
                recurrence_interval=1,
                recurrence_until=None,
                status=CalendarEventStatus.ACTIVE,
                commitment_status=CommitmentStatus.NOT_REQUIRED,
                commitment_reason=None,
            )
        )
        added += 1
    await session.flush()
    return added


async def run(args: argparse.Namespace) -> dict[str, bool | int | str]:
    async with session_scope() as session:
        team_id, manager_id, analysts = await ssg_staff(session)
        users_added = await seed_active_users(session, args.active_users)
        packages_added = await seed_packages(
            session,
            target=args.packages,
            team_id=team_id,
            manager_id=manager_id,
            analysts=analysts,
        )
        calendar_added = await seed_calendar(
            session,
            target=args.calendar_occurrences,
            team_id=team_id,
            manager_id=manager_id,
            analysts=analysts,
        )
        request_feeds = await seed_request_feeds(session, args.request_feed_rows)
        active_user_count = int(
            await session.scalar(
                select(func.count()).select_from(User).where(User.is_active.is_(True))
            )
            or 0
        )
        package_fixture_count = int(
            await session.scalar(
                select(func.count())
                .select_from(WorkPackage)
                .where(WorkPackage.title.like("Performance rehearsal package %"))
            )
            or 0
        )
        calendar_fixture_count = int(
            await session.scalar(
                select(func.count())
                .select_from(CalendarEvent)
                .where(
                    CalendarEvent.title.like("Performance rehearsal calendar entry %")
                )
            )
            or 0
        )
    passed = (
        active_user_count >= args.active_users
        and package_fixture_count >= args.packages
        and calendar_fixture_count >= args.calendar_occurrences
        and request_feeds["passed"]
    )
    return {
        "active_user_count": active_user_count,
        "active_user_target": args.active_users,
        "calendar_event_fixture_count": calendar_fixture_count,
        "calendar_occurrence_target": args.calendar_occurrences,
        "fixture_team": SSG_CODE,
        "packages_added": packages_added,
        "package_fixture_count": package_fixture_count,
        "passed": passed,
        "package_target": args.packages,
        "users_added": users_added,
        "calendar_events_added": calendar_added,
        "request_feeds": request_feeds,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--active-users", type=int, default=250)
    parser.add_argument("--packages", type=int, default=2_500)
    parser.add_argument("--calendar-occurrences", type=int, default=5_000)
    parser.add_argument("--request-feed-rows", type=int, default=2_500)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if (
        min(
            args.active_users,
            args.packages,
            args.calendar_occurrences,
            args.request_feed_rows,
        )
        < 1
    ):
        parser.error("all target counts must be positive")
    result = asyncio.run(run(args))
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
