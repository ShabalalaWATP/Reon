import { useMutation } from "@tanstack/react-query";
import { Layers3 } from "lucide-react";

import { productApi } from "../../lib/api/productClient";
import type { ProductPackage } from "../../lib/api/productTypes";
import { useAuth } from "../../lib/auth/AuthProvider";
import { useCapabilities } from "../../lib/capabilities/useCapabilities";
import { ExternalLinkForm, type ExternalLinkDraft } from "./ExternalLinkForm";
import { ManagedFileForm, type ManagedUpload } from "./ManagedFileForm";
import { PackageArtefactList } from "./PackageArtefactList";
import { newProductKey } from "./productPresentation";

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
  const upload = useMutation({
    mutationFn: async (draft: ManagedUpload) => {
      const created = await productApi.addManagedArtefact(productPackage.id, {
        expectedVersion: productPackage.version,
        filename: draft.file.name,
        idempotencyKey: newProductKey(),
        label: draft.label,
        mediaType: draft.mediaType,
        sha256: draft.sha256,
        sizeBytes: draft.file.size,
      }, csrfToken);
      const receipt = await productApi.uploadContent(
        productPackage.id,
        created.uploadIntent.id,
        draft.file,
        created.package.version,
        created.uploadIntent.uploadToken,
        csrfToken,
      );
      await productApi.completeUpload(productPackage.id, created.uploadIntent.id, {
        expectedVersion: receipt.packageVersion,
        idempotencyKey: newProductKey(),
      }, csrfToken);
    },
    onSuccess: onChanged,
  });
  const link = useMutation({
    mutationFn: (draft: ExternalLinkDraft) => productApi.addExternalLink(productPackage.id, {
      ...draft,
      expectedVersion: productPackage.version,
      idempotencyKey: newProductKey(),
    }, csrfToken),
    onSuccess: onChanged,
  });

  return (
    <section className="product-builder" aria-labelledby="package-builder-title">
      <header className="product-section-heading"><div><span>Version contents</span><h2 id="package-builder-title">Build release package</h2></div><p><Layers3 aria-hidden="true" size={16} />{productPackage.artefacts.length} of 10 artefacts</p></header>
      <PackageArtefactList artefacts={productPackage.artefacts} />
      {full ? <p className="form-banner" role="status">This package has reached the ten-artefact limit.</p> : (
        <div className="product-entry-grid">
          {capabilities.managedFileUploads ? <ManagedFileForm disabled={upload.isPending || link.isPending} onUpload={async (draft) => { await upload.mutateAsync(draft); }} /> : <p className="form-banner" role="status">Managed-file uploads are unavailable because this environment has no approved semantic/CDR scanner. Approved external links remain available.</p>}
          <ExternalLinkForm disabled={upload.isPending || link.isPending} onAdd={async (draft) => { await link.mutateAsync(draft); }} />
        </div>
      )}
    </section>
  );
}
