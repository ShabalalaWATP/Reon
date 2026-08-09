import type { RequestStatus } from "./requestTypes";

export type OrganisationUnit = {
  id: string;
  code: string;
  name: string;
  kind: "ROOT" | "COMMAND" | "OPS_GROUP" | "TEAM";
  parentId: string | null;
  staffingStatus: "ROUTING_POOL" | "STAFFED" | "UNSTAFFED";
  version: number;
};

export type RoutingPathUnit = Pick<
  OrganisationUnit,
  "id" | "code" | "name" | "kind"
>;

export type RoutingOptionsWorkspace = {
  route: RoutingPathUnit[];
  items: OrganisationUnit[];
};

export type TrackedRequestRouteUnit = Pick<
  OrganisationUnit,
  "id" | "name" | "kind"
>;

export type TrackedRequest = {
  id: string;
  reference: string;
  status: RequestStatus;
  currentOwner: string | null;
  requiredBy: string;
  updatedAt: string;
  route: TrackedRequestRouteUnit[];
  awaitingTeamStaffing: boolean;
};
