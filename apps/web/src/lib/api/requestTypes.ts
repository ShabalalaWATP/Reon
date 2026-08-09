export type RequestStatus =
  | "ROUTING_PENDING"
  | "TRIAGE_REVIEW"
  | "INFORMATION_REQUIRED"
  | "COORDINATION_REVIEW"
  | "ON_HOLD"
  | "ALLOCATION_REVIEW"
  | "DELIVERY_PLANNING"
  | "IN_PROGRESS"
  | "CUSTOMER_INFORMATION_REQUIRED"
  | "LEAD_REVIEW"
  | "REWORK_REQUIRED"
  | "QUALITY_REVIEW"
  | "READY_FOR_RELEASE"
  | "COMPLETED"
  | "CLOSED_NOT_PROGRESSED"
  | "CANCELLED";

export type RequestSummary = {
  id: string;
  reference: string;
  title: string;
  status: RequestStatus;
  currentOwner: string | null;
  requiredBy: string;
  createdAt: string;
  updatedAt: string;
  needsRequesterInput: boolean;
  productAvailable: boolean;
  feedbackSubmitted: boolean;
};

export type RequestEvent = {
  id: string;
  type: string;
  message: string;
  actorDisplayName: string | null;
  createdAt: string;
};

export type Deliverable = {
  id: string;
  title: string;
  text: string;
  releasedAt: string | null;
};

export type Feedback = {
  id: string;
  rating: number;
  comments: string;
  createdAt: string;
};

export type ClarificationMessage = {
  id: string;
  kind: "REQUEST" | "RESPONSE" | "WITHDRAWAL";
  body: string;
  actorDisplayName: string;
  createdAt: string;
};

export type ClarificationThread = {
  id: string;
  sequence: number;
  question: string;
  reason: string;
  responseDeadline: string;
  status: "OPEN" | "ANSWERED" | "WITHDRAWN";
  version: number;
  assignedSpecialist: { id: string; displayName: string };
  messages: ClarificationMessage[];
  createdAt: string;
  closedAt: string | null;
};

export type RequestDetail = RequestSummary & {
  serviceCategory: string;
  description: string;
  desiredOutcome: string;
  backgroundContext: string;
  requiredByReason: string;
  preferredDeliverableType: string;
  successCriteria: string;
  requestingBusinessArea: string;
  intendedRecipients: string[];
  sensitivity: "STANDARD" | "SENSITIVE" | "RESTRICTED";
  handlingInstructions: string;
  requester: { id: string; displayName: string };
  assignedDeliveryTeam: string | null;
  assignedSpecialist: { id: string; displayName: string } | null;
  events: RequestEvent[];
  eventsNextCursor?: string | null;
  deliverable: Deliverable | null;
  feedback: Feedback | null;
  clarifications: ClarificationThread[];
  workflowError: string | null;
};

export type RequestCreateInput = Pick<
  RequestDetail,
  | "title"
  | "serviceCategory"
  | "description"
  | "desiredOutcome"
  | "backgroundContext"
  | "requiredBy"
  | "requiredByReason"
  | "preferredDeliverableType"
  | "successCriteria"
  | "requestingBusinessArea"
  | "intendedRecipients"
  | "sensitivity"
  | "handlingInstructions"
> & { submissionKey?: string };

export type RequestDraftInput = {
  title?: string | null;
  serviceCategory?: string | null;
  description?: string | null;
  desiredOutcome?: string | null;
  backgroundContext?: string | null;
  requiredBy?: string | null;
  requiredByReason?: string | null;
  preferredDeliverableType?: string | null;
  successCriteria?: string | null;
  requestingBusinessArea?: string | null;
  intendedRecipients?: string[] | null;
  sensitivity?: "STANDARD" | "SENSITIVE" | "RESTRICTED" | null;
  handlingInstructions?: string | null;
};

export type RequestDraft = RequestDraftInput & {
  id: string;
  requesterId: string;
  version: number;
  createdAt: string;
  updatedAt: string;
};

export type RequestDraftUpdateInput = RequestDraftInput & {
  expectedVersion: number;
};

export type RequestDraftSubmitInput = RequestCreateInput & {
  expectedVersion: number;
};

export type FeedbackInput = {
  submissionKey?: string;
  rating: number;
  comments: string;
};
