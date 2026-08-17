import { CheckCircle2, Fingerprint, Send, ShieldAlert } from "lucide-react";

import type { ProductPackage } from "../../lib/api/productTypes";
import { formatDate } from "../../lib/status";
import { usePackageReviewController, type PackageReviewAction } from "./usePackageReviewController";

export function PackageReviewPanel({
  onChanged,
  productPackage,
}: {
  onChanged: (updated: ProductPackage) => void;
  productPackage: ProductPackage;
}) {
  const controller = usePackageReviewController(productPackage, onChanged);
  const authoring = controller.role === "DELIVERY_SPECIALIST" && productPackage.status === "DRAFT";

  return (
    <aside className="product-review-panel" aria-labelledby="review-panel-title">
      <div className="section-heading">
        <span>{authoring ? "Final step" : "Immutable decision"}</span>
        <h2 id="review-panel-title">
          {authoring ? "Submit product" : `Review version ${productPackage.packageVersion}`}
        </h2>
      </div>
      <dl className="product-integrity">
        <div>
          <dt>Record version</dt>
          <dd>{productPackage.version}</dd>
        </div>
        <div>
          <dt>Checksum</dt>
          <dd className="mono-ref">
            {controller.checksum ? `${controller.checksum.slice(0, 16)}…` : "Created on submission"}
          </dd>
        </div>
        <div>
          <dt>Author</dt>
          <dd>{productPackage.authorDisplayName}</dd>
        </div>
      </dl>
      <p className="product-integrity-note">
        <Fingerprint aria-hidden="true" size={17} />
        {authoring
          ? "MIST creates the review checksum when you submit. Any later change creates a new version."
          : "Manager and QC decisions bind to this exact package checksum. Any change creates another version."}
      </p>
      <CoveringNote controller={controller} productPackage={productPackage} />
      <ValidationWarning clean={controller.clean} status={productPackage.status} />
      <ReviewActions controller={controller} productPackage={productPackage} />
      <DecisionEvidence productPackage={productPackage} />
      {controller.action.isError ? (
        <p className="form-banner form-banner--error" role="alert">
          {controller.action.error.message}
        </p>
      ) : null}
    </aside>
  );
}

type Controller = ReturnType<typeof usePackageReviewController>;

function CoveringNote({
  controller,
  productPackage,
}: {
  controller: Controller;
  productPackage: ProductPackage;
}) {
  if (controller.role === "DELIVERY_SPECIALIST" && productPackage.status === "DRAFT") {
    return (
      <label className="form-field">
        <span>Covering note to Customer</span>
        <textarea
          maxLength={2000}
          minLength={3}
          onChange={(event) => controller.setCoveringNote(event.target.value)}
          rows={5}
          value={controller.coveringNote}
        />
        <small>
          This note is released with the product and included in the immutable review checksum.
        </small>
      </label>
    );
  }
  if (!productPackage.coveringNote) return null;
  return (
    <div className="product-covering-note">
      <strong>Covering note to Customer</strong>
      <p>{productPackage.coveringNote}</p>
    </div>
  );
}

function ValidationWarning({
  clean,
  status,
}: {
  clean: boolean;
  status: ProductPackage["status"];
}) {
  if (clean || status !== "DRAFT") return null;
  return (
    <p className="form-banner form-banner--warning" role="status">
      <ShieldAlert aria-hidden="true" size={16} />
      Every artefact must pass validation before review.
    </p>
  );
}

function ReviewActions({
  controller,
  productPackage,
}: {
  controller: Controller;
  productPackage: ProductPackage;
}) {
  if (controller.role === "DELIVERY_SPECIALIST" && productPackage.status === "DRAFT") {
    return <SpecialistSubmit controller={controller} />;
  }
  if (controller.role === "DELIVERY_TEAM_LEAD" && productPackage.status === "REVIEW_READY") {
    return <ManagerApproval controller={controller} />;
  }
  if (controller.role !== "QUALITY_RELEASE") return null;
  return <QualityReleaseActions controller={controller} productPackage={productPackage} />;
}

function SpecialistSubmit({ controller }: { controller: Controller }) {
  const disabled =
    !controller.clean || controller.coveringNote.trim().length < 3 || controller.action.isPending;
  return (
    <ActionButton action="submit" controller={controller} disabled={disabled}>
      Submit product
    </ActionButton>
  );
}

function ManagerApproval({ controller }: { controller: Controller }) {
  return (
    <ActionButton
      action="approve"
      controller={controller}
      disabled={!controller.checksum || controller.action.isPending}
    >
      <CheckCircle2 aria-hidden="true" size={16} />
      Approve exact package
    </ActionButton>
  );
}

function QualityReleaseActions({
  controller,
  productPackage,
}: {
  controller: Controller;
  productPackage: ProductPackage;
}) {
  if (productPackage.status === "DISSEMINATED") return <Withdrawal controller={controller} />;
  if (productPackage.status !== "MANAGER_APPROVED") return null;
  if (productPackage.requestStatus === "QUALITY_REVIEW") {
    return (
      <p className="product-integrity-note">
        Complete the workflow review before dissemination becomes available.
      </p>
    );
  }
  if (productPackage.requestStatus !== "READY_FOR_RELEASE") return null;
  const disabled =
    !controller.checksum ||
    (controller.hasExternalLink && !controller.attested) ||
    controller.action.isPending;
  return (
    <>
      {controller.hasExternalLink ? (
        <label className="product-attestation">
          <input
            checked={controller.attested}
            onChange={(event) => controller.setAttested(event.target.checked)}
            type="checkbox"
          />
          <span>
            <strong>External access attested</strong>
            <small>
              I have confirmed the Customer can access each destination and its handling is
              appropriate.
            </small>
          </span>
        </label>
      ) : null}
      <ActionButton action="disseminate" controller={controller} disabled={disabled}>
        <Send aria-hidden="true" size={16} />
        Disseminate to Customer
      </ActionButton>
    </>
  );
}

function Withdrawal({ controller }: { controller: Controller }) {
  return (
    <div className="product-withdraw">
      <label className="form-field">
        <span>Withdrawal reason</span>
        <textarea
          minLength={8}
          onChange={(event) => controller.setReason(event.target.value)}
          rows={3}
          value={controller.reason}
        />
      </label>
      <ActionButton
        action="withdraw"
        controller={controller}
        disabled={controller.reason.trim().length < 8 || controller.action.isPending}
      >
        Withdraw access
      </ActionButton>
    </div>
  );
}

function ActionButton({
  action,
  children,
  controller,
  disabled,
}: {
  action: PackageReviewAction;
  children: React.ReactNode;
  controller: Controller;
  disabled: boolean;
}) {
  return (
    <button
      className={action === "withdraw" ? "button" : "button button--primary"}
      disabled={disabled}
      onClick={() => controller.action.mutate(action)}
      type="button"
    >
      {children}
    </button>
  );
}

function DecisionEvidence({ productPackage }: { productPackage: ProductPackage }) {
  return (
    <>
      {productPackage.managerApprovedAt ? (
        <p className="product-evidence">
          Manager approval: {productPackage.managerApprovedBy} ·{" "}
          {formatDate(productPackage.managerApprovedAt, true)}
        </p>
      ) : null}
      {productPackage.disseminatedAt ? (
        <p className="product-evidence">
          Disseminated: {productPackage.disseminatedBy} ·{" "}
          {formatDate(productPackage.disseminatedAt, true)}
        </p>
      ) : null}
    </>
  );
}
