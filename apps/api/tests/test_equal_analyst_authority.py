"""Equal production authority for every active assigned Analyst."""

from istari_service.authorisation import PolicyDenial, WorkOperation
from istari_service.models import RequestStatus, UserRole, WorkflowTaskStatus
from istari_service.policies import decide_work_access, decide_work_completion

from authorisation_test_support import actor, request, work


def test_assigned_analyst_can_view_and_complete_shared_delivery_work() -> None:
    owner = actor(UserRole.REQUESTER)
    lead = actor(UserRole.DELIVERY_SPECIALIST, scope="SSG Team")
    analyst = actor(UserRole.DELIVERY_SPECIALIST, scope="SSG Team")
    delivery = request(
        owner,
        status=RequestStatus.IN_PROGRESS,
        team="SSG Team",
        specialist_id=lead.id,
        participants=frozenset({lead.id, analyst.id}),
    )
    shared = work(
        delivery,
        task_status=WorkflowTaskStatus.CLAIMED,
        assignee_id=lead.id,
    )

    assert decide_work_access(analyst, shared, WorkOperation.VIEW).allowed
    assert decide_work_access(analyst, shared, WorkOperation.COMPLETE).allowed
    assert decide_work_completion(analyst, delivery, "submit", lead.id).allowed

    outsider = actor(UserRole.DELIVERY_SPECIALIST, scope="SSG Team")
    assert (
        decide_work_completion(outsider, delivery, "submit", lead.id).denial
        is PolicyDenial.OBJECT_SCOPE
    )
