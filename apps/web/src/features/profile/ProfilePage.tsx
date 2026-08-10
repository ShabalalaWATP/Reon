import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, CheckCircle2, FilePenLine, ShieldCheck, UserRound } from "lucide-react";

import { PageState } from "../../components/PageState";
import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import { useAuth } from "../../lib/auth/AuthProvider";
import { roleLabels } from "../../lib/routes";
import { formatDate } from "../../lib/status";
import {
  profileAccessLabel,
  profileInitials,
  profileMembershipText,
  profileRoleDescription,
  profileScopeLabel,
} from "./profileModel";
import { PersonalProfileForm } from "./PersonalProfileForm";

export function ProfilePage() {
  const { session } = useAuth();
  const user = session!.user;
  const queryClient = useQueryClient();
  const profile = useQuery({
    queryKey: protectedQueryKeys.profile(user.id),
    queryFn: api.profile,
  });
  const organisation = useQuery({
    queryKey: protectedQueryKeys.organisationUnits(user.id),
    queryFn: api.organisationUnits,
    enabled: user.organisationUnitIds.length > 0,
    staleTime: 60_000,
  });
  const memberships = (organisation.data?.items ?? []).filter((unit) =>
    user.organisationUnitIds.includes(unit.id));
  const update = useMutation({
    mutationFn: (input: Parameters<typeof api.updateProfile>[0]) => api.updateProfile(input, session!.csrfToken),
    onSuccess: (saved) => queryClient.setQueryData(protectedQueryKeys.profile(user.id), saved),
  });

  if (profile.isPending) return <PageState kind="loading" title="Loading your profile" />;
  if (profile.isError) return <PageState action={<button className="button" onClick={() => void profile.refetch()}>Try again</button>} kind="error" title="Profile could not be loaded" />;

  return (
    <main className="page-stack profile-page">
      <header className="profile-identity">
        <span aria-hidden="true" className="profile-avatar">{profileInitials(user.displayName)}</span>
        <div>
          <span>Personal profile</span>
          <h1>{user.displayName}</h1>
          <p>{profileRoleDescription(user)}</p>
        </div>
        <strong className="profile-status"><CheckCircle2 aria-hidden="true" size={16} />Active account</strong>
      </header>

      <div className="profile-sections">
        <section aria-labelledby="profile-account-title">
          <header><UserRound aria-hidden="true" size={19} /><div><span>Identity</span><h2 id="profile-account-title">Account details</h2></div></header>
          <dl className="profile-definition-list">
            <div><dt>Name</dt><dd>{user.displayName}</dd></div>
            <div><dt>Account ID</dt><dd className="mono-ref">{user.username}</dd></div>
            <div><dt>Work email</dt><dd>{profile.data.email}</dd></div>
            <div><dt>Representative role</dt><dd>{roleLabels[user.role]}</dd></div>
            <div><dt>Workspace access</dt><dd>{profileAccessLabel(user)}</dd></div>
          </dl>
        </section>

        <section aria-labelledby="profile-personal-title" className="profile-personal-section">
          <header><FilePenLine aria-hidden="true" size={19} /><div><span>About you</span><h2 id="profile-personal-title">Personal details</h2></div></header>
          <p className="profile-note">Add optional information about yourself. These details do not change your ISTARI access or where requests are routed.</p>
          <PersonalProfileForm disabled={update.isPending} key={profile.data.version} onSubmit={update.mutate} profile={profile.data} />
          {update.isSuccess ? <p className="form-banner form-banner--success" role="status">Personal details saved.</p> : null}
          {update.isError ? <p className="form-banner form-banner--error" role="alert">Your personal details could not be saved. Refresh and try again.</p> : null}
        </section>

        <section aria-labelledby="profile-organisation-title">
          <header><Building2 aria-hidden="true" size={19} /><div><span>Access boundary</span><h2 id="profile-organisation-title">Organisation and scope</h2></div></header>
          <dl className="profile-definition-list">
            <div><dt>Operational scope</dt><dd>{profileScopeLabel(user)}</dd></div>
            <div><dt>Organisation assignments</dt><dd>{profileMembershipText(user.organisationUnitIds.length, memberships.map((unit) => unit.name), organisation.isError)}</dd></div>
          </dl>
          {user.role === "REQUESTER" ? <p className="profile-note">Customers do not choose or see an internal routing destination. Each request is visible only to its Customer and authorised staff.</p> : null}
        </section>

        <section aria-labelledby="profile-session-title">
          <header><ShieldCheck aria-hidden="true" size={19} /><div><span>Security</span><h2 id="profile-session-title">Current session</h2></div></header>
          <dl className="profile-definition-list">
            <div><dt>Session state</dt><dd>Authenticated</dd></div>
            <div><dt>Signed in until</dt><dd>{formatDate(session!.expiresAt, true)}</dd></div>
          </dl>
          <p className="profile-note">Your role, name and organisational access are managed by an authorised Administrator. Your personal details remain yours to maintain.</p>
        </section>
      </div>
    </main>
  );
}
