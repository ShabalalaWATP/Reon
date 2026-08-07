export type UserRole =
  | "PLATFORM_ADMIN"
  | "REQUESTER"
  | "INTAKE_TRIAGE"
  | "SERVICE_COORDINATION"
  | "OPERATIONS_ALLOCATION"
  | "DELIVERY_TEAM_LEAD"
  | "DELIVERY_SPECIALIST"
  | "QUALITY_RELEASE";

export type User = {
  id: string;
  username: string;
  displayName: string;
  role: UserRole;
  scope: string;
};

export type Session = {
  user: User;
  csrfToken: string;
  expiresAt: string;
  elevatedUntil: string | null;
};

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

export type EligibleSpecialist = {
  id: string;
  displayName: string;
};

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

export type OrganisationUnit = {
  id: string;
  code: string;
  name: string;
  kind: "ROOT" | "COMMAND" | "OPS_GROUP" | "TEAM";
  parentId: string | null;
  staffingStatus: "ROUTING_POOL" | "STAFFED" | "UNSTAFFED";
  version: number;
};

export type UserMembership = {
  organisationUnitId: string;
  organisationUnitName: string;
  organisationUnitKind: OrganisationUnit["kind"];
};

export type AdminUser = User & {
  isActive: boolean;
  version: number;
  memberships: UserMembership[];
  createdAt: string;
  updatedAt: string;
};

export type AdminUserWriteInput = {
  displayName: string;
  role: UserRole;
  scope: string;
  organisationUnitIds: string[];
};

export type AdminUserUpdateInput = AdminUserWriteInput & { expectedVersion: number };
export type AdminUserStatusInput = { isActive: boolean; expectedVersion: number };
export type OrganisationUnitRenameInput = { name: string; expectedVersion: number };

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

export type FeedbackInput = { submissionKey?: string; rating: number; comments: string };
export type ListResponse<T> = { items: T[] };
