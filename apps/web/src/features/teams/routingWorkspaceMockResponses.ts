import type { ServerCapabilities } from "../../lib/api/capabilityClient";
import type { TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import type { Session } from "../../lib/api/types";
import { json } from "../../test/render";

type RoutingResponseOptions = {
  omitMemberCount?: boolean;
  statisticsSummary?: Array<{
    key: string;
    label: string;
    value: number;
    unit: string;
    suppressed: boolean;
  }>;
  workloadVisible?: boolean;
};

export function routingIdentityResponse(
  url: URL,
  access: TeamWorkspaceAccess,
  options: RoutingResponseOptions,
  session: Session,
  capabilities: ServerCapabilities,
) {
  if (url.pathname.endsWith("/auth/me")) return json(session);
  if (url.pathname.endsWith("/me/capabilities")) return json(capabilities);
  if (url.pathname.endsWith("/team-workspaces")) return json({ items: [access] });
  if (!url.pathname.endsWith("/team-workspaces/crioc")) return undefined;
  return json({
    access,
    managerCount: 1,
    ...(options.omitMemberCount ? {} : { memberCount: 1 }),
    analystCount: 0,
    activeWorkCount: 2,
    dueSoonCount: 1,
    overdueCount: 0,
    workloadVisible: options.workloadVisible,
  });
}

export function routingReportingResponse(url: URL, options: RoutingResponseOptions) {
  if (url.pathname.endsWith("/statistics/scopes"))
    return json({
      items: [
        {
          id: "scope-crioc",
          unitId: "crioc",
          name: "CRIOC",
          kind: "ROOT",
          includeDescendants: true,
          units: [{ id: "crioc", parentId: null, name: "CRIOC", kind: "ROOT", depth: 0 }],
        },
      ],
    });
  if (url.pathname.endsWith("/statistics"))
    return json({
      summary: options.statisticsSummary ?? [
        { key: "received", label: "Received", value: 8, unit: "count", suppressed: false },
        { key: "completed", label: "Completed", value: 3, unit: "count", suppressed: false },
        { key: "released", label: "Released", value: 2, unit: "count", suppressed: false },
      ],
    });
  if (url.pathname.endsWith("/calendar")) return json({ items: [] });
  if (url.pathname.endsWith("/activity")) return json({ items: [] });
  return undefined;
}
