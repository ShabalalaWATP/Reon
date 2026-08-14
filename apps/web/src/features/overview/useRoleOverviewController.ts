import { useQuery } from "@tanstack/react-query";

import { actionNotificationApi } from "../../lib/api/actionNotificationClient";
import type { ServerCapabilities } from "../../lib/api/capabilityClient";
import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { StatisticsDashboard } from "../../lib/api/statisticsTypes";
import type { TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import type { Session } from "../../lib/api/types";
import { useCapabilities } from "../../lib/capabilities/useCapabilities";
import { addLocalDays, localDateInputValue } from "../../lib/dateInputs";
import { navigationForRole, roleLabels, type NavigationItem } from "../../lib/routes";

const today = localDateInputValue(new Date());
const monthStart = localDateInputValue(addLocalDays(new Date(), -29));
const emptyFilters = { sections: [], actionTypes: [], dueBefore: null, limit: 6 };

export type OverviewActions = Awaited<ReturnType<typeof actionNotificationApi.actions>>;

export type ScopedOverviewState =
  | { kind: "loading" }
  | { kind: "error" }
  | {
      actions?: OverviewActions;
      destinations: NavigationItem[];
      firstName: string;
      kind: "ready";
      organisationName: string;
      statistics?: StatisticsDashboard;
    };

export type QualityOverviewState =
  | { kind: "loading" }
  | { kind: "error" }
  | {
      actions: OverviewActions;
      firstName: string;
      kind: "ready";
      metrics: Map<string, number>;
      scopeId: string;
      unitId: string;
    };

export function useScopedOverviewController(
  session: Session,
  administrator: boolean,
): ScopedOverviewState {
  const queryKeys = protectedQueryKeys(session);
  const capabilityQuery = useCapabilities();
  const { capabilities } = capabilityQuery;
  const scopes = useQuery({
    queryKey: queryKeys.statisticsScopes(),
    queryFn: api.statisticsScopes,
    enabled: capabilities.statistics,
  });
  const actions = useQuery({
    queryKey: queryKeys.actions("overview"),
    queryFn: () => actionNotificationApi.actions(emptyFilters),
    enabled: capabilities.myWork,
  });
  const scope = scopes.data?.items[0];
  const statistics = useQuery({
    queryKey: queryKeys.statistics(
      scope?.id ?? "",
      scope?.unitId ?? "",
      monthStart,
      today,
      "Europe/London",
    ),
    queryFn: () => loadStatistics(scope?.id, scope?.unitId),
    enabled: capabilities.statistics && Boolean(scope?.unitId),
  });
  const workspaces = useQuery({
    queryKey: queryKeys.teamWorkspaces(),
    queryFn: api.teamWorkspaces,
    enabled: !administrator,
  });
  return buildScopedState({
    actions,
    administrator,
    capabilities,
    capabilitiesPending: capabilityQuery.isPending,
    scope,
    scopes,
    session,
    statistics,
    workspace: workspaces.data?.items[0],
    workspaces,
  });
}

export function useQualityOverviewController(session: Session): QualityOverviewState {
  const queryKeys = protectedQueryKeys(session);
  const actions = useQuery({
    queryKey: queryKeys.actions("quality-overview"),
    queryFn: () => actionNotificationApi.actions(emptyFilters),
  });
  const scopes = useQuery({
    queryKey: queryKeys.statisticsScopes(),
    queryFn: api.statisticsScopes,
  });
  const scope = scopes.data?.items[0];
  const statistics = useQuery({
    queryKey: queryKeys.statistics(
      scope?.id ?? "",
      scope?.unitId ?? "",
      monthStart,
      today,
      "Europe/London",
    ),
    queryFn: () => loadStatistics(scope?.id, scope?.unitId),
    enabled: Boolean(scope?.unitId),
  });
  return buildQualityState({ actions, scope, scopes, session, statistics });
}

type QualityInput = {
  actions: QueryState<OverviewActions>;
  scope?: { id: string; unitId: string | null };
  scopes: QueryState<unknown>;
  session: Session;
  statistics: QueryState<StatisticsDashboard>;
};

function buildQualityState(input: QualityInput): QualityOverviewState {
  if (qualityLoading(input)) return { kind: "loading" };
  if (input.actions.isError || input.scopes.isError || input.statistics.isError)
    return { kind: "error" };
  if (!input.actions.data || !input.scope?.unitId || !input.statistics.data)
    return { kind: "error" };
  return {
    actions: input.actions.data,
    firstName: firstName(input.session),
    kind: "ready",
    metrics: new Map(
      input.statistics.data.summary.map((metric) => [metric.key, metric.value ?? 0]),
    ),
    scopeId: input.scope.id,
    unitId: input.scope.unitId,
  };
}

function qualityLoading(input: QualityInput) {
  if (input.actions.isPending || input.scopes.isPending) return true;
  return Boolean(input.scope?.unitId) && input.statistics.isPending;
}

async function loadStatistics(scopeId?: string, unitId?: string) {
  if (!scopeId || !unitId) throw new Error("A reporting scope is required.");
  return api.statistics({
    scopeId,
    unitId,
    from: monthStart,
    to: today,
    timeZone: "Europe/London",
  });
}

type ScopedInput = {
  actions: QueryState<OverviewActions>;
  administrator: boolean;
  capabilities: ServerCapabilities;
  capabilitiesPending: boolean;
  scope?: { id: string; name: string; unitId: string | null };
  scopes: QueryState<unknown>;
  session: Session;
  statistics: QueryState<StatisticsDashboard>;
  workspace?: TeamWorkspaceAccess;
  workspaces: QueryState<unknown>;
};

type QueryState<T> = { data?: T; isError: boolean; isPending: boolean };

function buildScopedState(input: ScopedInput): ScopedOverviewState {
  if (scopedLoading(input)) return { kind: "loading" };
  if (scopedError(input)) return { kind: "error" };
  const organisationName = input.administrator
    ? "Platform service"
    : (input.scope?.name ?? input.workspace?.teamName ?? "Organisation");
  const statisticsAvailable = Boolean(input.statistics.data);
  return {
    actions: input.actions.data,
    destinations: scopedDestinations(input, statisticsAvailable),
    firstName: firstName(input.session),
    kind: "ready",
    organisationName,
    statistics: input.statistics.data,
  };
}

function scopedLoading(input: ScopedInput) {
  if (input.capabilitiesPending) return true;
  if (input.capabilities.myWork && input.actions.isPending) return true;
  if (!input.administrator && input.workspaces.isPending) return true;
  return (
    input.capabilities.statistics &&
    (input.scopes.isPending || (Boolean(input.scope?.unitId) && input.statistics.isPending))
  );
}

function scopedError(input: ScopedInput) {
  if (input.capabilities.myWork && input.actions.isError) return true;
  if (input.workspaces.isError || (!input.administrator && !input.workspace)) return true;
  if (!input.capabilities.statistics) return false;
  if (input.scopes.isError || input.statistics.isError) return true;
  return !memberWithoutStatistics(input) && (!input.scope?.unitId || !input.statistics.data);
}

function memberWithoutStatistics(input: ScopedInput) {
  return (
    !input.administrator && input.workspace?.workspacePosition === "MEMBER" && !input.scope?.unitId
  );
}

function scopedDestinations(input: ScopedInput, statisticsAvailable: boolean) {
  const workspace = input.workspace
    ? { id: input.workspace.teamId, name: input.workspace.teamName }
    : undefined;
  return navigationForRole(input.session.user.role, input.capabilities, {
    statisticsAvailable,
    workspace,
  }).filter((item) => item.path !== "/overview");
}

function firstName(session: Session) {
  return session.user.displayName.trim().split(/\s+/u)[0] ?? session.user.displayName;
}

export function scopedOverviewEyebrow(
  session: Session,
  administrator: boolean,
  organisationName: string,
) {
  return administrator
    ? "Administration overview"
    : `${organisationName} · ${roleLabels[session.user.role]}`;
}
