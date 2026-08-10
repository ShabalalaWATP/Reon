"""User-facing ownership labels for stable request status projections."""

from istari_service.models import RequestStatus

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
    RequestStatus.QUALITY_REVIEW: "QC Manager",
    RequestStatus.READY_FOR_RELEASE: "QC Manager",
    RequestStatus.COMPLETED: "Customer",
    RequestStatus.CLOSED_NOT_PROGRESSED: "Customer",
    RequestStatus.CANCELLED: "Customer",
}
