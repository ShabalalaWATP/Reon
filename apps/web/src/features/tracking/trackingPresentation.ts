import type { RequestStatus } from "../../lib/api/types";

export type JourneyState = "complete" | "current" | "upcoming";

const routingStatuses = new Set<RequestStatus>([
  "ROUTING_PENDING",
  "TRIAGE_REVIEW",
  "INFORMATION_REQUIRED",
  "COORDINATION_REVIEW",
  "ON_HOLD",
  "ALLOCATION_REVIEW",
]);
const productionStatuses = new Set<RequestStatus>([
  "DELIVERY_PLANNING",
  "IN_PROGRESS",
  "CUSTOMER_INFORMATION_REQUIRED",
]);
const checkStatuses = new Set<RequestStatus>(["LEAD_REVIEW", "REWORK_REQUIRED"]);
const qualityStatuses = new Set<RequestStatus>(["QUALITY_REVIEW", "READY_FOR_RELEASE"]);

export function lifecyclePhase(status: RequestStatus): number {
  if (routingStatuses.has(status)) return 0;
  if (productionStatuses.has(status)) return 1;
  if (checkStatuses.has(status)) return 2;
  if (qualityStatuses.has(status)) return 3;
  return 4;
}

export function journeyState(index: number, current: number): JourneyState {
  if (index < current) return "complete";
  return index === current ? "current" : "upcoming";
}

export function routePosition(status: RequestStatus, routeLength: number): number {
  if (routeLength === 0) return -1;
  if (status === "ROUTING_PENDING" || status === "TRIAGE_REVIEW" || status === "INFORMATION_REQUIRED") return 0;
  if (status === "COORDINATION_REVIEW" || status === "ON_HOLD") return Math.min(1, routeLength - 1);
  if (status === "ALLOCATION_REVIEW") return Math.min(2, routeLength - 1);
  return routeLength;
}

export function lifecycleLabels(status: RequestStatus): string[] {
  const finalLabel = status === "CANCELLED" || status === "CLOSED_NOT_PROGRESSED"
    ? "Closed"
    : "Customer delivery";
  return ["Routing", "Production", "Team check", "Quality and release", finalLabel];
}
