import { describe, expect, it } from "vitest";

import {
  managedUploadStageLabel,
  prepareManagedUploads,
  unfinishedManagedUploads,
  uploadErrorMessage,
  type ManagedUpload,
} from "./managedUploadModel";

const file = new File(["brief"], "brief.pdf", { type: "application/pdf" });
const draft: ManagedUpload = {
  file,
  label: "Brief",
  mediaType: "application/pdf",
  sha256: "a".repeat(64),
};

describe("managed upload model", () => {
  it("prepares both stable keys before network work begins", () => {
    const keys = ["create-one", "complete-one", "create-two", "complete-two"];
    const uploads = prepareManagedUploads([draft, { ...draft, label: "Second" }], () =>
      keys.shift()!,
    );

    expect(uploads).toEqual([
      expect.objectContaining({
        completeIdempotencyKey: "complete-one",
        createIdempotencyKey: "create-one",
        stage: "waiting",
      }),
      expect.objectContaining({
        completeIdempotencyKey: "complete-two",
        createIdempotencyKey: "create-two",
        stage: "waiting",
      }),
    ]);
    expect(keys).toHaveLength(0);
  });

  it("selects only unfinished work and describes every state", () => {
    const [base] = prepareManagedUploads([draft], () => "key");
    const stages = ["waiting", "creating", "uploading", "scanning", "complete"] as const;
    expect(stages.map((stage) => managedUploadStageLabel({ ...base, stage }))).toEqual([
      "Waiting",
      "Creating secure upload",
      "Uploading",
      "Scanning",
      "Complete",
    ]);
    expect(managedUploadStageLabel({ ...base, error: undefined, stage: "error" })).toBe(
      "Upload stopped: Unknown error",
    );
    expect(managedUploadStageLabel({ ...base, error: "Unavailable", stage: "error" })).toBe(
      "Upload stopped: Unavailable",
    );
    expect(unfinishedManagedUploads([{ ...base, stage: "complete" }, base])).toEqual([base]);
    expect(uploadErrorMessage(new Error("Stopped"))).toBe("Stopped");
    expect(uploadErrorMessage("offline")).toBe("The file could not be uploaded.");
  });
});
