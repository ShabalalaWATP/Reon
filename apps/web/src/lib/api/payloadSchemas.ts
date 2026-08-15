import { z } from "zod";

import { payloadParser } from "./payloadContract";
import type { RequestDetail, WorkItem } from "./types";

const requestStatusSchema = z.enum([
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

const workStageSchema = z.enum([
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

const workActionNameSchema = z.enum([
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

const personSchema = z.object({ id: z.string(), displayName: z.string() });

const requestEventSchema = z.object({
  id: z.string(),
  type: z.string(),
  message: z.string(),
  actorDisplayName: z.string().nullable(),
  createdAt: z.string(),
});

const deliverableSchema = z.object({
  id: z.string(),
  title: z.string(),
  text: z.string(),
  releasedAt: z.string().nullable(),
});

const feedbackSchema = z.object({
  id: z.string(),
  rating: z.number(),
  comments: z.string(),
  createdAt: z.string(),
});

const clarificationMessageSchema = z.object({
  id: z.string(),
  kind: z.enum(["REQUEST", "RESPONSE", "WITHDRAWAL"]),
  body: z.string(),
  actorDisplayName: z.string(),
  createdAt: z.string(),
});

const clarificationThreadSchema = z.object({
  id: z.string(),
  sequence: z.number(),
  question: z.string(),
  reason: z.string(),
  responseDeadline: z.string(),
  status: z.enum(["OPEN", "ANSWERED", "WITHDRAWN"]),
  version: z.number(),
  assignedSpecialist: personSchema,
  messages: z.array(clarificationMessageSchema),
  createdAt: z.string(),
  closedAt: z.string().nullable(),
});

const requestDetailSchema: z.ZodType<RequestDetail> = z.object({
  id: z.string(),
  reference: z.string(),
  title: z.string(),
  status: requestStatusSchema,
  currentOwner: z.string().nullable(),
  requiredBy: z.string(),
  createdAt: z.string(),
  updatedAt: z.string(),
  version: z.number(),
  needsRequesterInput: z.boolean(),
  productAvailable: z.boolean(),
  feedbackSubmitted: z.boolean(),
  productMode: z.enum(["LEGACY", "MANAGED"]),
  serviceCategory: z.string(),
  description: z.string(),
  questionToAnswer: z.string(),
  desiredOutcome: z.string(),
  backgroundContext: z.string(),
  subjectAreaOrLocation: z.string(),
  coverageStart: z.string(),
  coverageEnd: z.string(),
  customerUrgency: z.enum(["ROUTINE", "TIME_SENSITIVE", "IMMEDIATE"]),
  supportedActivityOrDecision: z.string(),
  requiredByReason: z.string(),
  preferredDeliverableType: z.string(),
  successCriteria: z.string(),
  constraintsOrCaveats: z.string(),
  supportingInformation: z.string(),
  sensitivity: z.enum(["STANDARD", "SENSITIVE", "RESTRICTED"]),
  handlingInstructions: z.string(),
  requester: personSchema,
  assignedDeliveryTeam: z.string().nullable(),
  assignedSpecialist: personSchema.nullable(),
  contributors: z.array(personSchema),
  events: z.array(requestEventSchema),
  eventsNextCursor: z.string().nullable().optional(),
  deliverable: deliverableSchema.nullable(),
  feedback: feedbackSchema.nullable(),
  clarifications: z.array(clarificationThreadSchema),
  workflowError: z.string().nullable(),
});

const workItemSchema: z.ZodType<WorkItem> = z.object({
  id: z.string(),
  requestId: z.string(),
  requestReference: z.string(),
  requestVersion: z.number(),
  title: z.string(),
  stage: workStageSchema,
  status: z.string(),
  assigneeId: z.string().nullable(),
  assigneeDisplayName: z.string().nullable(),
  deliveryTeam: z.string().nullable(),
  availableActions: z.array(workActionNameSchema),
  assignedToCurrentUser: z.boolean().optional(),
  assignmentRole: z.enum(["LEAD_ANALYST", "ANALYST"]).nullable().optional(),
  createdAt: z.string(),
  updatedAt: z.string(),
});

export const parseRequestDetail = payloadParser("request", requestDetailSchema);
export const parseWorkItem = payloadParser("work item", workItemSchema);
