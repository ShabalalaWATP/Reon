export type ManagedUpload = {
  file: File;
  label: string;
  mediaType: string;
  sha256: string;
};

export type ManagedUploadStage =
  "waiting" | "creating" | "uploading" | "scanning" | "complete" | "error";

export type ManagedUploadProgress = {
  completeIdempotencyKey: string;
  createIdempotencyKey: string;
  draft: ManagedUpload;
  error?: string;
  stage: ManagedUploadStage;
};

export function prepareManagedUploads(
  drafts: ManagedUpload[],
  newKey: () => string,
): ManagedUploadProgress[] {
  return drafts.map((draft) => {
    const createIdempotencyKey = newKey();
    const completeIdempotencyKey = newKey();
    return {
      completeIdempotencyKey,
      createIdempotencyKey,
      draft,
      stage: "waiting",
    };
  });
}

export function unfinishedManagedUploads(uploads: readonly ManagedUploadProgress[]) {
  return uploads.filter((upload) => upload.stage !== "complete");
}

export function managedUploadStageLabel(upload: ManagedUploadProgress) {
  if (upload.stage === "creating") return "Creating secure upload";
  if (upload.stage === "uploading") return "Uploading";
  if (upload.stage === "scanning") return "Scanning";
  if (upload.stage === "complete") return "Complete";
  if (upload.stage === "error") return `Upload stopped: ${upload.error ?? "Unknown error"}`;
  return "Waiting";
}

export function uploadErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : "The file could not be uploaded.";
}
