import type {
  ProductArtefactLifecycle,
  ProductPackageStatus,
} from "../../lib/api/productTypes";

export const packageStatusLabels: Record<ProductPackageStatus, string> = {
  DISSEMINATED: "Disseminated",
  DRAFT: "Draft",
  MANAGER_APPROVED: "Manager approved",
  REPLACED: "Replaced",
  REVIEW_READY: "Awaiting Manager review",
  WITHDRAWN: "Withdrawn",
};

export const artefactStatusLabels: Record<ProductArtefactLifecycle, string> = {
  CLEAN: "Ready for review",
  EXPIRED: "Expired",
  FAILED: "Validation failed",
  PENDING_UPLOAD: "Awaiting upload",
  QUARANTINED: "Scanning",
  RELEASED: "Released",
  REPLACED: "Replaced",
  WITHDRAWN: "Withdrawn",
};

export function formatBytes(bytes: number | null) {
  if (bytes === null) return "External link";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function newProductKey() {
  return crypto.randomUUID();
}
