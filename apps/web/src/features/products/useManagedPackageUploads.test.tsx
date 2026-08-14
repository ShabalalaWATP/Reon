import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type {
  ManagedArtefactResult,
  ProductPackage,
  UploadContentReceipt,
} from "../../lib/api/productTypes";
import type { ManagedUpload } from "./managedUploadModel";
import { useManagedPackageUploads } from "./useManagedPackageUploads";

type ManagedUploadApi = NonNullable<Parameters<typeof useManagedPackageUploads>[0]["api"]>;

const emptyPackage: ProductPackage = {
  artefacts: [],
  authorDisplayName: "Ben Doak",
  coveringNote: null,
  disseminatedAt: null,
  disseminatedBy: null,
  id: "package-1",
  managerApprovedAt: null,
  managerApprovedBy: null,
  packageChecksum: null,
  packageVersion: 1,
  policyVersion: 2,
  requestId: "request-1",
  requestReference: "SR-1",
  requestStatus: "IN_PROGRESS",
  requestTitle: "Synthetic request",
  status: "DRAFT",
  version: 1,
  withdrawalReason: null,
};

const drafts: ManagedUpload[] = [
  upload("first.pdf", "First", "a"),
  upload("second.pdf", "Second", "b"),
];

describe("managed package upload controller", () => {
  it("retains partial progress, reconciles version and retries only unfinished files", async () => {
    let packageVersion = 1;
    let secondUploadAttempts = 0;
    const createKeys: string[] = [];
    const createVersions: number[] = [];
    const api: ManagedUploadApi = {
      addManagedArtefact: vi.fn(async (_packageId, input) => {
        createKeys.push(input.idempotencyKey);
        createVersions.push(input.expectedVersion);
        packageVersion += 1;
        return intent(input.filename, packageVersion);
      }),
      uploadContent: vi.fn(async (_packageId, intentId) => {
        if (intentId === "intent-second.pdf" && secondUploadAttempts++ === 0) {
          packageVersion += 1;
          throw new Error("Connection lost after upload.");
        }
        packageVersion += 1;
        return receipt(intentId, packageVersion);
      }),
      completeUpload: vi.fn(async () => ({ ...emptyPackage, version: ++packageVersion })),
      package: vi.fn(async () => ({ ...emptyPackage, version: packageVersion })),
    };
    const keys = ["create-1", "complete-1", "create-2", "complete-2"];
    const onChanged = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() =>
      useManagedPackageUploads({
        api,
        csrfToken: "csrf",
        newKey: () => keys.shift()!,
        onChanged,
        productPackage: emptyPackage,
      }),
    );

    let startError: unknown;
    await act(async () => {
      try {
        await result.current.start(drafts);
      } catch (error) {
        startError = error;
      }
    });
    expect(startError).toEqual(
      expect.objectContaining({
        message: "Connection lost after upload.",
      }),
    );
    expect(result.current.uploads.map((item) => item.stage)).toEqual(["complete", "error"]);
    expect(api.completeUpload).toHaveBeenCalledTimes(1);
    expect(api.package).toHaveBeenCalledTimes(1);

    await act(async () => result.current.retry());

    expect(result.current.uploads.map((item) => item.stage)).toEqual(["complete", "complete"]);
    expect(createKeys).toEqual(["create-1", "create-2", "create-2"]);
    expect(createVersions).toEqual([1, 4, 6]);
    expect(api.completeUpload).toHaveBeenCalledTimes(2);
    expect(api.package).toHaveBeenCalledTimes(2);
    expect(onChanged).toHaveBeenCalledTimes(2);
  });

  it("reuses the create key after a lost create response", async () => {
    let createAttempts = 0;
    let packageVersion = 1;
    const createKeys: string[] = [];
    const api: ManagedUploadApi = {
      addManagedArtefact: vi.fn(async (_packageId, input) => {
        createKeys.push(input.idempotencyKey);
        packageVersion = 2;
        if (createAttempts++ === 0) throw new Error("Response lost after reservation.");
        return intent(input.filename, packageVersion);
      }),
      uploadContent: vi.fn(async (_packageId, intentId) => receipt(intentId, ++packageVersion)),
      completeUpload: vi.fn(async () => ({ ...emptyPackage, version: ++packageVersion })),
      package: vi.fn(async () => ({ ...emptyPackage, version: packageVersion })),
    };
    const keys = ["stable-create", "stable-complete"];
    const { result } = renderHook(() =>
      useManagedPackageUploads({
        api,
        csrfToken: "csrf",
        newKey: () => keys.shift()!,
        onChanged: vi.fn().mockResolvedValue(undefined),
        productPackage: emptyPackage,
      }),
    );

    let startError: unknown;
    await act(async () => {
      try {
        await result.current.start([drafts[0]]);
      } catch (error) {
        startError = error;
      }
    });
    expect(startError).toEqual(
      expect.objectContaining({
        message: "Response lost after reservation.",
      }),
    );
    await act(async () => result.current.retry());

    expect(createKeys).toEqual(["stable-create", "stable-create"]);
    expect(result.current.uploads[0].stage).toBe("complete");
  });

  it("replays the same completion key after a lost completion response", async () => {
    let completionAttempts = 0;
    let packageVersion = 1;
    const completionKeys: string[] = [];
    const api: ManagedUploadApi = {
      addManagedArtefact: vi.fn(async (_packageId, input) =>
        intent(input.filename, ++packageVersion),
      ),
      uploadContent: vi.fn(async (_packageId, intentId) => receipt(intentId, ++packageVersion)),
      completeUpload: vi.fn(async (_packageId, _intentId, command) => {
        completionKeys.push(command.idempotencyKey);
        packageVersion += 1;
        if (completionAttempts++ === 0) throw new Error("Response lost after completion.");
        return { ...emptyPackage, version: packageVersion };
      }),
      package: vi.fn(async () => ({ ...emptyPackage, version: packageVersion })),
    };
    const keys = ["create", "complete"];
    const { result } = renderHook(() =>
      useManagedPackageUploads({
        api,
        csrfToken: "csrf",
        newKey: () => keys.shift()!,
        onChanged: vi.fn().mockResolvedValue(undefined),
        productPackage: emptyPackage,
      }),
    );

    let startError: unknown;
    await act(async () => {
      try {
        await result.current.start([drafts[0]]);
      } catch (error) {
        startError = error;
      }
    });
    expect(startError).toEqual(
      expect.objectContaining({
        message: "Response lost after completion.",
      }),
    );
    await act(async () => result.current.retry());

    expect(completionKeys).toEqual(["complete", "complete"]);
    expect(result.current.uploads[0].stage).toBe("complete");
  });

  it("guards concurrent work, refresh errors and a changed package", async () => {
    let releaseCreate!: () => void;
    const pendingCreate = new Promise<void>((resolve) => {
      releaseCreate = resolve;
    });
    const api: ManagedUploadApi = {
      addManagedArtefact: vi.fn(async (_packageId, input) => {
        await pendingCreate;
        return intent(input.filename, 2);
      }),
      uploadContent: vi.fn(async (_packageId, intentId) => receipt(intentId, 3)),
      completeUpload: vi.fn(async () => ({ ...emptyPackage, version: 4 })),
      package: vi.fn(async () => ({ ...emptyPackage, version: 4 })),
    };
    const onChanged = vi.fn().mockRejectedValue(new Error("Refresh unavailable"));
    const { result, rerender } = renderHook(
      ({ productPackage }) =>
        useManagedPackageUploads({
          api,
          csrfToken: "csrf",
          newKey: () => crypto.randomUUID(),
          onChanged,
          productPackage,
        }),
      { initialProps: { productPackage: emptyPackage } },
    );

    let firstRun!: Promise<void>;
    act(() => {
      firstRun = result.current.start([drafts[0]]);
    });
    await waitFor(() => expect(result.current.isPending).toBe(true));
    await expect(result.current.start([drafts[1]])).rejects.toThrow(
      "Retry the unfinished files before starting another upload.",
    );
    releaseCreate();
    await act(async () => firstRun);
    expect(result.current.uploads[0].stage).toBe("complete");

    rerender({ productPackage: { ...emptyPackage, id: "package-2", version: 1 } });
    await waitFor(() => expect(result.current.uploads).toEqual([]));
  });
});

