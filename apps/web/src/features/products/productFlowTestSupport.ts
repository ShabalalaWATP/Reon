import { vi } from "vitest";

import type { ProductArtefact, ProductPackage, ProductRelease } from "../../lib/api/productTypes";
import type { Session } from "../../lib/api/types";
import { requestSummary, staffSession } from "../../test/fixtures";

export const artefacts: ProductArtefact[] = [
  {
    id: "art-file",
    packageId: "pkg-1",
    position: 1,
    kind: "MANAGED_FILE",
    lifecycle: "CLEAN",
    label: "Decision brief",
    filename: "brief.pdf",
    mediaType: "application/pdf",
    sizeBytes: 2048,
    sha256: "a".repeat(64),
    destinationDomain: null,
    expiresAt: null,
    scanResult: "CLEAN",
    scanReason: null,
    releasedAt: null,
    version: 1,
  },
  {
    id: "art-link",
    packageId: "pkg-1",
    position: 2,
    kind: "EXTERNAL_LINK",
    lifecycle: "CLEAN",
    label: "Interactive product",
    filename: null,
    mediaType: null,
    sizeBytes: null,
    sha256: null,
    destinationDomain: "products.example.test",
    expiresAt: "2099-08-10T10:00:00Z",
    scanResult: null,
    scanReason: null,
    releasedAt: null,
    version: 1,
  },
];

export const basePackage: ProductPackage = {
  id: "pkg-1",
  requestId: requestSummary.id,
  requestReference: requestSummary.reference,
  requestTitle: requestSummary.title,
  requestStatus: "IN_PROGRESS",
  authorDisplayName: "Lewis Ferguson",
  packageVersion: 2,
  policyVersion: 2,
  status: "DRAFT",
  coveringNote: null,
  packageChecksum: null,
  version: 1,
  artefacts,
  managerApprovedAt: null,
  managerApprovedBy: null,
  disseminatedAt: null,
  disseminatedBy: null,
  withdrawalReason: null,
};

export const release: ProductRelease = {
  packageId: basePackage.id,
  requestId: requestSummary.id,
  packageVersion: 2,
  status: "DISSEMINATED",
  releasedAt: "2026-08-07T10:00:00Z",
  releasedBy: "QC Manager",
  coveringNote: "Synthetic note to the Customer.",
  acceptedAt: null,
  artefacts: artefacts.map((item) => ({
    ...item,
    lifecycle: "RELEASED",
    releasedAt: "2026-08-07T10:00:00Z",
  })),
};

export function roleSession(role: Session["user"]["role"]): Session {
  return { ...staffSession, user: { ...staffSession.user, role } };
}

export function mockCrypto() {
  vi.stubGlobal("crypto", {
    randomUUID: () => "99999999-9999-4999-8999-999999999999",
    subtle: { digest: vi.fn().mockResolvedValue(new Uint8Array(32).buffer) },
  });
}
