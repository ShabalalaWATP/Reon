import { ArrowLeft } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

import { PageState } from "../../components/PageState";
import { ApiError } from "../../lib/api/client";
import type { AdminUser } from "../../lib/api/types";
import { AdminUserForm } from "./AdminUserForm";
import { StepUpPanel } from "./StepUpPanel";
import { useAdminUserPageController } from "./useAdminUserPageController";

export function AdminUserPage({ create = false }: { create?: boolean }) {
  const controller = useAdminUserPageController(create);
  if (isLoading(controller)) return <PageState kind="loading" title="Loading user profile" />;
  if (hasUserError(controller))
    return <UserLoadError onRetry={() => void controller.user.refetch()} />;
  if (controller.units.isError)
    return <OrganisationLoadError onRetry={() => void controller.units.refetch()} />;
  return <AdminUserContent controller={controller} />;
}

type Controller = ReturnType<typeof useAdminUserPageController>;

function AdminUserContent({ controller }: { controller: Controller }) {
  const managed = controller.create ? undefined : controller.user.data;
  return (
    <main className="page-stack page-stack--narrow admin-user-page">
      <Link className="back-link" to="/admin/users">
        <ArrowLeft aria-hidden="true" size={16} />
        User accounts
      </Link>
      <header className="page-heading">
        <div>
          <span>Platform administration</span>
          <h1>{controller.create ? "Create user" : managed?.displayName}</h1>
          <p>
            {controller.create
              ? "Create a synthetic MVP account. The username is generated automatically."
              : `${managed?.username} · ${managed?.isActive ? "Active" : "Inactive"}`}
          </p>
        </div>
      </header>
      <StepUpPanel />
      <SaveStatus controller={controller} managed={managed} />
      <AdminUserForm
        disabled={controller.save.isPending || !controller.elevated}
        onSubmit={(input) => controller.save.mutate(input)}
        pending={controller.save.isPending}
        units={controller.units.data!.items}
        user={managed}
      />
      {managed ? (
        <AccountStatus
          currentUserId={controller.currentUserId}
          disabled={controller.status.isPending || !controller.elevated}
          error={controller.status.error}
          onChange={(active) => controller.status.mutate(active)}
          user={managed}
        />
      ) : null}
    </main>
  );
}

function SaveStatus({ controller, managed }: { controller: Controller; managed?: AdminUser }) {
  if (controller.justCreated && managed)
    return (
      <p className="form-banner" role="status">
        Account created. Username: <strong>{managed.username}</strong>.
      </p>
    );
  if (controller.save.isSuccess)
    return (
      <p className="form-banner" role="status">
        Account details saved.
      </p>
    );
  if (controller.save.isError)
    return <ErrorBanner error={controller.save.error} fallback="The account could not be saved." />;
  return null;
}

function isLoading(controller: Controller) {
  return (!controller.create && controller.user.isPending) || controller.units.isPending;
}

function hasUserError(controller: Controller) {
  return !controller.create && controller.user.isError;
}

function UserLoadError({ onRetry }: { onRetry: () => void }) {
  return (
    <PageState
      action={
        <button className="button" onClick={onRetry}>
          Try again
        </button>
      }
      kind="error"
      title="User profile could not be loaded"
    >
      The account may no longer be available.
    </PageState>
  );
}

function OrganisationLoadError({ onRetry }: { onRetry: () => void }) {
  return (
    <PageState
      action={
        <button className="button" onClick={onRetry}>
          Try again
        </button>
      }
      kind="error"
      title="Organisation could not be loaded"
    >
      Membership options are required before this profile can be changed.
    </PageState>
  );
}

function AccountStatus({
  currentUserId,
  disabled,
  error,
  onChange,
  user,
}: {
  currentUserId: string;
  disabled: boolean;
  error: Error | null;
  onChange: (active: boolean) => void;
  user: AdminUser;
}) {
  const [confirming, setConfirming] = useState(false);
  const self = currentUserId === user.id;
  return (
    <section className="admin-status" aria-labelledby="account-status-title">
      <div>
        <span className="mono-ref">Account state</span>
        <h2 id="account-status-title">{user.isActive ? "Active" : "Inactive"}</h2>
        <p>
          {user.isActive
            ? "This user can sign in and receive work allowed by their role."
            : "This user cannot sign in or receive new work."}
        </p>
      </div>
      {error ? <ErrorBanner error={error} fallback="Account status could not be changed." /> : null}
      {user.isActive ? (
        confirming ? (
          <div className="admin-confirm" role="group" aria-label="Confirm deactivation">
            <strong>Deactivate {user.displayName}?</strong>
            <button
              className="button"
              disabled={disabled}
              onClick={() => {
                setConfirming(false);
                onChange(false);
              }}
              type="button"
            >
              Confirm deactivation
            </button>
            <button
              className="button button--quiet"
              onClick={() => setConfirming(false)}
              type="button"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            className="button"
            disabled={self || disabled}
            onClick={() => setConfirming(true)}
            title={self ? "You cannot deactivate your own account." : undefined}
            type="button"
          >
            Deactivate account
          </button>
        )
      ) : (
        <button
          className="button button--primary"
          disabled={disabled}
          onClick={() => onChange(true)}
          type="button"
        >
          Reactivate account
        </button>
      )}
    </section>
  );
}

function ErrorBanner({ error, fallback }: { error: Error; fallback: string }) {
  return (
    <p className="form-banner form-banner--error" role="alert">
      {error instanceof ApiError ? error.message : fallback}
    </p>
  );
}
