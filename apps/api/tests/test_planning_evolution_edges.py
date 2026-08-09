"""Policy and pure planning-projection boundary coverage."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from istari_service.board_models import WorkPackageStatus
from istari_service.domain import Actor
from istari_service.errors import TeamWorkspaceNotFound
from istari_service.management_models import ManagementAction
from istari_service.models import UserRole
from istari_service.planning_analytics_models import PackageBlocker
from istari_service.planning_capacity import (
    PlanningCapacityDay,
    PlanningCapacityProjection,
)
from istari_service.planning_policy import (
    authorise_planning_preview,
    authorise_planning_read,
)
from istari_service.planning_projection import (
    blocker_warnings,
    capacity_conflicts,
    dependency_warnings,
)
from istari_service.repositories.management import ManagementScope
from istari_service.repositories.planning import (
    PackagePlanningRows,
    SqlAlchemyPlanningRepository,
)
from planning_evolution_data import package


def _actor() -> Actor:
    return Actor(
        id=uuid4(),
        username="synthetic-lead",
        display_name="Synthetic Lead",
        role=UserRole.DELIVERY_TEAM_LEAD,
        scope="synthetic",
    )


async def test_exact_grant_read_and_preview_requires_both_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = _actor()
    team_id = uuid4()
    session = AsyncMock()
    session.scalar.side_effect = (None, uuid4())
    await authorise_planning_read(session, actor, team_id, ManagementAction.CAPACITY)
    scopes = iter(
        (
            ManagementScope(
                grant_id=uuid4(),
                root_unit_id=team_id,
                target_unit_id=team_id,
                include_descendants=False,
                action=ManagementAction.BOARD,
                grant_version=1,
            ),
            None,
        )
    )

    async def resolve(*args: object, **kwargs: object) -> ManagementScope | None:
        del args, kwargs
        return next(scopes)

    monkeypatch.setattr(
        "istari_service.planning_policy.resolve_management_scope", resolve
    )
    with pytest.raises(TeamWorkspaceNotFound):
        await authorise_planning_preview(session, actor, team_id, uuid4())


async def test_empty_template_and_checklist_repository_paths() -> None:
    session = AsyncMock()
    repository = SqlAlchemyPlanningRepository(session)
    assert await repository._template_items([]) == {}
    owner = package(uuid4(), uuid4(), uuid4(), "No checklist", WorkPackageStatus.READY)
    owner.id = uuid4()
    session.scalars.return_value = ()
    assert await repository._checklists(((owner, "Owner"),), [owner.id]) == []


def test_projection_edges_are_bounded_and_skip_orphans() -> None:
    owner = package(uuid4(), uuid4(), uuid4(), "Owner", WorkPackageStatus.IN_PROGRESS)
    dependency = package(
        owner.team_id, uuid4(), uuid4(), "Dependency", WorkPackageStatus.READY
    )
    owner.id = uuid4()
    dependency.id = uuid4()
    orphan_blocker = PackageBlocker(
        package_id=uuid4(),
        team_id=owner.team_id,
        reason="Synthetic orphan",
        opened_at=datetime.now(UTC),
        opened_by_user_id=uuid4(),
        version=1,
    )
    rows = PackagePlanningRows(
        packages=((owner, "Owner"), (dependency, "Dependency")),
        iteration_names={},
        dependencies=((owner.id, dependency), (uuid4(), None)),
        blockers=(orphan_blocker,),
        checklists=(),
    )
    warnings, counts = dependency_warnings(rows)
    blockers, ages = blocker_warnings(rows, datetime.now(UTC))
    assert warnings[0].status == "AT_RISK"
    assert counts == {owner.id: 1}
    assert blockers == [] and ages == {}
    start = datetime.now(UTC).date()
    capacity = PlanningCapacityProjection(
        days=tuple(
            PlanningCapacityDay(
                date=start + timedelta(days=offset),
                baseline_minutes=1,
                calendar_minutes=1,
                reserved_minutes=1,
                available_minutes=0,
            )
            for offset in range(40)
        ),
        source_digest="synthetic",
    )
    conflicts = capacity_conflicts(capacity, 40, warnings, start)
    assert len(conflicts) == 100
