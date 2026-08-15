import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, CheckCircle2, FilePenLine, ShieldCheck, UserRound } from "lucide-react";
import { useState } from "react";

import { PageState } from "../../components/PageState";
import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { PersonalProfile, PersonalProfileUpdate } from "../../lib/api/types";
import { useAuth } from "../../lib/auth/AuthProvider";
import { roleLabels } from "../../lib/routes";
import { formatDate } from "../../lib/status";
import {
  profileAccessLabel,
  profileInitials,
  profileMembershipText,
  profileRoleDescription,
  profileScopeLabel,
  profileWorkspacePositionText,
} from "./profileModel";
import { PersonalProfileDetails } from "./PersonalProfileDetails";
import { PersonalProfileForm } from "./PersonalProfileForm";

export function ProfilePage() {
  const { session } = useAuth();
  const queryKeys = protectedQueryKeys(session);
  const user = session!.user;
  const queryClient = useQueryClient();
  const [editingPersonal, setEditingPersonal] = useState(false);
  const profile = useQuery({
    queryKey: queryKeys.profile(),
    queryFn: api.profile,
  });
  const organisation = useQuery({
    queryKey: queryKeys.organisationUnits(),
    queryFn: api.organisationUnits,
    enabled: user.organisationUnitIds.length > 0,
    staleTime: 60_000,
  });
  const workspaceAccess = useQuery({
    queryKey: queryKeys.teamWorkspaces(),
    queryFn: api.teamWorkspaces,
    enabled: user.organisationUnitIds.length > 0,
    staleTime: 60_000,
  });
  const memberships = (organisation.data?.items ?? []).filter((unit) =>
    user.organisationUnitIds.includes(unit.id),
  );
  const update = useMutation({
    mutationFn: (input: Parameters<typeof api.updateProfile>[0]) =>
      api.updateProfile(input, session!.csrfToken),
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKeys.profile(), saved);
      setEditingPersonal(false);
    },
  });

  if (profile.isPending) return <PageState kind="loading" title="Loading your profile" />;
  if (profile.isError)
    return (
      <PageState
        action={
          <button className="button" onClick={() => void profile.refetch()}>
            Try again
          </button>
        }
        kind="error"
        title="Profile could not be loaded"
      />
    );

  return (
    <main className="page-stack profile-page">
      <header className="profile-identity">
        <span aria-hidden="true" className="profile-avatar">
          {profileInitials(user.displayName)}
        </span>
        <div>
          <span>Personal profile</span>
          <h1>{user.displayName}</h1>
          <p>{profileRoleDescription(user)}</p>
        </div>
        <strong className="profile-status">
          <CheckCircle2 aria-hidden="true" size={16} />
          Active account
        </strong>
      </header>

      <div className="profile-sections">
        <section aria-labelledby="profile-account-title">
          <header>
            <UserRound aria-hidden="true" size={19} />
            <div>
              <span>Identity</span>
              <h2 id="profile-account-title">Account details</h2>
            </div>
          </header>
          <dl className="profile-definition-list">
            <div>
              <dt>Name</dt>
              <dd>{user.displayName}</dd>
            </div>
            <div>
              <dt>Account ID</dt>
              <dd className="mono-ref">{user.username}</dd>
            </div>
            <div>
              <dt>Work email</dt>
              <dd>{profile.data.email}</dd>
            </div>
            <div>
              <dt>Representative role</dt>
              <dd>{roleLabels[user.role]}</dd>
            </div>
            <div>
              <dt>Workspace access</dt>
              <dd>{profileAccessLabel(user, workspaceAccess.data?.items ?? [])}</dd>
            </div>
          </dl>
        </section>

        <PersonalDetailsSection
          editing={editingPersonal}
          failed={update.isError}
          onCancel={() => setEditingPersonal(false)}
          onEdit={() => setEditingPersonal(true)}
          onSubmit={update.mutate}
          profile={profile.data}
          saved={update.isSuccess}
          saving={update.isPending}
        />

        <section aria-labelledby="profile-organisation-title">
          <header>
            <Building2 aria-hidden="true" size={19} />
            <div>
              <span>Access boundary</span>
              <h2 id="profile-organisation-title">Organisation and scope</h2>
            </div>
          </header>
          <dl className="profile-definition-list">
            <div>
              <dt>Operational scope</dt>
              <dd>{profileScopeLabel(user)}</dd>
            </div>
            <div>
              <dt>Organisation assignments</dt>
              <dd>
                {profileMembershipText(
                  user.organisationUnitIds.length,
                  memberships.map((unit) => unit.name),
                  organisation.isError,
                )}
              </dd>
            </div>
            {user.organisationUnitIds.length > 0 ? (
              <div>
                <dt>Workspace position</dt>
                <dd>
                  {profileWorkspacePositionText(
                    user.organisationUnitIds.length,
                    workspaceAccess.data?.items ?? [],
                    workspaceAccess.isError,
                  )}
                </dd>
              </div>
            ) : null}
          </dl>
          {user.role === "REQUESTER" ? (
            <p className="profile-note">
              Customers do not choose or see an internal routing destination. Each request is
              visible only to its Customer and authorised staff.
            </p>
          ) : null}
        </section>

        <section aria-labelledby="profile-session-title">
          <header>
            <ShieldCheck aria-hidden="true" size={19} />
            <div>
              <span>Security</span>
              <h2 id="profile-session-title">Current session</h2>
            </div>
          </header>
          <dl className="profile-definition-list">
            <div>
              <dt>Session state</dt>
              <dd>Authenticated</dd>
            </div>
            <div>
              <dt>Signed in until</dt>
              <dd>{formatDate(session!.expiresAt, true)}</dd>
            </div>
          </dl>
          <p className="profile-note">
            Your role, name and organisational access are managed by an authorised Administrator.
            Your personal details remain yours to maintain.
          </p>
        </section>
      </div>
    </main>
  );
}

