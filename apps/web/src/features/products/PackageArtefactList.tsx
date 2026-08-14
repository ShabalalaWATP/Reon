import { ExternalLink, FileText, LockKeyhole } from "lucide-react";

import { productArtefactUrl } from "../../lib/api/productClient";
import type { ProductArtefact } from "../../lib/api/productTypes";
import { formatDate } from "../../lib/status";
import { artefactStatusLabels, formatBytes } from "./productPresentation";

export function PackageArtefactList({
  artefacts,
  customerAccess = false,
}: {
  artefacts: ProductArtefact[];
  customerAccess?: boolean;
}) {
  if (!artefacts.length)
    return <p className="inline-empty">No artefacts have been added to this version.</p>;
  return (
    <ol className="product-artefact-list" aria-label="Package artefacts">
      {artefacts.map((artefact, index) => (
        <PackageArtefactRow
          artefact={artefact}
          customerAccess={customerAccess}
          index={index}
          key={artefact.id}
        />
      ))}
    </ol>
  );
}

function PackageArtefactRow({
  artefact,
  customerAccess,
  index,
}: {
  artefact: ProductArtefact;
  customerAccess: boolean;
  index: number;
}) {
  const reviewDestination = customerAccess ? null : (artefact.reviewDestinationUrl ?? null);
  return (
    <li>
      <span className="product-artefact-index">{String(index + 1).padStart(2, "0")}</span>
      <ArtefactIcon kind={artefact.kind} />
      <ArtefactDescription artefact={artefact} reviewDestination={reviewDestination} />
      <span className={`product-state product-state--${artefact.lifecycle.toLowerCase()}`}>
        {artefactStatusLabels[artefact.lifecycle]}
      </span>
      <CustomerArtefactAction artefact={artefact} customerAccess={customerAccess} />
      <ReviewArtefactActions artefact={artefact} customerAccess={customerAccess} />
    </li>
  );
}

function ArtefactIcon({ kind }: { kind: ProductArtefact["kind"] }) {
  return (
    <span className="product-artefact-icon">
      {kind === "MANAGED_FILE" ? (
        <FileText aria-hidden="true" size={18} />
      ) : (
        <ExternalLink aria-hidden="true" size={18} />
      )}
    </span>
  );
}

function ArtefactDescription({
  artefact,
  reviewDestination,
}: {
  artefact: ProductArtefact;
  reviewDestination: string | null;
}) {
  const destination =
    artefact.filename ?? artefact.destinationDomain ?? "Approved external destination";
  return (
    <span className="product-artefact-copy">
      <strong>{artefact.label}</strong>
      <small>
        {destination} · {formatBytes(artefact.sizeBytes)}
      </small>
      {reviewDestination ? <small className="mono-ref">{reviewDestination}</small> : null}
      {artefact.expiresAt ? <small>Expires {formatDate(artefact.expiresAt, true)}</small> : null}
    </span>
  );
}

function CustomerArtefactAction({
  artefact,
  customerAccess,
}: {
  artefact: ProductArtefact;
  customerAccess: boolean;
}) {
  if (!customerAccess) return null;
  if (artefact.lifecycle !== "RELEASED") {
    return (
      <span className="product-unavailable">
        <LockKeyhole aria-hidden="true" size={14} />
        Unavailable
      </span>
    );
  }
  const external = artefact.kind === "EXTERNAL_LINK";
  return (
    <a
      className="button button--quiet"
      href={productArtefactUrl(artefact.id, artefact.kind)}
      rel={external ? "noopener noreferrer" : undefined}
      target={external ? "_blank" : undefined}
    >
      {external ? "Open product" : "Download"}
    </a>
  );
}

function ReviewArtefactActions({
  artefact,
  customerAccess,
}: {
  artefact: ProductArtefact;
  customerAccess: boolean;
}) {
  if (customerAccess) return null;
  return (
    <>
      {artefact.reviewUrl ? (
        <a
          className="button button--quiet"
          href={artefact.reviewUrl}
          rel="noopener noreferrer"
          target="_blank"
        >
          Inspect file
        </a>
      ) : null}
      {artefact.reviewDestinationUrl ? (
        <a
          className="button button--quiet"
          href={artefact.reviewDestinationUrl}
          rel="noopener noreferrer"
          target="_blank"
        >
          Inspect destination
        </a>
      ) : null}
    </>
  );
}
