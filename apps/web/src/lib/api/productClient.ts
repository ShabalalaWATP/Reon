import { ApiError, apiRequest } from "./client";
import type {
  ExternalLinkInput,
  ManagedArtefactInput,
  ManagedArtefactResult,
  ProductPackage,
  ProductRelease,
  UploadContentReceipt,
} from "./productTypes";

const packagesRoot = "/product-packages";
const packagePath = (packageId: string) =>
  `${packagesRoot}/${encodeURIComponent(packageId)}`;

type VersionedCommand = {
  expectedVersion: number;
  idempotencyKey: string;
};

export const productApi = {
  createPackage: (
    input: { requestId: string; expectedVersion: number; idempotencyKey: string },
    csrfToken: string,
  ) => apiRequest<ProductPackage>(packagesRoot, { body: input, csrfToken, method: "POST" }),
  package: (packageId: string) => apiRequest<ProductPackage>(packagePath(packageId)),
  packageForRequest: (requestId: string) => apiRequest<ProductPackage>(
    `${packagesRoot}/by-request/${encodeURIComponent(requestId)}`,
  ),
  addManagedArtefact: (
    packageId: string,
    input: ManagedArtefactInput,
    csrfToken: string,
  ) => apiRequest<ManagedArtefactResult>(`${packagePath(packageId)}/managed-artefacts`, {
    body: input,
    csrfToken,
    method: "POST",
  }),
  uploadContent: (
    packageId: string,
    intentId: string,
    file: File,
    expectedVersion: number,
    uploadToken: string,
    csrfToken: string,
  ) => uploadContent(
    `${packagePath(packageId)}/uploads/${encodeURIComponent(intentId)}/content?expectedVersion=${expectedVersion}`,
    file,
    uploadToken,
    csrfToken,
  ),
  completeUpload: (
    packageId: string,
    intentId: string,
    input: VersionedCommand,
    csrfToken: string,
  ) => apiRequest<ProductPackage>(`${packagePath(packageId)}/uploads/${encodeURIComponent(intentId)}/complete`, {
    body: input,
    csrfToken,
    method: "POST",
  }),
  addExternalLink: (
    packageId: string,
    input: ExternalLinkInput,
    csrfToken: string,
  ) => apiRequest<ProductPackage>(`${packagePath(packageId)}/external-links`, {
    body: input,
    csrfToken,
    method: "POST",
  }),
  submit: (packageId: string, input: VersionedCommand, csrfToken: string) =>
    command(packageId, "submit", input, csrfToken),
  managerApprove: (
    packageId: string,
    input: VersionedCommand & { packageChecksum: string },
    csrfToken: string,
  ) => command(packageId, "manager-approve", input, csrfToken),
  disseminate: (
    packageId: string,
    input: VersionedCommand & { packageChecksum: string; externalLinkAttested: boolean },
    csrfToken: string,
  ) => apiRequest<ProductPackage>(`/releases/${encodeURIComponent(packageId)}/disseminate`, {
    body: input,
    csrfToken,
    method: "POST",
  }),
  withdraw: (
    packageId: string,
    input: VersionedCommand & { reason: string },
    csrfToken: string,
  ) => apiRequest<ProductPackage>(`/releases/${encodeURIComponent(packageId)}/withdraw`, {
    body: input,
    csrfToken,
    method: "POST",
  }),
  releaseForRequest: (requestId: string) =>
    apiRequest<ProductRelease>(`/releases/requests/${encodeURIComponent(requestId)}`),
};

export const productArtefactUrl = (artefactId: string, kind: ProductRelease["artefacts"][number]["kind"]) =>
  `/api/v1/releases/artefacts/${encodeURIComponent(artefactId)}/${kind === "MANAGED_FILE" ? "download" : "open"}`;

function command<T extends VersionedCommand>(
  packageId: string,
  action: string,
  input: T,
  csrfToken: string,
) {
  return apiRequest<ProductPackage>(`${packagePath(packageId)}/${action}`, {
    body: input,
    csrfToken,
    method: "POST",
  });
}

async function uploadContent(path: string, file: File, uploadToken: string, csrfToken: string) {
  const response = await fetch(`/api/v1${path}`, {
    body: file,
    credentials: "include",
    headers: {
      Accept: "application/json",
      "Content-Type": file.type || "application/octet-stream",
      "X-CSRF-Token": csrfToken,
      "X-Upload-Token": uploadToken,
    },
    method: "PUT",
  });
  if (!response.ok) {
    let message = `Upload failed with status ${response.status}.`;
    try {
      const body = await response.json() as { detail?: string | { message?: string } };
      message = typeof body.detail === "string" ? body.detail : body.detail?.message ?? message;
    } catch {
      // The status remains useful when an upstream response is not JSON.
    }
    throw new ApiError(message, response.status);
  }
  return response.json() as Promise<UploadContentReceipt>;
}
