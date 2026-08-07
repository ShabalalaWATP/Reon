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
  if (!artefacts.length) return <p className="inline-empty">No artefacts have been added to this version.</p>;
  return (
    <ol className="product-artefact-list" aria-label="Package artefacts">
      {artefacts.map((artefact, index) => {
        const available = customerAccess && artefact.lifecycle === "RELEASED";
        return (
          <li key={artefact.id}>
            <span className="product-artefact-index">{String(index + 1).padStart(2, "0")}</span>
            <span className="product-artefact-icon">{artefact.kind === "MANAGED_FILE" ? <FileText aria-hidden="true" size={18} /> : <ExternalLink aria-hidden="true" size={18} />}</span>
            <span className="product-artefact-copy"><strong>{artefact.label}</strong><small>{artefact.filename ?? artefact.destinationDomain ?? "Approved external destination"} · {formatBytes(artefact.sizeBytes)}</small>{artefact.expiresAt ? <small>Expires {formatDate(artefact.expiresAt, true)}</small> : null}</span>
            <span className={`product-state product-state--${artefact.lifecycle.toLowerCase()}`}>{artefactStatusLabels[artefact.lifecycle]}</span>
            {available ? <a className="button button--quiet" href={productArtefactUrl(artefact.id, artefact.kind)} rel={artefact.kind === "EXTERNAL_LINK" ? "noopener noreferrer" : undefined} target={artefact.kind === "EXTERNAL_LINK" ? "_blank" : undefined}>{artefact.kind === "MANAGED_FILE" ? "Download" : "Open product"}</a> : customerAccess ? <span className="product-unavailable"><LockKeyhole aria-hidden="true" size={14} />Unavailable</span> : null}
          </li>
        );
      })}
    </ol>
  );
}
