import type {
  ConfigurationPreview,
  ConfigurationVersion,
  WorkflowDefinition,
} from "../lib/api/configurationTypes";

const effectiveFrom = "2026-09-01T09:00:00Z";

export const configurationVersion: ConfigurationVersion = {
  id: "cfg-2",
  sequence: 2,
  label: "Northern branch changes",
  status: "DRAFT",
  effectiveFrom,
  createdByUserId: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  basedOnVersionId: "cfg-1",
  version: 1,
  createdAt: "2026-08-07T09:00:00Z",
  updatedAt: "2026-08-07T09:00:00Z",
  reason: null,
  validatedAt: null,
  submittedAt: null,
  activatedAt: null,
  rejectedAt: null,
  units: [
    { unitId: "unit-root", code: "ISTARI", name: "ISTARI", kind: "ROOT", effectiveFrom, effectiveUntil: null, routingEnabled: true, minimumManagers: 0, minimumAnalysts: 0 },
    { unitId: "unit-command", code: "NORTH", name: "Northern Command", kind: "COMMAND", effectiveFrom, effectiveUntil: null, routingEnabled: true, minimumManagers: 0, minimumAnalysts: 0 },
    { unitId: "unit-ops", code: "NORTH_OPS", name: "Northern Ops Group", kind: "OPS_GROUP", effectiveFrom, effectiveUntil: null, routingEnabled: true, minimumManagers: 0, minimumAnalysts: 0 },
    { unitId: "unit-team", code: "PINE_TEAM", name: "Pine Team", kind: "TEAM", effectiveFrom, effectiveUntil: null, routingEnabled: true, minimumManagers: 1, minimumAnalysts: 2 },
  ],
  edges: [
    { parentUnitId: "unit-root", childUnitId: "unit-command", effectiveFrom, effectiveUntil: null },
    { parentUnitId: "unit-command", childUnitId: "unit-ops", effectiveFrom, effectiveUntil: null },
    { parentUnitId: "unit-ops", childUnitId: "unit-team", effectiveFrom, effectiveUntil: null },
  ],
  candidateGroups: [
    { unitId: "unit-root", purpose: "ROUTING", candidateGroup: "istari-routing" },
    { unitId: "unit-command", purpose: "ROUTING", candidateGroup: "north-routing" },
    { unitId: "unit-ops", purpose: "ROUTING", candidateGroup: "north-ops-routing" },
    { unitId: "unit-team", purpose: "MANAGER", candidateGroup: "pine-managers" },
    { unitId: "unit-team", purpose: "ANALYST", candidateGroup: "pine-analysts" },
  ],
  workflowTemplate: {
    schemaId: "istari.workflow-template/v1",
    formVersion: "request.v1",
    notificationPolicyVersion: "notice.v1",
    organisationRootId: "unit-root",
    routeDepth: 3,
    coreFields: ["title", "service_category", "description", "desired_outcome", "background_context", "required_by", "required_by_reason", "preferred_deliverable_type", "success_criteria", "requesting_business_area", "intended_recipients", "sensitivity", "handling_instructions"],
    serviceCategories: ["Advisory support"],
    productTypes: ["Briefing note"],
    taskLabels: {
      intake_review: "JIOC review", requester_response: "Customer response", coordination_review: "Command review", on_hold: "On hold", allocation_review: "Ops allocation", delivery_planning: "Delivery planning", delivery_work: "Product development", lead_review: "Manager review", quality_review: "Quality review", release: "Release",
    },
    allowedOutcomes: {
      intake_review: ["request_information", "progress", "close"], requester_response: ["provide_information", "withdraw"], coordination_review: ["send_to_allocation", "return_to_triage", "hold", "close"], on_hold: ["resume", "close"], allocation_review: ["allocate", "return_to_coordination"], delivery_planning: ["assign", "return_for_reallocation"], delivery_work: ["submit"], lead_review: ["approve", "changes_required"], quality_review: ["approve", "changes_required"], release: ["release"],
    },
    reminderDays: [1, 3, 7],
    artefactTypes: ["LEGACY_TEXT", "PDF", "DOCX", "PPTX"],
    approvedLinkDomains: ["products.example.test"],
    workflowDefinitionId: "workflow-1",
  },
  findings: [],
  approval: null,
};

export const workflowDefinition: WorkflowDefinition = {
  id: "workflow-1", processId: "istari-service-request", processDefinitionKey: "deployment-key",
  processVersion: 4, compatibilityKey: "istari-human-route-v1", checksum: "a".repeat(64),
  approvedAt: "2026-08-01T09:00:00Z",
};

export const configurationPreview: ConfigurationPreview = {
  versionId: "cfg-2",
  comparedWithVersionId: "cfg-1",
  snapshotDigest: "b".repeat(64),
  changes: [{ type: "ADDED", unitId: "unit-team", code: "PINE_TEAM", message: "Pine Team will be added beneath Northern Ops Group.", effectiveAt: configurationVersion.effectiveFrom }],
};
