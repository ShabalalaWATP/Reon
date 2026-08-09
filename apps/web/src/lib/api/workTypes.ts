import type { RequestStatus } from "./requestTypes";

export type WorkStage = Exclude<
  RequestStatus,
  "ROUTING_PENDING" | "COMPLETED" | "CLOSED_NOT_PROGRESSED" | "CANCELLED"
>;

export type WorkItem = {
  id: string;
  requestId: string;
  requestReference: string;
  requestVersion: number;
  title: string;
  stage: WorkStage;
  status: string;
  assigneeId: string | null;
  assigneeDisplayName: string | null;
  deliveryTeam: string | null;
  availableActions: WorkAction["action"][];
  createdAt: string;
  updatedAt: string;
};

export type EligibleSpecialist = { id: string; displayName: string };

export type RelatedRecordCandidate = {
  id: string;
  reference: string;
  title: string;
  status: RequestStatus;
  requiredBy: string;
  productAvailable: boolean;
};

export type RequestLinkType =
  | "POSSIBLE_DUPLICATE"
  | "RELATED_REQUEST"
  | "EXISTING_OUTPUT";

export type RequestLink = {
  id: string;
  target: RelatedRecordCandidate;
  linkType: RequestLinkType;
  reason: string;
  actorDisplayName: string;
  createdAt: string;
};

export type RequestLinkWorkspace = {
  sourceVersion: number;
  items: RequestLink[];
};

export type RequestLinkCreateInput = {
  expectedVersion: number;
  targetRequestId: string;
  linkType: RequestLinkType;
  reason: string;
};

export type WorkAction =
  | { action: "request_information"; reason: string }
  | {
      action: "progress";
      category: string;
      destinationUnitId: string;
      priority: "LOW" | "MEDIUM" | "HIGH" | "URGENT";
    }
  | { action: "close"; reason: string }
  | { action: "provide_information"; information: string }
  | { action: "withdraw"; reason: string }
  | { action: "send_to_allocation"; destinationUnitId: string; note: string }
  | { action: "return_to_triage"; reason: string }
  | { action: "hold"; reason: string }
  | { action: "resume"; note: string }
  | {
      action: "allocate";
      destinationUnitId: string;
      requiredCapabilities: string[];
    }
  | { action: "return_to_coordination"; reason: string }
  | { action: "assign"; specialistId: string }
  | { action: "return_for_reallocation"; reason: string }
  | { action: "submit"; deliverableTitle: string; deliverableText: string }
  | {
      action: "request_clarification";
      question: string;
      reason: string;
      responseDeadline: string;
    }
  | {
      action: "provide_clarification";
      threadId: string;
      expectedVersion: number;
      information: string;
    }
  | { action: "approve" }
  | { action: "changes_required"; reason: string }
  | { action: "release"; recipients: string[] };
