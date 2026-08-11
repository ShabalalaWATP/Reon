import type {
  AdminUser,
  RequestDetail,
  RequestSummary,
  Session,
  TrackedRequest,
  WorkItem,
} from "../lib/api/types";
import type { ServerCapabilities } from "../lib/api/capabilityClient";
import { organisationUnit } from "./organisationFixtures";

export {
  organisationChildren,
  organisationUnit,
  organisationUnits,
} from "./organisationFixtures";

export const requesterSession: Session = {
  user: {
    id: "11111111-1111-4111-8111-111111111111",
    username: "admin2",
    displayName: "John McGinn",
    role: "REQUESTER",
    scope: "Customer",
    organisationUnitIds: [],
  },
  csrfToken: "csrf-token",
  expiresAt: "2026-08-07T12:00:00Z",
  elevatedUntil: null,
};

export const enabledCapabilities: ServerCapabilities = {
  myWork: true,
  notifications: true,
  configuration: true,
  products: true,
  managedFileUploads: true,
  planning: true,
  statistics: true,
};

export const staffSession: Session = {
  ...requesterSession,
  user: {
    ...requesterSession.user,
    id: "22222222-2222-4222-8222-222222222222",
    username: "admin3",
    displayName: "Scott McTominay",
    role: "INTAKE_TRIAGE",
    scope: "Shared queue",
  },
};

export const adminSession: Session = {
  ...requesterSession,
  user: {
    ...requesterSession.user,
    id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    username: "admin1",
    displayName: "Andy Robertson",
    role: "PLATFORM_ADMIN",
    scope: "Platform",
  },
  elevatedUntil: "2099-08-07T12:00:00Z",
};

export const adminManagedUser: AdminUser = {
  id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  username: "admin2",
  email: "admin2@istari.example.test",
  displayName: "John McGinn",
  role: "REQUESTER",
  scope: "Customer Group A",
  isActive: true,
  version: 1,
  createdAt: "2026-08-06T09:00:00Z",
  updatedAt: "2026-08-06T09:00:00Z",
  memberships: [],
};

export const requestSummary: RequestSummary = {
  id: "33333333-3333-4333-8333-333333333333",
  reference: "ISR-2026-0012",
  title: "Quarterly service readiness summary",
  status: "IN_PROGRESS",
  currentOwner: "SSG Team",
  requiredBy: "2026-09-10",
  createdAt: "2026-08-06T09:00:00Z",
  updatedAt: "2026-08-06T10:00:00Z",
  version: 1,
  needsRequesterInput: false,
  productAvailable: false,
  feedbackSubmitted: false,
};

export const requestDetail: RequestDetail = {
  ...requestSummary,
  serviceCategory: "Advisory support",
  description: "Provide a concise readiness summary covering the agreed service measures.",
  questionToAnswer: "What does the synthetic evidence show?",
  desiredOutcome: "Leaders can make a clear decision about the next quarter.",
  backgroundContext: "The fictional service review takes place each quarter.",
  subjectAreaOrLocation: "Synthetic subject area",
  coverageStart: "2026-08-01",
  coverageEnd: "2026-08-05",
  customerUrgency: "ROUTINE",
  supportedActivityOrDecision: "A fictional planning decision.",
  requiredByReason: "The review meeting is scheduled for the following day.",
  preferredDeliverableType: "Briefing note",
  successCriteria: "The note covers all agreed measures and next steps.",
  constraintsOrCaveats: "No known constraints.",
  supportingInformation: "No supporting material is available.",
  sensitivity: "STANDARD",
  handlingInstructions: "Standard handling applies.",
  requester: { id: requesterSession.user.id, displayName: requesterSession.user.displayName },
  assignedDeliveryTeam: "SSG Team",
  assignedSpecialist: { id: "44444444-4444-4444-8444-444444444444", displayName: "Lewis Ferguson" },
  contributors: [],
  events: [{ id: "event-1", type: "SUBMITTED", message: "Request submitted", actorDisplayName: "John McGinn", createdAt: "2026-08-06T09:00:00Z" }],
  deliverable: null,
  feedback: null,
  clarifications: [],
  workflowError: null,
};

export const workItem: WorkItem = {
  id: "55555555-5555-4555-8555-555555555555",
  requestId: requestDetail.id,
  requestReference: requestDetail.reference,
  requestVersion: 1,
  title: requestDetail.title,
  stage: "TRIAGE_REVIEW",
  status: "AVAILABLE",
  assigneeId: null,
  assigneeDisplayName: null,
  deliveryTeam: null,
  availableActions: ["request_information", "progress", "close"],
  createdAt: "2026-08-06T09:01:00Z",
  updatedAt: "2026-08-06T09:02:00Z",
};

export const trackedRequest: TrackedRequest = {
  id: requestDetail.id,
  reference: requestDetail.reference,
  title: requestDetail.title,
  status: "ALLOCATION_REVIEW",
  currentOwner: "Cedar Team",
  requiredBy: requestDetail.requiredBy,
  createdAt: requestDetail.createdAt,
  updatedAt: requestDetail.updatedAt,
  route: [
    organisationUnit("CRIOC"),
    organisationUnit("JOCK"),
    organisationUnit("ACSA_B_OPS"),
    organisationUnit("CEDAR_TEAM"),
  ].map(({ id, kind, name }) => ({ id, kind, name })),
  awaitingTeamStaffing: false,
};
