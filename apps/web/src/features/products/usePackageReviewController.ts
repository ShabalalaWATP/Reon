import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { productApi } from "../../lib/api/productClient";
import type { ProductPackage } from "../../lib/api/productTypes";
import { useAuth } from "../../lib/auth/AuthProvider";
import { newProductKey } from "./productPresentation";

export type PackageReviewAction = "submit" | "approve" | "disseminate" | "withdraw";

export function usePackageReviewController(
  productPackage: ProductPackage,
  onChanged: (updated: ProductPackage) => void,
) {
  const { session } = useAuth();
  const [attested, setAttested] = useState(false);
  const [coveringNote, setCoveringNote] = useState(productPackage.coveringNote ?? "");
  const [reason, setReason] = useState("");
  const checksum = productPackage.packageChecksum;
  const action = useMutation({
    mutationFn: (name: PackageReviewAction) =>
      runPackageAction(name, productPackage, session!.csrfToken, {
        attested,
        coveringNote,
        reason,
      }),
    onSuccess: (updated) => onChanged(updated),
  });

  return {
    action,
    attested,
    checksum,
    clean: hasValidatedArtefacts(productPackage),
    coveringNote,
    hasExternalLink: productPackage.artefacts.some((item) => item.kind === "EXTERNAL_LINK"),
    reason,
    role: session!.user.role,
    setAttested,
    setCoveringNote,
    setReason,
  };
}

function hasValidatedArtefacts(productPackage: ProductPackage) {
  return (
    productPackage.artefacts.length > 0 &&
    productPackage.artefacts.every(
      (item) => item.lifecycle === "CLEAN" || item.lifecycle === "RELEASED",
    )
  );
}

function runPackageAction(
  name: PackageReviewAction,
  productPackage: ProductPackage,
  csrfToken: string,
  input: { attested: boolean; coveringNote: string; reason: string },
) {
  const base = {
    expectedVersion: productPackage.version,
    idempotencyKey: newProductKey(),
  };
  if (name === "submit") {
    return productApi.submit(
      productPackage.id,
      { ...base, coveringNote: input.coveringNote.trim() },
      csrfToken,
    );
  }
  if (name === "withdraw") {
    return productApi.withdraw(
      productPackage.id,
      { ...base, reason: input.reason.trim() },
      csrfToken,
    );
  }
  const packageChecksum = requireChecksum(productPackage.packageChecksum);
  if (name === "approve") {
    return productApi.managerApprove(productPackage.id, { ...base, packageChecksum }, csrfToken);
  }
  return productApi.disseminate(
    productPackage.id,
    { ...base, externalLinkAttested: input.attested, packageChecksum },
    csrfToken,
  );
}

function requireChecksum(checksum: string | null) {
  if (!checksum) throw new Error("This package does not have a review checksum.");
  return checksum;
}