function upload(filename: string, label: string, checksum: string): ManagedUpload {
  return {
    file: new File([filename], filename, { type: "application/pdf" }),
    label,
    mediaType: "application/pdf",
    sha256: checksum.repeat(64),
  };
}

function intent(filename: string, version: number): ManagedArtefactResult {
  return {
    artefact: {
      destinationDomain: null,
      expiresAt: null,
      filename,
      id: `artefact-${filename}`,
      kind: "MANAGED_FILE",
      label: filename,
      lifecycle: "PENDING_UPLOAD",
      mediaType: "application/pdf",
      packageId: emptyPackage.id,
      position: 1,
      releasedAt: null,
      scanReason: null,
      scanResult: null,
      sha256: "a".repeat(64),
      sizeBytes: filename.length,
      version: 1,
    },
    package: { ...emptyPackage, version },
    uploadIntent: {
      expiresAt: "2099-01-01T00:00:00Z",
      id: `intent-${filename}`,
      objectKey: `opaque-${filename}`,
      uploadToken: `token-${filename}`,
    },
  };
}

function receipt(intentId: string, packageVersion: number): UploadContentReceipt {
  return {
    intentId,
    packageVersion,
    sha256: "a".repeat(64),
    sizeBytes: 10,
    uploadedAt: "2026-08-14T10:00:00Z",
  };
}
