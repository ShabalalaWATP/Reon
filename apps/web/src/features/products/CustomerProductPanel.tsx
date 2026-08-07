import { useQuery } from "@tanstack/react-query";
import { PackageCheck } from "lucide-react";

import { PageState } from "../../components/PageState";
import { ApiError, productDownloadUrl } from "../../lib/api/client";
import { productApi } from "../../lib/api/productClient";
import { useAuth } from "../../lib/auth/AuthProvider";
import { useCapabilities } from "../../lib/capabilities/useCapabilities";
import { formatDate } from "../../lib/status";
import { PackageArtefactList } from "./PackageArtefactList";

export function CustomerProductPanel({ compact = false, requestId }: { compact?: boolean; requestId: string }) {
  const { capabilities, isPending } = useCapabilities();
  if (isPending) return null;
  if (!capabilities.products) return <LegacyProductLink compact={compact} requestId={requestId} />;
  return <EnabledCustomerProductPanel compact={compact} requestId={requestId} />;
}

function EnabledCustomerProductPanel({ compact, requestId }: { compact: boolean; requestId: string }) {
  const { session } = useAuth();
  const release = useQuery({
    queryFn: () => productApi.releaseForRequest(requestId),
    queryKey: ["protected", session!.user.id, "request-release", requestId],
  });
  if (release.isPending) return compact ? <span className="product-inline-state">Checking product…</span> : <PageState kind="loading" title="Loading released product" />;
  if (release.isError && release.error instanceof ApiError && release.error.status === 404) return <LegacyProductLink compact={compact} requestId={requestId} />;
  if (release.isError) return compact ? <span className="product-inline-state product-inline-state--error">Product temporarily unavailable</span> : <PageState action={<button className="button" onClick={() => void release.refetch()}>Try again</button>} kind="error" title="Released product is temporarily unavailable" />;
  if (release.data.status !== "DISSEMINATED") return <span className="product-inline-state">Product {release.data.status.toLowerCase()}</span>;
  if (compact) return <div className="customer-product-actions"><strong><PackageCheck aria-hidden="true" size={15} />Product available</strong><PackageArtefactList artefacts={release.data.artefacts} customerAccess /></div>;
  return <section className="customer-product-panel" aria-labelledby="released-products-title"><header className="product-section-heading"><div><span>Disseminated package v{release.data.packageVersion}</span><h2 id="released-products-title">Product available</h2></div><p>Released by {release.data.releasedBy} · {formatDate(release.data.releasedAt, true)}</p></header><PackageArtefactList artefacts={release.data.artefacts} customerAccess /></section>;
}

function LegacyProductLink({ compact, requestId }: { compact: boolean; requestId: string }) {
  return <div className="customer-product-actions"><strong><PackageCheck aria-hidden="true" size={15} />Product available</strong><a className={compact ? "button button--small" : "button button--primary"} href={productDownloadUrl(requestId)}>Download product</a></div>;
}
