import { useMutation } from "@tanstack/react-query";
import { Layers3 } from "lucide-react";

import { productApi } from "../../lib/api/productClient";
import type { ProductPackage } from "../../lib/api/productTypes";
import { useAuth } from "../../lib/auth/AuthProvider";
import { useCapabilities } from "../../lib/capabilities/useCapabilities";
import { ExternalLinkForm, type ExternalLinkDraft } from "./ExternalLinkForm";
import { ManagedFileForm } from "./ManagedFileForm";
import { PackageArtefactList } from "./PackageArtefactList";
import { newProductKey } from "./productPresentation";
import { useManagedPackageUploads } from "./useManagedPackageUploads";

export function PackageBuilder({
  onChanged,
  productPackage,
}: {
  onChanged: () => Promise<unknown>;
  productPackage: ProductPackage;
}) {
  const { session } = useAuth();
  const { capabilities } = useCapabilities();
  const csrfToken = session!.csrfToken;
  const full = productPackage.artefacts.length >= 10;
  const managedUploads = useManagedPackageUploads({
    csrfToken,
    onChanged,
    productPackage,
  });
  const link = useMutation({
    mutationFn: (draft: ExternalLinkDraft) =>
      productApi.addExternalLink(
        productPackage.id,
        {
          ...draft,
          expectedVersion: productPackage.version,
          idempotencyKey: newProductKey(),
        },
        csrfToken,
      ),
    onSuccess: onChanged,
  });

  return (
    <section className="product-builder" aria-labelledby="package-builder-title">
      <header className="product-section-heading">
        <div>
          <span>Version contents</span>
          <h2 id="package-builder-title">Build release package</h2>
        </div>
        <p>
          <Layers3 aria-hidden="true" size={16} />
          {productPackage.artefacts.length} of 10 artefacts
        </p>
      </header>
      <PackageArtefactList artefacts={productPackage.artefacts} />
      {full && !managedUploads.hasUnfinished ? (
        <p className="form-banner" role="status">
          This package has reached the ten-artefact limit.
        </p>
      ) : (
        <div className="product-entry-grid">
          {capabilities.managedFileUploads ? (
            <ManagedFileForm
              disabled={link.isPending}
              maximumFiles={Math.max(
                managedUploads.unfinishedCount,
                10 - productPackage.artefacts.length,
              )}
              onRetry={managedUploads.retry}
              onUpload={managedUploads.start}
              progress={managedUploads.uploads}
              uploading={managedUploads.isPending}
            />
          ) : (
            <p className="form-banner" role="status">
              Managed-file uploads are unavailable because this environment has no approved
              semantic/CDR scanner. Approved external links remain available.
            </p>
          )}
          <ExternalLinkForm
            disabled={anyTrue(
              managedUploads.isPending,
              managedUploads.hasUnfinished,
              link.isPending,
            )}
            onAdd={async (draft) => {
              await link.mutateAsync(draft);
            }}
          />
        </div>
      )}
    </section>
  );
}

function anyTrue(...values: boolean[]) {
  return values.includes(true);
}
