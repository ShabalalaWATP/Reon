import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, LockKeyhole } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";

import { PageState } from "../../components/PageState";
import { productApi } from "../../lib/api/productClient";
import { useAuth } from "../../lib/auth/AuthProvider";
import { PackageArtefactList } from "./PackageArtefactList";
import { PackageBuilder } from "./PackageBuilder";
import { PackageReviewPanel } from "./PackageReviewPanel";
import { newProductKey, packageStatusLabels } from "./productPresentation";

export function ProductPackagePage() {
  const { packageId } = useParams();
  const { session } = useAuth();
  const query = useQuery({
    enabled: Boolean(packageId && packageId !== "new"),
    queryFn: () => productApi.package(packageId!),
    queryKey: ["protected", session!.user.id, "product-package", packageId],
  });
  if (!packageId || packageId === "new") return <CreatePackage />;
  if (query.isPending) return <PageState kind="loading" title="Loading product package" />;
  if (query.isError) return <PageState action={<button className="button" onClick={() => void query.refetch()}>Try again</button>} kind="error" title="Product package could not be loaded">It may have changed or you may no longer have access.</PageState>;
  const productPackage = query.data;
  const editable = session!.user.role === "DELIVERY_SPECIALIST" && productPackage.status === "DRAFT";
  return (
    <main className="page-stack product-package-page">
      <Link className="back-link" to={session!.user.role === "DELIVERY_SPECIALIST" ? "/delivery/my-work" : session!.user.role === "DELIVERY_TEAM_LEAD" ? "/delivery/team" : "/quality-release"}><ArrowLeft aria-hidden="true" size={16} />Return to work queue</Link>
      <header className="detail-heading product-package-heading"><div><span className="mono-ref">{productPackage.requestReference} · package v{productPackage.packageVersion}</span><h1>{productPackage.requestTitle}</h1><p>Assemble, review and disseminate one immutable release version.</p></div><span className={`product-state product-state--${productPackage.status.toLowerCase()}`}>{packageStatusLabels[productPackage.status]}</span></header>
      <div className="product-workspace">
        <div>{editable ? <PackageBuilder onChanged={() => query.refetch()} productPackage={productPackage} /> : <section className="product-builder" aria-labelledby="package-contents-title"><header className="product-section-heading"><div><span>Read-only version</span><h2 id="package-contents-title">Package contents</h2></div><p><LockKeyhole aria-hidden="true" size={15} />Changes create a new version</p></header><PackageArtefactList artefacts={productPackage.artefacts} /></section>}</div>
        <PackageReviewPanel onChanged={() => query.refetch()} productPackage={productPackage} />
      </div>
    </main>
  );
}

function CreatePackage() {
  const { session } = useAuth();
  const navigate = useNavigate();
  const [search] = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const create = useMutation({
    mutationFn: (input: { requestId: string; expectedVersion: number }) => productApi.createPackage({ ...input, idempotencyKey: newProductKey() }, session!.csrfToken),
    onSuccess: (created) => void navigate(`/product-packages/${created.id}`, { replace: true }),
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const requestId = String(data.get("requestId") ?? "").trim();
    const expectedVersion = Number(data.get("expectedVersion"));
    if (!requestId || !Number.isInteger(expectedVersion) || expectedVersion < 1) {
      setError("Enter the request identifier and current version from your assigned work.");
      return;
    }
    setError(null);
    create.mutate({ expectedVersion, requestId });
  }
  return <main className="page-stack page-stack--narrow"><header className="page-heading"><div><span>Product development</span><h1>Start release package</h1><p>Create a version against the exact assigned request record.</p></div></header><form className="product-create-form" onSubmit={submit} noValidate><label className="form-field"><span>Request identifier</span><input defaultValue={search.get("requestId") ?? ""} name="requestId" /></label><label className="form-field"><span>Request version</span><input defaultValue={search.get("version") ?? ""} min={1} name="expectedVersion" type="number" /></label>{error || create.isError ? <p className="form-banner form-banner--error" role="alert">{error ?? create.error?.message}</p> : null}<button className="button button--primary" disabled={create.isPending} type="submit">{create.isPending ? "Creating package…" : "Create release package"}</button></form></main>;
}
