import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router";

import { PageState } from "../../components/PageState";
import { api, ApiError } from "../../lib/api/client";
import type { AdminUser, AdminUserWriteInput } from "../../lib/api/types";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import { isSessionElevated, useAuth } from "../../lib/auth/AuthProvider";
import { AdminUserForm } from "./AdminUserForm";
import { StepUpPanel } from "./StepUpPanel";

export function AdminUserPage({ create = false }: { create?: boolean }) {
  const { session } = useAuth();
  const { userId: managedUserId } = useParams();
  const userId = session!.user.id;
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const elevated = isSessionElevated(session);
  const user = useQuery({ queryKey: protectedQueryKeys.adminUser(userId, managedUserId), queryFn: () => api.adminUser(managedUserId!), enabled: !create });
  const units = useQuery({ queryKey: protectedQueryKeys.organisationUnits(userId), queryFn: api.organisationUnits });
  const save = useMutation({
    mutationFn: (input: AdminUserWriteInput) => create ? api.createAdminUser(input, session!.csrfToken) : api.updateAdminUser(managedUserId!, { ...input, expectedVersion: user.data!.version }, session!.csrfToken),
    onSuccess: (saved) => {
      void queryClient.invalidateQueries({ queryKey: ["protected", userId, "admin-users"] });
      queryClient.setQueryData(protectedQueryKeys.adminUser(userId, saved.id), saved);
      if (create) void navigate(`/admin/users/${saved.id}`, { replace: true, state: { created: true } });
    },
  });
  const status = useMutation({
    mutationFn: (isActive: boolean) => api.updateAdminUserStatus(managedUserId!, { isActive, expectedVersion: user.data!.version }, session!.csrfToken),
    onSuccess: (saved) => {
      queryClient.setQueryData(protectedQueryKeys.adminUser(userId, saved.id), saved);
      void queryClient.invalidateQueries({ queryKey: ["protected", userId, "admin-users"] });
    },
  });
  if (!create && user.isPending || units.isPending) return <PageState kind="loading" title="Loading user profile" />;
  if (!create && user.isError) return <PageState action={<button className="button" onClick={() => void user.refetch()}>Try again</button>} kind="error" title="User profile could not be loaded">The account may no longer be available.</PageState>;
  if (units.isError) return <PageState action={<button className="button" onClick={() => void units.refetch()}>Try again</button>} kind="error" title="Organisation could not be loaded">Membership options are required before this profile can be changed.</PageState>;
  const managed = create ? undefined : user.data;
  const justCreated = Boolean((location.state as { created?: boolean } | null)?.created);
  return (
    <main className="page-stack page-stack--narrow admin-user-page">
      <Link className="back-link" to="/admin/users"><ArrowLeft aria-hidden="true" size={16} />User accounts</Link>
      <header className="page-heading"><div><span>Platform administration</span><h1>{create ? "Create user" : managed?.displayName}</h1><p>{create ? "Create a synthetic MVP account. The username is generated automatically." : `${managed?.username} · ${managed?.isActive ? "Active" : "Inactive"}`}</p></div></header>
      <StepUpPanel />
      {justCreated && managed ? <p className="form-banner" role="status">Account created. Username: <strong>{managed.username}</strong>.</p> : save.isSuccess ? <p className="form-banner" role="status">Account details saved.</p> : null}
      {save.isError ? <ErrorBanner error={save.error} fallback="The account could not be saved." /> : null}
      <AdminUserForm disabled={save.isPending || !elevated} onSubmit={(input) => save.mutate(input)} pending={save.isPending} units={units.data!.items} user={managed} />
      {managed ? <AccountStatus currentUserId={session!.user.id} disabled={status.isPending || !elevated} error={status.error} onChange={(active) => status.mutate(active)} user={managed} /> : null}
    </main>
  );
}

function AccountStatus({ currentUserId, disabled, error, onChange, user }: { currentUserId: string; disabled: boolean; error: Error | null; onChange: (active: boolean) => void; user: AdminUser }) {
  const [confirming, setConfirming] = useState(false);
  const self = currentUserId === user.id;
  return <section className="admin-status" aria-labelledby="account-status-title"><div><span className="mono-ref">Account state</span><h2 id="account-status-title">{user.isActive ? "Active" : "Inactive"}</h2><p>{user.isActive ? "This user can sign in and receive work allowed by their role." : "This user cannot sign in or receive new work."}</p></div>{error ? <ErrorBanner error={error} fallback="Account status could not be changed." /> : null}{user.isActive ? confirming ? <div className="admin-confirm" role="group" aria-label="Confirm deactivation"><strong>Deactivate {user.displayName}?</strong><button className="button" disabled={disabled} onClick={() => { setConfirming(false); onChange(false); }} type="button">Confirm deactivation</button><button className="button button--quiet" onClick={() => setConfirming(false)} type="button">Cancel</button></div> : <button className="button" disabled={self || disabled} onClick={() => setConfirming(true)} title={self ? "You cannot deactivate your own account." : undefined} type="button">Deactivate account</button> : <button className="button button--primary" disabled={disabled} onClick={() => onChange(true)} type="button">Reactivate account</button>}</section>;
}

function ErrorBanner({ error, fallback }: { error: Error; fallback: string }) {
  return <p className="form-banner form-banner--error" role="alert">{error instanceof ApiError ? error.message : fallback}</p>;
}
