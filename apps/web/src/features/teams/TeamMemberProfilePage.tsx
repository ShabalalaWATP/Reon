import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, BadgeCheck, Building2, Mail, UserRound } from "lucide-react";
import { Link, useParams } from "react-router";

import { PageState } from "../../components/PageState";
import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import { useAuth } from "../../lib/auth/AuthProvider";
import { roleLabels } from "../../lib/routes";
import { profileInitials } from "../profile/profileModel";

export function TeamMemberProfilePage() {
  const { session } = useAuth();
  const { memberId, teamId } = useParams();
  const userId = session?.user.id ?? "anonymous";
  const profile = useQuery({
    queryKey: protectedQueryKeys.teamMemberProfile(userId, teamId, memberId),
    queryFn: () => api.teamMemberProfile(teamId!, memberId!),
    enabled: Boolean(session && teamId && memberId),
  });

  if (profile.isPending) return <PageState kind="loading" title="Loading team member profile" />;
  if (profile.isError) {
    return <PageState action={<button className="button" onClick={() => void profile.refetch()}>Try again</button>} kind="error" title="Team member profile could not be loaded">The person may no longer be visible in this workspace.</PageState>;
  }

  const member = profile.data;
  return (
    <main className="page-stack profile-page team-member-profile">
      <Link className="team-profile-back" to={`/teams/${member.teamId}/people`}><ArrowLeft aria-hidden="true" size={16} />Back to {member.teamName} people</Link>
      <header className="profile-identity">
        <span aria-hidden="true" className="profile-avatar">{profileInitials(member.name)}</span>
        <div><span>Team member profile</span><h1>{member.name}</h1><p>{roleLabels[member.role]} in {member.teamName}</p></div>
        <strong className={member.accountActive ? "profile-status" : "profile-status profile-status--inactive"}><BadgeCheck aria-hidden="true" size={16} />{member.accountActive ? "Active account" : "Inactive account"}</strong>
      </header>
      <div className="profile-sections team-member-profile__sections">
        <section aria-labelledby="member-identity-title">
          <header><UserRound aria-hidden="true" size={19} /><div><span>Professional identity</span><h2 id="member-identity-title">Profile details</h2></div></header>
          <dl className="profile-definition-list">
            <div><dt>Name</dt><dd>{member.name}</dd></div>
            <div><dt>Representative role</dt><dd>{roleLabels[member.role]}</dd></div>
            <div><dt>Rank or grade</dt><dd>{member.rankOrGrade ?? "Not provided"}</dd></div>
            <div><dt>Work email</dt><dd><a href={`mailto:${member.email}`}><Mail aria-hidden="true" size={14} />{member.email}</a></dd></div>
          </dl>
        </section>
        <section aria-labelledby="member-team-title">
          <header><Building2 aria-hidden="true" size={19} /><div><span>Workspace context</span><h2 id="member-team-title">Team membership</h2></div></header>
          <dl className="profile-definition-list">
            <div><dt>Team</dt><dd>{member.teamName}</dd></div>
            <div><dt>Position</dt><dd>{member.workspacePosition === "MANAGER" ? "Manager" : "Member"}</dd></div>
            <div><dt>Membership</dt><dd>{sentenceCase(member.membershipState)}</dd></div>
            <div><dt>Skills</dt><dd>{member.skills.join(", ") || "Not listed"}</dd></div>
          </dl>
        </section>
      </div>
      <p className="profile-note team-member-profile__privacy">Private profile notes and service numbers are not shared through team workspaces.</p>
    </main>
  );
}

function sentenceCase(value: string) {
  return `${value.charAt(0)}${value.slice(1).toLowerCase()}`;
}
