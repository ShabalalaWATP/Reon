import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PackageCheck } from "lucide-react";
import { useRef } from "react";

import { PageState } from "../../components/PageState";
import { productDownloadUrl } from "../../lib/api/client";
import { productApi } from "../../lib/api/productClient";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import { useAuth } from "../../lib/auth/AuthProvider";
import { useCapabilities } from "../../lib/capabilities/useCapabilities";
import { formatDate } from "../../lib/status";
import { PackageArtefactList } from "./PackageArtefactList";

export function CustomerProductPanel({
  compact = false,
  requestId,
}: {
  compact?: boolean;
  requestId: string;
}) {
  const { capabilities, isPending } = useCapabilities();
  if (isPending) return null;
  if (!capabilities.products) return <LegacyProductLink compact={compact} requestId={requestId} />;
  return <EnabledCustomerProductPanel compact={compact} requestId={requestId} />;
}

function EnabledCustomerProductPanel({
  compact,
  requestId,
}: {
  compact: boolean;
  requestId: string;
}) {
  const { session } = useAuth();
  const client = useQueryClient();
  const queryKey = protectedQueryKeys(session).requestRelease(requestId);
  const acceptanceKey = useRef(globalThis.crypto.randomUUID());
  const release = useQuery({
    queryFn: () => productApi.releaseForRequest(requestId),
    queryKey,
  });
  const acceptance = useMutation({
    mutationFn: () =>
      productApi.acceptRelease(requestId, acceptanceKey.current, session!.csrfToken),
    onSuccess: (accepted) => client.setQueryData(queryKey, accepted),
  });
  if (release.isPending)
    return compact ? (
      <span className="product-inline-state">Checking product…</span>
    ) : (
      <PageState kind="loading" title="Loading released product" />
    );
  if (release.isError)
    return compact ? (
      <span className="product-inline-state product-inline-state--error">
        Product temporarily unavailable
      </span>
    ) : (
      <PageState
        action={
          <button className="button" onClick={() => void release.refetch()}>
            Try again
          </button>
        }
        kind="error"
        title="Released product is temporarily unavailable"
      />
    );
  if (release.data === null) return <LegacyProductLink compact={compact} requestId={requestId} />;
  if (release.data.status !== "DISSEMINATED")
    return (
      <span className="product-inline-state">Product {release.data.status.toLowerCase()}</span>
    );
  const acceptanceControl = release.data.acceptedAt ? (
    <p className="product-acceptance product-acceptance--complete">
      <PackageCheck aria-hidden="true" size={16} />
      Accepted {formatDate(release.data.acceptedAt, true)}
    </p>
  ) : (
    <div className="product-acceptance">
      <p>
        Confirm that this product has been received and accepted. Opening it does not accept it
        automatically.
      </p>
      {acceptance.isError ? (
        <p className="form-banner form-banner--error" role="alert">
          Product acceptance could not be recorded.
        </p>
      ) : null}
      <button
        className="button button--primary"
        disabled={acceptance.isPending}
        onClick={() => acceptance.mutate()}
        type="button"
      >
        {acceptance.isPending ? "Recording acceptance…" : "Accept product"}
      </button>
    </div>
  );
  const note = (
    <div className="product-covering-note">
      <strong>Note from the product team</strong>
      <p>{release.data.coveringNote}</p>
    </div>
  );
  if (compact)
    return (
      <div className="customer-product-actions">
        <strong>
          <PackageCheck aria-hidden="true" size={15} />
          Product available
        </strong>
        {note}
        <PackageArtefactList artefacts={release.data.artefacts} customerAccess />
        {acceptanceControl}
      </div>
    );
  return (
    <section className="customer-product-panel" aria-labelledby="released-products-title">
      <header className="product-section-heading">
        <div>
          <span>Disseminated package v{release.data.packageVersion}</span>
          <h2 id="released-products-title">Product available</h2>
        </div>
        <p>
          Released by {release.data.releasedBy} · {formatDate(release.data.releasedAt, true)}
        </p>
      </header>
      {note}
      <PackageArtefactList artefacts={release.data.artefacts} customerAccess />
      {acceptanceControl}
    </section>
  );
}

function LegacyProductLink({ compact, requestId }: { compact: boolean; requestId: string }) {
  return (
    <div className="customer-product-actions">
      <strong>
        <PackageCheck aria-hidden="true" size={15} />
        Product available
      </strong>
      <a
        className={compact ? "button button--small" : "button button--primary"}
        href={productDownloadUrl(requestId)}
      >
        Download product
      </a>
    </div>
  );
}
