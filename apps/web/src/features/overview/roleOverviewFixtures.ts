import type { StatisticsScope } from "../../lib/api/statisticsTypes";

export function overviewScopes(
  empty: boolean,
  withTeam: boolean,
  scope: StatisticsScope,
  teamId: string,
) {
  if (empty) return { items: [] };
  if (!withTeam) return { items: [scope] };
  return {
    items: [
      {
        ...scope,
        id: "scope-ssg",
        unitId: teamId,
        name: "SSG Team",
        kind: "TEAM",
        units: [{ id: teamId, parentId: null, name: "SSG Team", kind: "TEAM", depth: 0 }],
      },
    ],
  };
}
