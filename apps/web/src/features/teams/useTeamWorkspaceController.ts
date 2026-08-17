import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router";

import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import type { Session } from "../../lib/api/types";

export type WorkspaceView =
  "overview" | "queue" | "board" | "calendar" | "people" | "statistics" | "activity";
export type WorkspaceViewLink = readonly [WorkspaceView, string];

const deliveryViews: WorkspaceViewLink[] = [
  ["overview", "Overview"],
  ["queue", "Work queue"],
  ["board", "Board"],
  ["calendar", "Calendar"],
  ["people", "People"],
  ["statistics", "Statistics"],
  ["activity", "Activity"],
];
const routingViews: WorkspaceViewLink[] = deliveryViews.filter(([key]) => key !== "board");

export type TeamWorkspaceState =
  | { kind: "loading" }
  | { kind: "error"; retry: () => void }
  | { kind: "empty" }
  | { kind: "unavailable" }
  | { kind: "redirect"; path: string }
  | {
      availableViews: WorkspaceViewLink[];
      isRouting: boolean;
      kind: "ready";
      selected: TeamWorkspaceAccess;
      switchWorkspace: (teamId: string) => void;
      view: WorkspaceView;
      workspaces: TeamWorkspaceAccess[];
    };

export function useTeamWorkspaceController(session: Session): TeamWorkspaceState {
  const queryKeys = protectedQueryKeys(session);
  const navigate = useNavigate();
  const { teamId, view = "overview" } = useParams();
  const workspaces = useQuery({
    queryKey: queryKeys.teamWorkspaces(),
    queryFn: api.teamWorkspaces,
  });
  if (workspaces.isPending) return { kind: "loading" };
  if (workspaces.isError) return { kind: "error", retry: () => void workspaces.refetch() };
  if (workspaces.data.items.length === 0) return { kind: "empty" };
  const selected = workspaces.data.items.find((item) => item.teamId === teamId);
  if (!selected) return { kind: "unavailable" };
  const isRouting = selected.unitKind !== undefined && selected.unitKind !== "TEAM";
  const availableViews = allowedViews(selected, isRouting);
  if (!isWorkspaceView(view) || !availableViews.some(([key]) => key === view)) {
    return { kind: "redirect", path: `/teams/${selected.teamId}/overview` };
  }
  return {
    availableViews,
    isRouting,
    kind: "ready",
    selected,
    switchWorkspace: (nextTeamId) => void navigate(`/teams/${nextTeamId}/overview`),
    view,
    workspaces: workspaces.data.items,
  };
}

function allowedViews(access: TeamWorkspaceAccess, isRouting: boolean) {
  const baseViews = isRouting ? routingViews : deliveryViews;
  return baseViews.filter(([key]) => !access.views || access.views.includes(key.toUpperCase()));
}

function isWorkspaceView(value: string): value is WorkspaceView {
  return deliveryViews.some(([key]) => key === value);
}
