import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { PageState } from "../../components/PageState";
import { actionNotificationApi } from "../../lib/api/actionNotificationClient";
import type { NotificationPreference, NotificationQuery, NotificationStateAction, NotificationStateFilter, PersonalNotification } from "../../lib/api/actionNotificationTypes";
import { ApiError } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import { useAuth } from "../../lib/auth/AuthProvider";
import { freshnessMessage, humaniseCode } from "../my-work/myWorkModel";
import { NotificationPreferencesPanel } from "./NotificationPreferencesPanel";
import { NotificationRegister } from "./NotificationRegister";

const initialFilters: NotificationQuery = { states: [], eventTypes: [], fromDate: null, toDate: null };

export function NotificationsPage() {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState(initialFilters);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const userId = session!.user.id;
  const filtersKey = JSON.stringify(filters);
  const list = useInfiniteQuery({ queryKey: protectedQueryKeys.notifications(userId, filtersKey), queryFn: ({ pageParam }) => actionNotificationApi.notifications({ ...filters, cursor: pageParam ?? undefined }), initialPageParam: null as string | null, getNextPageParam: (page) => page.nextCursor, refetchInterval: 30_000 });
  const preferences = useQuery({ queryKey: protectedQueryKeys.notificationPreferences(userId), queryFn: actionNotificationApi.notificationPreferences });
  const state = useMutation({ mutationFn: ({ action, items }: { action: NotificationStateAction; items: PersonalNotification[] }) => actionNotificationApi.updateNotificationState(action, items, session!.csrfToken), onSuccess: () => { setSelected(new Set()); void refresh(); } });
  const preference = useMutation({ mutationFn: ({ current, enabled, days }: { current: NotificationPreference; enabled: boolean; days: number[] }) => actionNotificationApi.updateNotificationPreference(current, enabled, days, session!.csrfToken), onSuccess: () => void queryClient.invalidateQueries({ queryKey: protectedQueryKeys.notificationPreferences(userId) }) });
  const refresh = () => Promise.all([queryClient.invalidateQueries({ queryKey: ["protected", userId, "notifications"] }), queryClient.invalidateQueries({ queryKey: protectedQueryKeys.notificationCount(userId) })]);
  if (list.isPending || preferences.isPending) return <PageState kind="loading" title="Loading notifications" />;
  if (list.isError || preferences.isError) return <NotificationError error={(list.error ?? preferences.error)!} retry={() => { void list.refetch(); void preferences.refetch(); }} />;
  const first = list.data.pages[0];
  const items = list.data.pages.flatMap((page) => page.items);
  const chosen = items.filter((item) => selected.has(item.id));
  const eventTypes = [...new Set([...items.map((item) => item.eventType), ...filters.eventTypes])].sort();
  const freshness = freshnessMessage(first.freshness);
  const mutationError = state.error ?? preference.error;
  const toggle = (id: string) => setSelected((current) => { const next = new Set(current); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  return <main className="page-stack notifications-page">
    <header className="page-heading"><div><span>Personal updates</span><h1>Notifications</h1><p>Safe event summaries and links to work you are currently authorised to open.</p></div><span className="notification-total" aria-label={`${first.unreadCount} unread notifications`}>{first.unreadCount} unread</span></header>
    {freshness ? <p className="freshness-banner" role="status"><strong>{first.freshness.pendingCount ? "Updating" : humaniseCode(first.freshness.status)}</strong> {freshness}</p> : null}
    <section className="notification-tools" aria-label="Notification filters and actions"><div className="notification-filters"><label className="form-field"><span>State</span><select onChange={(event) => setFilters((current) => ({ ...current, states: event.target.value ? [event.target.value as NotificationStateFilter] : [] }))} value={filters.states[0] ?? ""}><option value="">All states</option><option value="UNREAD">Unread</option><option value="READ">Read</option><option value="ARCHIVED">Archived</option><option value="ACTION_COMPLETED">Action completed</option></select></label><label className="form-field"><span>Event type</span><select onChange={(event) => setFilters((current) => ({ ...current, eventTypes: event.target.value ? [event.target.value] : [] }))} value={filters.eventTypes[0] ?? ""}><option value="">All event types</option>{eventTypes.map((type) => <option key={type} value={type}>{humaniseCode(type)}</option>)}</select></label><label className="form-field"><span>From</span><input onChange={(event) => setFilters((current) => ({ ...current, fromDate: event.target.value || null }))} type="date" value={filters.fromDate ?? ""} /></label><label className="form-field"><span>To</span><input onChange={(event) => setFilters((current) => ({ ...current, toDate: event.target.value || null }))} type="date" value={filters.toDate ?? ""} /></label></div><div className="notification-actions"><button className="button" disabled={chosen.length === 0 || state.isPending} onClick={() => state.mutate({ action: "MARK_READ", items: chosen })} type="button">Mark read</button><button className="button button--quiet" disabled={chosen.length === 0 || state.isPending} onClick={() => state.mutate({ action: "ARCHIVE", items: chosen })} type="button">Archive</button><span aria-live="polite">{chosen.length} selected</span></div></section>
    {mutationError ? <p className="form-banner form-banner--error" role="alert">{mutationError instanceof ApiError ? mutationError.message : "The notification change could not be saved."}</p> : null}
    {items.length ? <NotificationRegister items={items} selected={selected} toggle={toggle} /> : <PageState kind="empty" title="No notifications in this view">Change a filter or return when new work is assigned.</PageState>}
    {list.hasNextPage ? <button className="button work-load-more" disabled={list.isFetchingNextPage} onClick={() => void list.fetchNextPage()} type="button">{list.isFetchingNextPage ? "Loading…" : "Load more"}</button> : null}
    <NotificationPreferencesPanel disabled={preference.isPending} onSave={(current, enabled, days) => preference.mutate({ current, enabled, days })} preferences={preferences.data.groups} />
  </main>;
}

function NotificationError({ error, retry }: { error: Error; retry: () => void }) {
  const denied = error instanceof ApiError && error.status === 403;
  return <PageState action={denied ? undefined : <button className="button" onClick={retry}>Try again</button>} kind="error" title={denied ? "Notification access ended" : "Notifications could not be loaded"}>{denied ? "Your current role no longer permits this notification view." : "Check your connection and try again."}</PageState>;
}
