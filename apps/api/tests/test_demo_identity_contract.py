"""Static completeness checks for the synthetic account catalogue."""

from collections import Counter

from mist_service.demo_seed import DEMO_IDENTITIES
from mist_service.models import UserRole
from mist_service.organisation_models import OrganisationKind
from mist_service.organisation_seed import UNIT_DEFINITIONS
from mist_service.team_models import WorkspacePosition


def test_demo_identity_contract_covers_every_workspace() -> None:
    assert len(DEMO_IDENTITIES) == 108
    assert [identity.username for identity in DEMO_IDENTITIES] == [
        f"admin{number}" for number in range(1, 109)
    ]
    assert len({identity.display_name for identity in DEMO_IDENTITIES}) == 108
    assert Counter(identity.role for identity in DEMO_IDENTITIES) == {
        UserRole.PLATFORM_ADMIN: 2,
        UserRole.REQUESTER: 3,
        UserRole.INTAKE_TRIAGE: 4,
        UserRole.SERVICE_COORDINATION: 7,
        UserRole.OPERATIONS_ALLOCATION: 20,
        UserRole.DELIVERY_TEAM_LEAD: 29,
        UserRole.DELIVERY_SPECIALIST: 33,
        UserRole.QUALITY_RELEASE: 10,
    }
    disabled = [identity for identity in DEMO_IDENTITIES if not identity.active]
    assert [(identity.username, identity.display_name) for identity in disabled] == [
        ("admin16", "James Forrest")
    ]
    team_codes = {
        item.code for item in UNIT_DEFINITIONS if item.kind is OrganisationKind.TEAM
    }
    for code in team_codes:
        staff = [item for item in DEMO_IDENTITIES if code in item.unit_codes]
        assert any(item.role is UserRole.DELIVERY_TEAM_LEAD for item in staff)
        assert any(item.role is UserRole.DELIVERY_SPECIALIST for item in staff)
    routing_codes = {
        item.code for item in UNIT_DEFINITIONS if item.kind is not OrganisationKind.TEAM
    }
    for code in routing_codes:
        staff = [item for item in DEMO_IDENTITIES if code in item.unit_codes]
        assert {item.workspace_position for item in staff} >= {
            WorkspacePosition.MANAGER,
            WorkspacePosition.MEMBER,
        }
    ssg_staff = [item for item in DEMO_IDENTITIES if "SSG_TEAM" in item.unit_codes]
    assert Counter(item.role for item in ssg_staff) == {
        UserRole.DELIVERY_TEAM_LEAD: 3,
        UserRole.DELIVERY_SPECIALIST: 7,
    }
