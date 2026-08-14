import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { actionNotificationApi } from "../../lib/api/actionNotificationClient";
import type {
  NotificationCount,
  NotificationPreference,
  NotificationQuery,
  NotificationStateAction,
  PersonalNotification,
} from "../../lib/api/actionNotificationTypes";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import { useAuth } from "../../lib/auth/AuthProvider";

const initialFilters: NotificationQuery = {
  states: [],
  eventTypes: [],
  fromDate: null,
  toDate: null,
};

export function useNotificationsPage() {
  const { session } = useAuth();
  const queryKeys = useMemo(() => protectedQueryKeys(session), [session]);
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState(initialFilters);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const list = useInfiniteQuery({
    queryKey: queryKeys.notifications(JSON.stringify(filters)),
    queryFn: ({ pageParam }) =>
      actionNotificationApi.notifications({ ...filters, cursor: pageParam ?? undefined }),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.nextCursor,
    refetchInterval: 30_000,
  });
  const preferences = useQuery({
    queryKey: queryKeys.notificationPreferences(),
    queryFn: actionNotificationApi.notificationPreferences,
  });
  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.notificationsRoot() }),
      queryClient.invalidateQueries({ queryKey: queryKeys.notificationCount() }),
    ]);
  const state = useMutation({
    mutationFn: ({
      action,
      items,
    }: {
      action: NotificationStateAction;
      items: PersonalNotification[];
    }) => actionNotificationApi.updateNotificationState(action, items, session!.csrfToken),
    onSuccess: () => {
      setSelected(new Set());
      void refresh();
    },
  });
  const preference = useMutation({
    mutationFn: ({
      current,
      enabled,
      days,
    }: {
      current: NotificationPreference;
      enabled: boolean;
      days: number[];
    }) =>
      actionNotificationApi.updateNotificationPreference(
        current,
        enabled,
        days,
        session!.csrfToken,
      ),
    onSuccess: () =>
      void queryClient.invalidateQueries({ queryKey: queryKeys.notificationPreferences() }),
  });
  const firstPage = list.data?.pages[0];
  useEffect(() => {
    if (!firstPage) return;
    queryClient.setQueryData<NotificationCount>(queryKeys.notificationCount(), {
      unreadCount: firstPage.unreadCount,
      projectedAt: firstPage.freshness.projectedAt,
    });
  }, [firstPage, queryClient, queryKeys]);
  const toggle = (id: string) =>
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  return { filters, list, preference, preferences, selected, setFilters, state, toggle };
}
