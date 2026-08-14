import type { RequestDetail, RequestStatus } from "./requestTypes";

export type OrganisationUnit = {
  id: string;
  code: string;
  name: string;
  kind: "ROOT" | "COMMAND" | "OPS_GROUP" | "TEAM";
  parentId: string | null;
  staffingStatus: "ROUTING_POOL" | "STAFFED" | "UNSTAFFED";
  version: number;
};

export type RoutingPathUnit = Pick<OrganisationUnit, "id" | "code" | "name" | "kind">;

export type RoutingOptionsWorkspace = {
  route: RoutingPathUnit[];
  items: OrganisationUnit[];
};

export type TrackedRequestRouteUnit = Pick<OrganisationUnit, "id" | "name" | "kind">;

export type TrackedRequest = {
  id: string;
  reference: string;
  title: string;
  status: RequestStatus;
  currentOwner: string | null;
  requiredBy: string;
  createdAt: string;
  updatedAt: string;
  route: TrackedRequestRouteUnit[];
  awaitingTeamStaffing: boolean;
  ageDays: number;
  customerAcceptanceRequired: boolean;
  customerAcceptedAt: string | null;
};

export type TrackedRequestFilters = {
  search: string;
  status: RequestStatus | "";
  currentOwner: string;
  routeUnitId: string;
  minimumAgeDays: string;
};

export type TrackedRequestEvent = {
  id: string;
  type: string;
  message: string;
  actorDisplayName: string | null;
  priorStatus: RequestStatus | null;
  nextStatus: RequestStatus | null;
  createdAt: string;
};

export type CoordinationResult = { event: TrackedRequestEvent };

export type TrackedRequestDetail = TrackedRequest &
  Pick<
    RequestDetail,
    | "description"
    | "questionToAnswer"
    | "desiredOutcome"
    | "backgroundContext"
    | "subjectAreaOrLocation"
    | "coverageStart"
    | "coverageEnd"
    | "customerUrgency"
    | "supportedActivityOrDecision"
    | "requiredByReason"
    | "preferredDeliverableType"
    | "successCriteria"
    | "constraintsOrCaveats"
    | "supportingInformation"
    | "sensitivity"
    | "handlingInstructions"
  > & {
    requesterDisplayName: string;
    events: TrackedRequestEvent[];
    eventsNextCursor?: string | null;
  };
