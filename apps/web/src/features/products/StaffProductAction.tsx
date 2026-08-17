import { useQuery } from "@tanstack/react-query";
import { PackageOpen } from "lucide-react";
import { Link } from "react-router";

import { productApi } from "../../lib/api/productClient";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { WorkStage } from "../../lib/api/types";
import { useAuth } from "../../lib/auth/AuthProvider";
import { useCapabilities } from "../../lib/capabilities/useCapabilities";

const stagesByRole = {
  DELIVERY_SPECIALIST: ["IN_PROGRESS", "REWORK_REQUIRED"],
  DELIVERY_TEAM_LEAD: ["LEAD_REVIEW"],
  QUALITY_RELEASE: ["QUALITY_REVIEW", "READY_FOR_RELEASE"],
} satisfies Partial<Record<string, WorkStage[]>>;

export function StaffProductAction({
  requestId,
  requestVersion,
  stage,
}: {
  requestId: string;
  requestVersion: number;
  stage: WorkStage;
}) {
  const { capabilities, isPending } = useCapabilities();
  if (isPending || !capabilities.products) return null;
  return (
    <EnabledStaffProductAction
      requestId={requestId}
      requestVersion={requestVersion}
      stage={stage}
    />
  );
}

function EnabledStaffProductAction({
  requestId,
  requestVersion,
  stage,
}: {
  requestId: string;
  requestVersion: number;
  stage: WorkStage;
}) {
  const { session } = useAuth();
  const queryKeys = protectedQueryKeys(session);
  const role = session!.user.role;
  const relevant =
    role in stagesByRole &&
    stagesByRole[role as keyof typeof stagesByRole].includes(stage as never);
  const productPackage = useQuery({
    enabled: relevant,
    queryFn: () => productApi.packageForRequest(requestId),
    queryKey: queryKeys.requestProductPackage(requestId),
  });
  if (!relevant) return null;
  if (productPackage.isPending)
    return <p className="product-inline-state">Checking product package…</p>;
  if (productPackage.isError)
    return (
      <p className="product-inline-state product-inline-state--error">
        Product package is temporarily unavailable.
      </p>
    );
  if (productPackage.data === null)
    return role === "DELIVERY_SPECIALIST" ? (
      <Link
        className="button button--primary button--wide"
        to={`/product-packages/new?requestId=${encodeURIComponent(requestId)}&version=${requestVersion}`}
      >
        <PackageOpen aria-hidden="true" size={16} />
        Start product package
      </Link>
    ) : (
      <p className="product-inline-state">No managed product package has been started.</p>
    );
  if (
    role === "DELIVERY_SPECIALIST" &&
    stage === "REWORK_REQUIRED" &&
    productPackage.data.status !== "DRAFT"
  ) {
    return (
      <Link
        className="button button--primary button--wide"
        to={`/product-packages/new?requestId=${encodeURIComponent(requestId)}&version=${requestVersion}`}
      >
        <PackageOpen aria-hidden="true" size={16} />
        Start revised package
      </Link>
    );
  }
  const labels = {
    DELIVERY_SPECIALIST: "Open product package",
    DELIVERY_TEAM_LEAD: "Review product package",
  } as const;
  const label =
    role === "QUALITY_RELEASE"
      ? stage === "QUALITY_REVIEW"
        ? "Review product package"
        : "Disseminate product package"
      : labels[role as keyof typeof labels];
  return (
    <Link
      className="button button--primary button--wide"
      to={`/product-packages/${productPackage.data.id}`}
    >
      <PackageOpen aria-hidden="true" size={16} />
      {label}
    </Link>
  );
}
