import { useMutation } from "@tanstack/react-query";
import { FileUp, Layers3, Link2 } from "lucide-react";
import { useState } from "react";

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
  const [source, setSource] = useState<ProductSource | null>(null);
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
  const sourceLocked = anyTrue(
    managedUploads.isPending,
    managedUploads.hasUnfinished,
    link.isPending,
  );

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
        <div className="product-source-workspace">
          <ProductSourceSelector
            managedUploadsAvailable={capabilities.managedFileUploads}
            onChange={setSource}
            selected={source}
            sourceLocked={sourceLocked}
          />
          {!capabilities.managedFileUploads ? (
            <p className="form-banner" role="status">
              Managed-file uploads are unavailable because this environment has no approved
              semantic/CDR scanner. Approved external links remain available.
            </p>
          ) : null}
          {source === "managed" && capabilities.managedFileUploads ? (
            <div className="product-source-panel">
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
            </div>
          ) : null}
          {source === "link" ? (
            <div className="product-source-panel">
              <ExternalLinkForm
                disabled={sourceLocked}
                onAdd={async (draft) => {
                  await link.mutateAsync(draft);
                }}
              />
            </div>
          ) : null}
          {source === null ? (
            <p className="product-source-prompt">Choose one option to add the product.</p>
          ) : null}
        </div>
      )}
    </section>
  );
}

type ProductSource = "managed" | "link";

function ProductSourceSelector({
  managedUploadsAvailable,
  onChange,
  selected,
  sourceLocked,
}: {
  managedUploadsAvailable: boolean;
  onChange: (source: ProductSource) => void;
  selected: ProductSource | null;
  sourceLocked: boolean;
}) {
  return (
    <fieldset className="product-source-selector">
      <legend>How do you want to add the product?</legend>
      <p>Select the source first. MIST will show only the fields you need.</p>
      <div className="product-source-options">
        <button
          aria-pressed={selected === "managed"}
          className="product-source-option"
          disabled={!managedUploadsAvailable || sourceLocked}
          onClick={() => onChange("managed")}
          type="button"
        >
          <FileUp aria-hidden="true" size={21} />
          <span>
            <strong>Upload product to MIST</strong>
            <small>Store and scan a document or image securely.</small>
          </span>
        </button>
        <button
          aria-pressed={selected === "link"}
          className="product-source-option"
          disabled={sourceLocked}
          onClick={() => onChange("link")}
          type="button"
        >
          <Link2 aria-hidden="true" size={21} />
          <span>
            <strong>Add a product link</strong>
            <small>Point the customer to an approved HTTPS destination.</small>
          </span>
        </button>
      </div>
    </fieldset>
  );
}

function anyTrue(...values: boolean[]) {
  return values.includes(true);
}
