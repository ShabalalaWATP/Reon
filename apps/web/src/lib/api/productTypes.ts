export type ProductPackageStatus =
  "DRAFT" | "REVIEW_READY" | "MANAGER_APPROVED" | "DISSEMINATED" | "REPLACED" | "WITHDRAWN";

export type ProductArtefactLifecycle =
  | "PENDING_UPLOAD"
  | "QUARANTINED"
  | "CLEAN"
  | "RELEASED"
  | "FAILED"
  | "REPLACED"
  | "WITHDRAWN"
  | "EXPIRED";

export interface ProductArtefact {
  id: string;
  packageId: string;
  position: number;
  kind: "MANAGED_FILE" | "EXTERNAL_LINK";
  lifecycle: ProductArtefactLifecycle;
  label: string;
  filename: string | null;
  mediaType: string | null;
  sizeBytes: number | null;
  sha256: string | null;
  destinationDomain: string | null;
  reviewDestinationUrl?: string | null;
  reviewUrl?: string | null;
  expiresAt: string | null;
  scanResult: "CLEAN" | "FAILED" | "UNKNOWN" | "TIMED_OUT" | null;
  scanReason: string | null;
  releasedAt: string | null;
  version: number;
}

export interface ProductPackage {
  id: string;
  requestId: string;
  requestReference: string;
  requestTitle: string;
  requestStatus: string;
  packageVersion: number;
  policyVersion: number;
  status: ProductPackageStatus;
  coveringNote: string | null;
  packageChecksum: string | null;
  version: number;
  authorDisplayName: string;
  managerApprovedBy: string | null;
  managerApprovedAt: string | null;
  disseminatedBy: string | null;
  disseminatedAt: string | null;
  withdrawalReason: string | null;
  artefacts: ProductArtefact[];
}

export interface UploadIntent {
  id: string;
  objectKey: string;
  uploadToken: string;
  expiresAt: string;
}

export interface ManagedArtefactResult {
  package: ProductPackage;
  artefact: ProductArtefact;
  uploadIntent: UploadIntent;
}

export interface ProductRelease {
  packageId: string;
  requestId: string;
  packageVersion: number;
  status: "DISSEMINATED" | "WITHDRAWN" | "REPLACED";
  releasedAt: string;
  releasedBy: string;
  coveringNote: string;
  acceptedAt: string | null;
  artefacts: ProductArtefact[];
}

export interface UploadContentReceipt {
  intentId: string;
  sizeBytes: number;
  sha256: string;
  uploadedAt: string;
  packageVersion: number;
}

export interface ManagedArtefactInput {
  expectedVersion: number;
  label: string;
  filename: string;
  mediaType: string;
  sizeBytes: number;
  sha256: string;
  idempotencyKey: string;
}

export interface ExternalLinkInput {
  expectedVersion: number;
  label: string;
  url: string;
  expiresAt?: string;
  idempotencyKey: string;
}
