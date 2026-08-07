import { apiRequest } from "./client";
import type {
  ActionQuery,
  ActionWorkspace,
  NotificationCount,
  NotificationList,
  NotificationPreference,
  NotificationPreferences,
  NotificationQuery,
  NotificationStateAction,
  NotificationStateResult,
  PersonalNotification,
  SavedActionView,
  SavedActionViewInput,
  SavedActionViewUpdate,
} from "./actionNotificationTypes";

const listParams = (values: Record<string, string | string[] | number | undefined | null>) => {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (Array.isArray(value)) value.forEach((item) => query.append(key, item));
    else if (value !== null && value !== undefined && value !== "") query.set(key, String(value));
  }
  const encoded = query.toString();
  return encoded ? `?${encoded}` : "";
};

const utcDayBoundary = (value: string | null, endOfDay = false) => value
  ? `${value}T${endOfDay ? "23:59:59.999" : "00:00:00.000"}Z`
  : null;

export const actionNotificationApi = {
  actions: (input: ActionQuery) => apiRequest<ActionWorkspace>(`/me/actions${listParams({ sections: input.sections, actionTypes: input.actionTypes, dueBefore: input.dueBefore, limit: input.limit ?? 50, cursor: input.cursor })}`),
  createActionView: (input: SavedActionViewInput, csrfToken: string) => apiRequest<SavedActionView>("/me/actions/saved-views", { body: input, csrfToken, method: "POST" }),
  updateActionView: (id: string, input: SavedActionViewUpdate, csrfToken: string) => apiRequest<SavedActionView>(`/me/actions/saved-views/${encodeURIComponent(id)}`, { body: input, csrfToken, method: "PATCH" }),
  deleteActionView: (id: string, expectedVersion: number, csrfToken: string) => apiRequest<void>(`/me/actions/saved-views/${encodeURIComponent(id)}?expectedVersion=${expectedVersion}`, { csrfToken, method: "DELETE" }),
  notifications: (input: NotificationQuery) => apiRequest<NotificationList>(`/me/notifications${listParams({ states: input.states, eventTypes: input.eventTypes, from: utcDayBoundary(input.fromDate), to: utcDayBoundary(input.toDate, true), limit: input.limit ?? 50, cursor: input.cursor })}`),
  notificationCount: () => apiRequest<NotificationCount>("/me/notifications/count"),
  updateNotificationState: (action: NotificationStateAction, items: PersonalNotification[], csrfToken: string) => apiRequest<NotificationStateResult>("/me/notifications/state", { body: { action, targets: items.map((item) => ({ id: item.id, expectedVersion: item.version })) }, csrfToken, method: "POST" }),
  notificationPreferences: () => apiRequest<NotificationPreferences>("/me/notifications/preferences"),
  updateNotificationPreference: (preference: NotificationPreference, enabled: boolean, reminderDays: number[], csrfToken: string) => apiRequest<NotificationPreference>(`/me/notifications/preferences/${encodeURIComponent(preference.eventGroup)}`, { body: { enabled, reminderDays, expectedVersion: preference.version }, csrfToken, method: "PATCH" }),
};
