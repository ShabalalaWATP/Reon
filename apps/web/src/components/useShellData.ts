import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { actionNotificationApi } from "../lib/api/actionNotificationClient";
import { api } from "../lib/api/client";
import { protectedQueryKeys } from "../lib/api/queryKeys";
import type { Session } from "../lib/api/types";
import { useCapabilities } from "../lib/capabilities/useCapabilities";
import { navigationForRole } from "../lib/routes";

const TEAM_WORKSPACE_ROLES = new Set([
  "INTAKE_TRIAGE",
  "SERVICE_COORDINATION",
  "OPERATIONS_ALLOCATION",
  "DELIVERY_TEAM_LEAD",
  "DELIVERY_SPECIALIST",
]);

export function useShellData(session: Session, pathname: string) {
  const queryKeys = useMemo(() => protectedQueryKeys(session), [session]);
  const { capabilities } = useCapabilities();
  const notificationCount = useQuery({
    queryKey: queryKeys.notificationCount(),
    queryFn: actionNotificationApi.notificationCount,
    enabled: capabilities.notifications && pathname !== "/notifications",
    refetchInterval: 30_000,
  });
  const statisticsScopes = useQuery({
    queryKey: queryKeys.statisticsScopes(),
    queryFn: api.statisticsScopes,
    enabled: capabilities.statistics,
    staleTime: 60_000,
  });
  const teamWorkspaces = useQuery({
    queryKey: queryKeys.teamWorkspaces(),
    queryFn: api.teamWorkspaces,
    enabled: TEAM_WORKSPACE_ROLES.has(session.user.role),
    staleTime: 60_000,
  });
  const workspace = teamWorkspaces.data?.items[0];
  const navigation = navigationForRole(session.user.role, capabilities, {
    statisticsAvailable: (statisticsScopes.data?.items.length ?? 0) > 0,
    workspace: workspace ? { id: workspace.teamId, name: workspace.teamName } : undefined,
  });
  return {
    capabilities,
    navigation,
    notificationCount: notificationCount.data?.unreadCount ?? 0,
    teamWorkspaces,
  };
}
