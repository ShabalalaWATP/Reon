import { useCallback, useEffect, useRef, useState } from "react";

import { productApi } from "../../lib/api/productClient";
import type { ProductPackage } from "../../lib/api/productTypes";
import { newProductKey } from "./productPresentation";
import {
  prepareManagedUploads,
  unfinishedManagedUploads,
  uploadErrorMessage,
  type ManagedUpload,
  type ManagedUploadProgress,
} from "./managedUploadModel";

type ManagedUploadApi = Pick<
  typeof productApi,
  "addManagedArtefact" | "completeUpload" | "package" | "uploadContent"
>;

type ManagedUploadControllerOptions = {
  api?: ManagedUploadApi;
  csrfToken: string;
  newKey?: () => string;
  onChanged: () => Promise<unknown>;
  productPackage: ProductPackage;
};

export function useManagedPackageUploads({
  api = productApi,
  csrfToken,
  newKey = newProductKey,
  onChanged,
  productPackage,
}: ManagedUploadControllerOptions) {
  const [uploads, setUploads] = useState<ManagedUploadProgress[]>([]);
  const [isPending, setIsPending] = useState(false);
  const uploadsRef = useRef<ManagedUploadProgress[]>([]);
  const packageIdRef = useRef(productPackage.id);
  const packageVersionRef = useRef(productPackage.version);
  const runningRef = useRef(false);

  useEffect(() => {
    if (packageIdRef.current !== productPackage.id) {
      packageIdRef.current = productPackage.id;
      packageVersionRef.current = productPackage.version;
      uploadsRef.current = [];
      setUploads([]);
      return;
    }
    packageVersionRef.current = Math.max(packageVersionRef.current, productPackage.version);
  }, [productPackage.id, productPackage.version]);

  const replaceUpload = useCallback(
    (createIdempotencyKey: string, change: Partial<ManagedUploadProgress>) => {
      const next = uploadsRef.current.map((upload) =>
        upload.createIdempotencyKey === createIdempotencyKey ? { ...upload, ...change } : upload,
      );
      uploadsRef.current = next;
      setUploads(next);
    },
    [],
  );

  const refreshView = useCallback(async () => {
    try {
      await onChanged();
    } catch {
      // Upload success and retry state must not be replaced by a view refresh error.
    }
  }, [onChanged]);

  const reconcileVersion = useCallback(async () => {
    const authoritative = await api.package(packageIdRef.current);
    packageVersionRef.current = authoritative.version;
  }, [api]);

  const runUpload = useCallback(
    async (upload: ManagedUploadProgress) => {
      const id = upload.createIdempotencyKey;
      // Replaying every phase is deliberate: stable keys let the API return the
      // persisted reservation or completion after a response is lost.
      replaceUpload(id, { error: undefined, stage: "creating" });
      try {
        const created = await api.addManagedArtefact(
          packageIdRef.current,
          {
            expectedVersion: packageVersionRef.current,
            filename: upload.draft.file.name,
            idempotencyKey: upload.createIdempotencyKey,
            label: upload.draft.label,
            mediaType: upload.draft.mediaType,
            sha256: upload.draft.sha256,
            sizeBytes: upload.draft.file.size,
          },
          csrfToken,
        );
        packageVersionRef.current = created.package.version;
        replaceUpload(id, { stage: "uploading" });
        const receipt = await api.uploadContent(
          packageIdRef.current,
          created.uploadIntent.id,
          upload.draft.file,
          created.package.version,
          created.uploadIntent.uploadToken,
          csrfToken,
        );
        packageVersionRef.current = receipt.packageVersion;
        replaceUpload(id, { stage: "scanning" });
        const completed = await api.completeUpload(
          packageIdRef.current,
          created.uploadIntent.id,
          {
            expectedVersion: receipt.packageVersion,
            idempotencyKey: upload.completeIdempotencyKey,
          },
          csrfToken,
        );
        packageVersionRef.current = completed.version;
        replaceUpload(id, { stage: "complete" });
      } catch (error) {
        replaceUpload(id, { error: uploadErrorMessage(error), stage: "error" });
        throw error;
      }
    },
    [api, csrfToken, replaceUpload],
  );

  const runBatch = useCallback(
    async (batch: ManagedUploadProgress[]) => {
      if (runningRef.current) throw new Error("An upload is already in progress.");
      runningRef.current = true;
      setIsPending(true);
      try {
        for (const upload of unfinishedManagedUploads(batch)) {
          await runUpload(upload);
        }
        await refreshView();
      } catch (error) {
        try {
          await reconcileVersion();
        } catch {
          // The original upload failure remains the actionable error.
        }
        await refreshView();
        throw error;
      } finally {
        runningRef.current = false;
        setIsPending(false);
      }
    },
    [reconcileVersion, refreshView, runUpload],
  );

  const start = useCallback(
    async (drafts: ManagedUpload[]) => {
      if (unfinishedManagedUploads(uploadsRef.current).length > 0) {
        throw new Error("Retry the unfinished files before starting another upload.");
      }
      const prepared = prepareManagedUploads(drafts, newKey);
      uploadsRef.current = prepared;
      setUploads(prepared);
      await runBatch(prepared);
    },
    [newKey, runBatch],
  );

  const retry = useCallback(async () => {
    await reconcileVersion();
    await runBatch(uploadsRef.current);
  }, [reconcileVersion, runBatch]);

  const unfinished = unfinishedManagedUploads(uploads);
  return {
    hasUnfinished: unfinished.length > 0,
    isPending,
    retry,
    start,
    unfinishedCount: unfinished.length,
    uploads,
  };
}
