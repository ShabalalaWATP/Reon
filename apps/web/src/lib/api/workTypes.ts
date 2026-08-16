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
  assignedToCurrentUser?: boolean;
  assignmentRole?: "LEAD_ANALYST" | "ANALYST" | null;
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

export type RelatedRecordEvidence = {
  field: string;
  reason: string;
  excerpt: string;
};

export type RelatedRecordMatch = RelatedRecordCandidate & {
  matchStrength: number;
  matchBand: "STRONG" | "POSSIBLE" | "LIMITED";
  methods: ("FULL_TEXT" | "SEMANTIC" | "STRUCTURED")[];
  reasons: string[];
  evidence: RelatedRecordEvidence[];
};

export type RelatedRecordSearchResult = {
  mode: "HYBRID" | "TEXT_ONLY";
  items: RelatedRecordMatch[];
};

export type RequestLinkType =
  "POSSIBLE_DUPLICATE" | "RELATED_REQUEST" | "EXISTING_OUTPUT" | "NOT_RELEVANT";

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
      destinationUnitId: string;
      priority: "LOW" | "MEDIUM" | "HIGH" | "URGENT";
      note?: string;
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
  | { action: "assign"; specialistId: string; contributorIds: string[]; reason: string }
  | { action: "return_for_reallocation"; reason: string }
  | { action: "submit"; managedProduct: true }
  | { action: "submit"; managedProduct?: false; deliverableTitle: string; deliverableText: string }
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
  | { action: "release"; managedProduct: true }
  | { action: "release"; managedProduct?: false; recipients: string[] };
