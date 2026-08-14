import { useMemo, useState } from "react";
import { Link } from "react-router";

import type { TeamMember, TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import {
  canEndMembership,
  canManageRoster,
  DEFAULT_PEOPLE_SORT,
  memberPosition,
  sortPeople,
  type PeopleSortKey,
} from "./peopleSorting";
import { useEndMembershipController } from "./useRosterController";

export function PeopleTable({
  access,
  items,
  userId,
}: {
  access: TeamWorkspaceAccess;
  items: TeamMember[];
  userId: string;
}) {
  const [sort, setSort] = useState(DEFAULT_PEOPLE_SORT);
  const sorted = useMemo(
    () => sortPeople(items, sort, canManageRoster(access)),
    [access, items, sort],
  );
  const changeSort = (key: PeopleSortKey) =>
    setSort((current) => ({
      key,
      direction:
        current.key === key && current.direction === "ascending" ? "descending" : "ascending",
    }));
  return (
    <div className="team-table-wrap">
      <table className="team-table">
        <caption>Workspace membership history</caption>
        <PeopleTableHead changeSort={changeSort} sort={sort} />
        <tbody>
          {sorted.map((member) => (
            <PersonRow access={access} key={member.membershipId} member={member} userId={userId} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PeopleTableHead({
  changeSort,
  sort,
}: {
  changeSort: (key: PeopleSortKey) => void;
  sort: typeof DEFAULT_PEOPLE_SORT;
}) {
  const headers: Array<[PeopleSortKey, string]> = [
    ["person", "Person"],
    ["position", "Position"],
    ["skills", "Skills"],
    ["state", "State"],
    ["effective", "Effective"],
    ["activeWork", "Active work"],
    ["action", "Action"],
  ];
  return (
    <thead>
      <tr>
        {headers.map(([key, label]) => (
          <SortHeader
            active={sort.key === key}
            direction={sort.direction}
            key={key}
            label={label}
            onSort={() => changeSort(key)}
          />
        ))}
      </tr>
    </thead>
  );
}

function SortHeader({
  active,
  direction,
  label,
  onSort,
}: {
  active: boolean;
  direction: "ascending" | "descending";
  label: string;
  onSort: () => void;
}) {
  return (
    <th aria-sort={active ? direction : "none"} scope="col">
      <button className="team-table__sort" onClick={onSort} type="button">
        <span>{label}</span>
        <i aria-hidden="true">{active ? (direction === "ascending" ? "↑" : "↓") : "↕"}</i>
      </button>
    </th>
  );
}

function PersonRow({
  access,
  member,
}: {
  access: TeamWorkspaceAccess;
  member: TeamMember;
  userId: string;
}) {
  const controller = useEndMembershipController(access, member);
  const canEnd = canEndMembership(access, member);
  return (
    <>
      <MemberRow access={access} canEnd={canEnd} controller={controller} member={member} />
      {controller.ending ? <EndMembershipRow controller={controller} /> : null}
    </>
  );
}

function MemberRow({
  access,
  canEnd,
  controller,
  member,
}: {
  access: TeamWorkspaceAccess;
  canEnd: boolean;
  controller: ReturnType<typeof useEndMembershipController>;
  member: TeamMember;
}) {
  return (
    <tr>
      <th scope="row">
        <Link
          className="team-person-link"
          to={`/teams/${access.teamId}/people/${member.accountId}`}
        >
          {member.displayName}
        </Link>
        {member.endReason ? <small>{member.endReason}</small> : null}
      </th>
      <td>{memberPosition(member)}</td>
      <td>
        <Skills member={member} />
      </td>
      <td>
        <span className={`membership-state membership-state--${member.state.toLowerCase()}`}>
          {member.state.toLowerCase()}
        </span>
      </td>
      <td>{membershipPeriod(member)}</td>
      <td>{member.activeWorkCount}</td>
      <td>
        {canEnd ? (
          <button
            className="button button--quiet"
            disabled={member.activeWorkCount > 0}
            onClick={() => controller.setEnding(!controller.ending)}
            type="button"
          >
            End membership
          </button>
        ) : (
          "Not applicable"
        )}
      </td>
    </tr>
  );
}

function Skills({ member }: { member: TeamMember }) {
  if (!member.skills.length) return <span className="muted-text">Not listed</span>;
  return (
    <ul aria-label={`${member.displayName} skills`} className="skill-tags">
      {member.skills.map((skill) => (
        <li key={skill}>{skill}</li>
      ))}
    </ul>
  );
}

function EndMembershipRow({
  controller,
}: {
  controller: ReturnType<typeof useEndMembershipController>;
}) {
  return (
    <tr className="end-membership-row">
      <td colSpan={7}>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            controller.submit();
          }}
        >
          <label className="form-field">
            Reason for ending membership<span className="field-hint">Required</span>
            <textarea
              minLength={10}
              onChange={(event) => controller.setReason(event.target.value)}
              required
              value={controller.reason}
            />
          </label>
          {controller.error ? <p role="alert">{controller.error}</p> : null}
          <button className="button button--danger" disabled={controller.saving} type="submit">
            Confirm end
          </button>
        </form>
      </td>
    </tr>
  );
}

function membershipPeriod(member: TeamMember) {
  return `${formatDate(member.effectiveFrom)}${member.effectiveUntil ? ` to ${formatDate(member.effectiveUntil)}` : " onwards"}`;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" }).format(new Date(value));
}
