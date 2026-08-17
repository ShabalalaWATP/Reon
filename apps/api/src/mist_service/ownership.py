"""User-facing ownership labels for stable request status projections."""

from __future__ import annotations

from sqlalchemy import case, update
from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.models import RequestStatus, ServiceRequest

OWNER_BY_STATUS = {
    RequestStatus.ROUTING_PENDING: "JIOC Routing",
    RequestStatus.TRIAGE_REVIEW: "JIOC Routing",
    RequestStatus.INFORMATION_REQUIRED: "Customer",
    RequestStatus.COORDINATION_REVIEW: "Request Coordination",
    RequestStatus.ON_HOLD: "Request Coordination",
    RequestStatus.ALLOCATION_REVIEW: "Ops Routing",
    RequestStatus.DELIVERY_PLANNING: "Team Manager",
    RequestStatus.IN_PROGRESS: "Team Analyst",
    RequestStatus.CUSTOMER_INFORMATION_REQUIRED: "Customer",
    RequestStatus.LEAD_REVIEW: "Team Manager",
    RequestStatus.REWORK_REQUIRED: "Team Analyst",
    RequestStatus.QUALITY_REVIEW: "QC User or QC Manager",
    RequestStatus.READY_FOR_RELEASE: "QC Manager",
    RequestStatus.COMPLETED: "Customer",
    RequestStatus.CLOSED_NOT_PROGRESSED: "Customer",
    RequestStatus.CANCELLED: "Customer",
}


async def reconcile_owner_labels(session: AsyncSession) -> int:
    """Re-stamp any stored owner label that no longer matches its status.

    The owner label is a status-derived snapshot kept in a column so tracking
    can filter on it in SQL. It is re-stamped on every workflow transition,
    which leaves in-flight requests carrying an old label after the labels
    themselves are renamed. Running this at start heals them idempotently, so
    a label rename in code never needs a hand-written data correction.
    """

    expected = case(
        *(
            (ServiceRequest.status == status, label)
            for status, label in OWNER_BY_STATUS.items()
        ),
        else_=ServiceRequest.current_owner,
    )
    result = await session.execute(
        update(ServiceRequest)
        .where(ServiceRequest.current_owner != expected)
        .values(current_owner=expected)
        .execution_options(synchronize_session=False)
    )
    return int(result.rowcount)  # type: ignore[attr-defined]
