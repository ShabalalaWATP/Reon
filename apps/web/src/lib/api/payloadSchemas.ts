import {
  arrayOf,
  isBoolean,
  isNumber,
  isOneOf,
  isString,
  nullOr,
  optional,
  payloadParser,
  shape,
} from "./payloadContract";
import type { RequestDetail, WorkItem } from "./types";

const isRequestStatus = isOneOf([
  "ROUTING_PENDING",
  "TRIAGE_REVIEW",
  "INFORMATION_REQUIRED",
  "COORDINATION_REVIEW",
  "ON_HOLD",
  "ALLOCATION_REVIEW",
  "DELIVERY_PLANNING",
  "IN_PROGRESS",
  "CUSTOMER_INFORMATION_REQUIRED",
  "LEAD_REVIEW",
  "REWORK_REQUIRED",
  "QUALITY_REVIEW",
  "READY_FOR_RELEASE",
  "COMPLETED",
  "CLOSED_NOT_PROGRESSED",
  "CANCELLED",
]);

const isWorkStage = isOneOf([
  "TRIAGE_REVIEW",
  "INFORMATION_REQUIRED",
  "COORDINATION_REVIEW",
  "ON_HOLD",
  "ALLOCATION_REVIEW",
  "DELIVERY_PLANNING",
  "IN_PROGRESS",
  "CUSTOMER_INFORMATION_REQUIRED",
  "LEAD_REVIEW",
  "REWORK_REQUIRED",
  "QUALITY_REVIEW",
  "READY_FOR_RELEASE",
]);

const isWorkActionName = isOneOf([
  "request_information",
  "progress",
  "close",
  "provide_information",
  "withdraw",
  "send_to_allocation",
  "return_to_triage",
  "hold",
  "resume",
  "allocate",
  "return_to_coordination",
  "assign",
  "return_for_reallocation",
  "submit",
  "request_clarification",
  "provide_clarification",
  "approve",
  "changes_required",
  "release",
]);

const isPerson = shape({ id: isString, displayName: isString });

const isRequestEvent = shape({
  id: isString,
  type: isString,
  message: isString,
  actorDisplayName: nullOr(isString),
  createdAt: isString,
});

const isDeliverable = shape({
  id: isString,
  title: isString,
  text: isString,
  releasedAt: nullOr(isString),
});

const isFeedback = shape({
  id: isString,
  rating: isNumber,
  comments: isString,
  createdAt: isString,
});

const isClarificationMessage = shape({
  id: isString,
  kind: isOneOf(["REQUEST", "RESPONSE", "WITHDRAWAL"]),
  body: isString,
  actorDisplayName: isString,
  createdAt: isString,
});

const isClarificationThread = shape({
  id: isString,
  sequence: isNumber,
  question: isString,
  reason: isString,
  responseDeadline: isString,
  status: isOneOf(["OPEN", "ANSWERED", "WITHDRAWN"]),
  version: isNumber,
  assignedSpecialist: isPerson,
  messages: arrayOf(isClarificationMessage),
  createdAt: isString,
  closedAt: nullOr(isString),
});

const isRequestDetail = shape({
  id: isString,
  reference: isString,
  title: isString,
  status: isRequestStatus,
  currentOwner: nullOr(isString),
  requiredBy: isString,
  createdAt: isString,
  updatedAt: isString,
  version: isNumber,
  needsRequesterInput: isBoolean,
  productAvailable: isBoolean,
  feedbackSubmitted: isBoolean,
  productMode: isOneOf(["LEGACY", "MANAGED"]),
  serviceCategory: isString,
  description: isString,
  questionToAnswer: isString,
  desiredOutcome: isString,
  backgroundContext: isString,
  subjectAreaOrLocation: isString,
  coverageStart: isString,
  coverageEnd: isString,
  customerUrgency: isOneOf(["ROUTINE", "TIME_SENSITIVE", "IMMEDIATE"]),
  supportedActivityOrDecision: isString,
  requiredByReason: isString,
  preferredDeliverableType: isString,
  successCriteria: isString,
  constraintsOrCaveats: isString,
  supportingInformation: isString,
  sensitivity: isOneOf(["STANDARD", "SENSITIVE", "RESTRICTED"]),
  handlingInstructions: isString,
  requester: isPerson,
  assignedDeliveryTeam: nullOr(isString),
  assignedSpecialist: nullOr(isPerson),
  contributors: arrayOf(isPerson),
  events: arrayOf(isRequestEvent),
  eventsNextCursor: optional(nullOr(isString)),
  deliverable: nullOr(isDeliverable),
  feedback: nullOr(isFeedback),
  clarifications: arrayOf(isClarificationThread),
  workflowError: nullOr(isString),
});

const isWorkItem = shape({
  id: isString,
  requestId: isString,
  requestReference: isString,
  requestVersion: isNumber,
  title: isString,
  stage: isWorkStage,
  status: isString,
  assigneeId: nullOr(isString),
  assigneeDisplayName: nullOr(isString),
  deliveryTeam: nullOr(isString),
  availableActions: arrayOf(isWorkActionName),
  assignedToCurrentUser: optional(isBoolean),
  assignmentRole: optional(nullOr(isOneOf(["LEAD_ANALYST", "ANALYST"]))),
  createdAt: isString,
  updatedAt: isString,
});

export const parseRequestDetail = payloadParser<RequestDetail>("request", isRequestDetail);
export const parseWorkItem = payloadParser<WorkItem>("work item", isWorkItem);
