import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, Fingerprint, Send, ShieldAlert } from "lucide-react";
import { useState } from "react";

import { productApi } from "../../lib/api/productClient";
import type { ProductPackage } from "../../lib/api/productTypes";
import { useAuth } from "../../lib/auth/AuthProvider";
import { formatDate } from "../../lib/status";
import { newProductKey } from "./productPresentation";

export function PackageReviewPanel({
  onChanged,
  productPackage,
}: {
  onChanged: () => Promise<unknown>;
  productPackage: ProductPackage;
}) {
  const { session } = useAuth();
  const [attested, setAttested] = useState(false);
  const [reason, setReason] = useState("");
  const csrfToken = session!.csrfToken;
  const hasExternalLink = productPackage.artefacts.some((item) => item.kind === "EXTERNAL_LINK");
  const clean = productPackage.artefacts.length > 0 && productPackage.artefacts.every((item) => item.lifecycle === "CLEAN" || item.lifecycle === "RELEASED");
  const checksum = productPackage.packageChecksum;
  const action = useMutation({
    mutationFn: async (name: "submit" | "approve" | "disseminate" | "withdraw") => {
      if (name === "submit") return productApi.submit(productPackage.id, { expectedVersion: productPackage.version, idempotencyKey: newProductKey() }, csrfToken);
      if (name === "approve") return productApi.managerApprove(productPackage.id, { expectedVersion: productPackage.version, idempotencyKey: newProductKey(), packageChecksum: checksum! }, csrfToken);
      if (name === "disseminate") return productApi.disseminate(productPackage.id, { expectedVersion: productPackage.version, externalLinkAttested: attested, idempotencyKey: newProductKey(), packageChecksum: checksum! }, csrfToken);
      return productApi.withdraw(productPackage.id, { expectedVersion: productPackage.version, idempotencyKey: newProductKey(), reason: reason.trim() }, csrfToken);
    },
    onSuccess: onChanged,
  });
  const role = session!.user.role;

  return (
    <aside className="product-review-panel" aria-labelledby="review-panel-title">
      <div className="section-heading"><span>Immutable decision</span><h2 id="review-panel-title">Review version {productPackage.packageVersion}</h2></div>
      <dl className="product-integrity">
        <div><dt>Record version</dt><dd>{productPackage.version}</dd></div>
        <div><dt>Checksum</dt><dd className="mono-ref">{checksum ? `${checksum.slice(0, 16)}…` : "Created on submission"}</dd></div>
        <div><dt>Author</dt><dd>{productPackage.authorDisplayName}</dd></div>
      </dl>
      <p className="product-integrity-note"><Fingerprint aria-hidden="true" size={17} />Manager and QC decisions bind to this exact package checksum. Any change creates another version.</p>
      {!clean && productPackage.status === "DRAFT" ? <p className="form-banner form-banner--warning" role="status"><ShieldAlert aria-hidden="true" size={16} />Every artefact must pass validation before review.</p> : null}
      {role === "DELIVERY_SPECIALIST" && productPackage.status === "DRAFT" ? <button className="button button--primary" disabled={!clean || action.isPending} onClick={() => action.mutate("submit")} type="button">Submit exact version for review</button> : null}
      {role === "DELIVERY_TEAM_LEAD" && productPackage.status === "REVIEW_READY" ? <button className="button button--primary" disabled={!checksum || action.isPending} onClick={() => action.mutate("approve")} type="button"><CheckCircle2 aria-hidden="true" size={16} />Approve exact package</button> : null}
      {role === "QUALITY_RELEASE" && productPackage.status === "MANAGER_APPROVED" && productPackage.requestStatus === "READY_FOR_RELEASE" ? <>
        {hasExternalLink ? <label className="product-attestation"><input checked={attested} onChange={(event) => setAttested(event.target.checked)} type="checkbox" /><span><strong>External access attested</strong><small>I have confirmed the Customer can access each destination and its handling is appropriate.</small></span></label> : null}
        <button className="button button--primary" disabled={!checksum || (hasExternalLink && !attested) || action.isPending} onClick={() => action.mutate("disseminate")} type="button"><Send aria-hidden="true" size={16} />Disseminate to Customer</button>
      </> : null}
      {role === "QUALITY_RELEASE" && productPackage.status === "MANAGER_APPROVED" && productPackage.requestStatus === "QUALITY_REVIEW" ? <p className="product-integrity-note">Complete the workflow review before dissemination becomes available.</p> : null}
      {role === "QUALITY_RELEASE" && productPackage.status === "DISSEMINATED" ? <div className="product-withdraw"><label className="form-field"><span>Withdrawal reason</span><textarea minLength={8} onChange={(event) => setReason(event.target.value)} rows={3} value={reason} /></label><button className="button" disabled={reason.trim().length < 8 || action.isPending} onClick={() => action.mutate("withdraw")} type="button">Withdraw access</button></div> : null}
      {productPackage.managerApprovedAt ? <p className="product-evidence">Manager approval: {productPackage.managerApprovedBy} · {formatDate(productPackage.managerApprovedAt, true)}</p> : null}
      {productPackage.disseminatedAt ? <p className="product-evidence">Disseminated: {productPackage.disseminatedBy} · {formatDate(productPackage.disseminatedAt, true)}</p> : null}
      {action.isError ? <p className="form-banner form-banner--error" role="alert">{action.error.message}</p> : null}
    </aside>
  );
}