function PersonalDetailsSection({
  editing,
  failed,
  onCancel,
  onEdit,
  onSubmit,
  profile,
  saved,
  saving,
}: {
  editing: boolean;
  failed: boolean;
  onCancel: () => void;
  onEdit: () => void;
  onSubmit: (value: PersonalProfileUpdate) => void;
  profile: PersonalProfile;
  saved: boolean;
  saving: boolean;
}) {
  const hasDetails = Boolean(
    profile.profileTeam ||
    profile.rankOrGrade ||
    profile.serviceNumber ||
    profile.skills.length > 0 ||
    profile.additionalInformation,
  );
  const showForm = editing || !hasDetails;
  return (
    <section aria-labelledby="profile-personal-title" className="profile-personal-section">
      <header>
        <FilePenLine aria-hidden="true" size={19} />
        <div>
          <span>About you</span>
          <h2 id="profile-personal-title">Personal details</h2>
        </div>
        {!showForm ? (
          <button
            aria-label="Edit personal details"
            className="button button--quiet profile-personal-edit"
            onClick={onEdit}
            type="button"
          >
            Edit
          </button>
        ) : null}
      </header>
      {showForm ? (
        <>
          <p className="profile-note">
            Add optional information about yourself. These details do not change your Mist access or
            where requests are routed.
          </p>
          <PersonalProfileForm
            disabled={saving}
            key={profile.version}
            onCancel={hasDetails ? onCancel : undefined}
            onSubmit={onSubmit}
            profile={profile}
          />
        </>
      ) : (
        <PersonalProfileDetails profile={profile} />
      )}
      {saved ? (
        <p className="form-banner form-banner--success" role="status">
          Personal details saved.
        </p>
      ) : null}
      {failed ? (
        <p className="form-banner form-banner--error" role="alert">
          Your personal details could not be saved. Refresh and try again.
        </p>
      ) : null}
    </section>
  );
}
