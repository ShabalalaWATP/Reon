import type { OrganisationUnit } from "./types";

export type ConfigurationStatus =
  "DRAFT" | "VALIDATED" | "AWAITING_APPROVAL" | "ACTIVE" | "SUPERSEDED" | "REJECTED";

export interface ConfigurationUnitDraft {
  unitId: string;
  code: string;
  name: string;
  kind: OrganisationUnit["kind"];
  effectiveFrom: string;
  effectiveUntil: string | null;
  routingEnabled: boolean;
  minimumManagers: number;
  minimumAnalysts: number;
}

export interface ConfigurationEdgeDraft {
  parentUnitId: string;
  childUnitId: string;
  effectiveFrom: string;
  effectiveUntil: string | null;
}

export interface CandidateGroupDraft {
  unitId: string;
  purpose: "ROUTING" | "MANAGER" | "ANALYST";
  candidateGroup: string;
}

export interface WorkflowTemplateDraft {
  schemaId: "istari.workflow-template/v1";
  formVersion: string;
  notificationPolicyVersion: string;
  organisationRootId: string;
  routeDepth: 3;
  coreFields: string[];
  serviceCategories: string[];
  productTypes: string[];
  taskLabels: Record<string, string>;
  allowedOutcomes: Record<string, string[]>;
  reminderDays: number[];
  artefactTypes: Array<"LEGACY_TEXT" | "PDF" | "DOCX" | "PPTX">;
  approvedLinkDomains: string[];
  workflowDefinitionId: string;
}

export interface ConfigurationFinding {
  severity: "ERROR" | "WARNING";
  code: string;
  message: string;
  path: string;
  unitId: string | null;
}

export interface ConfigurationApproval {
  actorUserId: string;
  decision: "APPROVED" | "REJECTED";
  reviewedVersion: number;
  snapshotDigest: string;
  reason: string;
  createdAt: string;
}

export interface ConfigurationVersionSummary {
  id: string;
  sequence: number;
  label: string;
  status: ConfigurationStatus;
  effectiveFrom: string;
  createdByUserId: string;
  basedOnVersionId: string | null;
  version: number;
  createdAt: string;
  updatedAt: string;
}

export interface ConfigurationVersion extends ConfigurationVersionSummary {
  reason: string | null;
  validatedAt: string | null;
  submittedAt: string | null;
  activatedAt: string | null;
  rejectedAt: string | null;
  units: ConfigurationUnitDraft[];
  edges: ConfigurationEdgeDraft[];
  candidateGroups: CandidateGroupDraft[];
  workflowTemplate: WorkflowTemplateDraft;
  findings: ConfigurationFinding[];
  approval: ConfigurationApproval | null;
}

export interface ConfigurationPreviewChange {
  type:
    | "ADDED"
    | "MOVED"
    | "RENAMED"
    | "RETIRED"
    | "UNSTAFFED"
    | "PERMISSION_AFFECTED"
    | "WORKFLOW_AFFECTED"
    | "RESTORED";
  unitId: string;
  code: string;
  message: string;
  effectiveAt: string;
}

export interface ConfigurationPreview {
  versionId: string;
  comparedWithVersionId: string | null;
  snapshotDigest: string;
  changes: ConfigurationPreviewChange[];
}

export type ConfigurationDraftInput = Pick<
  ConfigurationVersion,
  | "basedOnVersionId"
  | "candidateGroups"
  | "edges"
  | "effectiveFrom"
  | "label"
  | "units"
  | "workflowTemplate"
>;

export interface WorkflowDefinition {
  id: string;
  processId: string;
  processDefinitionKey: string;
  processVersion: number;
  compatibilityKey: string;
  checksum: string;
  approvedAt: string;
}

export interface ConfigurationSnapshotUnit {
  unitId: string;
  code: string;
  name: string;
  kind: OrganisationUnit["kind"];
  parentUnitId: string | null;
  routingEnabled: boolean;
  candidateGroups: Partial<Record<CandidateGroupDraft["purpose"], string>>;
}

export interface ConfigurationSnapshot {
  versionId: string;
  asOf: string;
  units: ConfigurationSnapshotUnit[];
}
