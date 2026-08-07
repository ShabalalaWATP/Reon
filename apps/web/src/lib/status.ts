import type { RequestStatus } from "./api/types";

export const statusLabels: Record<RequestStatus, string> = {
  ROUTING_PENDING: "Submitted",
  TRIAGE_REVIEW: "JIOC routing",
  INFORMATION_REQUIRED: "Information required",
  COORDINATION_REVIEW: "Command routing",
  ON_HOLD: "On hold",
  ALLOCATION_REVIEW: "Ops routing",
  DELIVERY_PLANNING: "Team assignment",
  IN_PROGRESS: "Product development",
  CUSTOMER_INFORMATION_REQUIRED: "Awaiting Customer information",
  LEAD_REVIEW: "Manager review",
  REWORK_REQUIRED: "Changes required",
  QUALITY_REVIEW: "QC review",
  READY_FOR_RELEASE: "Ready for dissemination",
  COMPLETED: "Completed",
  CLOSED_NOT_PROGRESSED: "Closed without production",
  CANCELLED: "Cancelled",
};

export function statusTone(status: RequestStatus) {
  if (status === "COMPLETED") return "success";
  if (["CLOSED_NOT_PROGRESSED", "CANCELLED"].includes(status)) return "neutral";
  if (["INFORMATION_REQUIRED", "CUSTOMER_INFORMATION_REQUIRED", "REWORK_REQUIRED"].includes(status)) return "attention";
  return "active";
}

export function formatDate(value: string, includeTime = false) {
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    ...(includeTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  }).format(new Date(value));
}

export function isComplete(status: RequestStatus) {
  return ["COMPLETED", "CLOSED_NOT_PROGRESSED", "CANCELLED"].includes(status);
}

export function trackingStatusLabel(status: RequestStatus) {
  return status === "COMPLETED" ? "Disseminated" : statusLabels[status];
}

export function requesterGroup(status: RequestStatus, needsInput: boolean) {
  if (needsInput || ["INFORMATION_REQUIRED", "CUSTOMER_INFORMATION_REQUIRED"].includes(status)) return "Needs your input";
  return isComplete(status) ? "Completed" : "In progress";
}
