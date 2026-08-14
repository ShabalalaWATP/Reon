import { PageState } from "../../components/PageState";
import type {
  NotificationList,
  NotificationPreference,
  NotificationStateFilter,
  PersonalNotification,
} from "../../lib/api/actionNotificationTypes";
import { ApiError } from "../../lib/api/client";
import { freshnessMessage, humaniseCode } from "../my-work/myWorkModel";
import { NotificationPreferencesPanel } from "./NotificationPreferencesPanel";
import { NotificationRegister } from "./NotificationRegister";
import { useNotificationsPage } from "./useNotificationsPage";

export function NotificationsPage() {
  const controller = useNotificationsPage();
  if (controller.list.isPending || controller.preferences.isPending)
    return <PageState kind="loading" title="Loading notifications" />;
  if (controller.list.isError || controller.preferences.isError)
    return (
      <NotificationError
        error={(controller.list.error ?? controller.preferences.error)!}
        retry={() => {
          void controller.list.refetch();
          void controller.preferences.refetch();
        }}
      />
    );
  if (!controller.preferences.data)
    return (
      <PageState kind="error" title="Notifications could not be loaded">
        Notification preferences were not available. Try again.
      </PageState>
    );
  const first = controller.list.data.pages[0];
  const items = controller.list.data.pages.flatMap((page) => page.items);
  return (
    <NotificationsView
      controller={controller}
      first={first}
      items={items}
      preferenceGroups={controller.preferences.data.groups}
    />
  );
}

function NotificationsView({
  controller,
  first,
  items,
  preferenceGroups,
}: {
  controller: ReturnType<typeof useNotificationsPage>;
  first: NotificationList;
  items: PersonalNotification[];
  preferenceGroups: NotificationPreference[];
}) {
  const { filters, list, preference, selected, state, toggle } = controller;
  const chosen = items.filter((item) => selected.has(item.id));
  const eventTypes = [
    ...new Set([...items.map((item) => item.eventType), ...filters.eventTypes]),
  ].sort();
  return (
    <main className="page-stack notifications-page">
      <header className="page-heading">
        <div>
          <span>Personal updates</span>
          <h1>Notifications</h1>
          <p>Safe event summaries and links to work you are currently authorised to open.</p>
        </div>
        <span
          className="notification-total"
          aria-label={`${first.unreadCount} unread notifications`}
        >
          {first.unreadCount} unread
        </span>
      </header>
      <NotificationFreshness first={first} />
      <NotificationTools chosen={chosen} controller={controller} eventTypes={eventTypes} />
      <NotificationMutationError errors={[state.error, preference.error]} />
      <NotificationResults items={items} selected={selected} toggle={toggle} />
      <NotificationLoadMore list={list} />
      <NotificationPreferencesPanel
        disabled={preference.isPending}
        onSave={(current, enabled, days) => preference.mutate({ current, enabled, days })}
        preferences={preferenceGroups}
      />
    </main>
  );
}

function NotificationFreshness({ first }: { first: NotificationList }) {
  const message = freshnessMessage(first.freshness);
  if (!message) return null;
  return (
    <p className="freshness-banner" role="status">
      <strong>
        {first.freshness.pendingCount ? "Updating" : humaniseCode(first.freshness.status)}
      </strong>{" "}
      {message}
    </p>
  );
}

function NotificationTools({
  chosen,
  controller,
  eventTypes,
}: {
  chosen: PersonalNotification[];
  controller: ReturnType<typeof useNotificationsPage>;
  eventTypes: string[];
}) {
  const { filters, setFilters, state } = controller;
  return (
    <section className="notification-tools" aria-label="Notification filters and actions">
      <div className="notification-filters">
        <label className="form-field">
          <span>State</span>
          <select
            onChange={(event) =>
              setFilters((current) => ({
                ...current,
                states: event.target.value ? [event.target.value as NotificationStateFilter] : [],
              }))
            }
            value={filters.states[0] ?? ""}
          >
            <option value="">All states</option>
            <option value="UNREAD">Unread</option>
            <option value="READ">Read</option>
            <option value="ARCHIVED">Archived</option>
            <option value="ACTION_COMPLETED">Action completed</option>
          </select>
        </label>
        <label className="form-field">
          <span>Event type</span>
          <select
            onChange={(event) =>
              setFilters((current) => ({
                ...current,
                eventTypes: event.target.value ? [event.target.value] : [],
              }))
            }
            value={filters.eventTypes[0] ?? ""}
          >
            <option value="">All event types</option>
            {eventTypes.map((type) => (
              <option key={type} value={type}>
                {humaniseCode(type)}
              </option>
            ))}
          </select>
        </label>
        <label className="form-field">
          <span>From</span>
          <input
            onChange={(event) =>
              setFilters((current) => ({ ...current, fromDate: event.target.value || null }))
            }
            type="date"
            value={filters.fromDate ?? ""}
          />
        </label>
        <label className="form-field">
          <span>To</span>
          <input
            onChange={(event) =>
              setFilters((current) => ({ ...current, toDate: event.target.value || null }))
            }
            type="date"
            value={filters.toDate ?? ""}
          />
        </label>
      </div>
      <div className="notification-actions">
        <button
          className="button"
          disabled={chosen.length === 0 || state.isPending}
          onClick={() => state.mutate({ action: "MARK_READ", items: chosen })}
          type="button"
        >
          Mark read
        </button>
        <button
          className="button button--quiet"
          disabled={chosen.length === 0 || state.isPending}
          onClick={() => state.mutate({ action: "ARCHIVE", items: chosen })}
          type="button"
        >
          Archive
        </button>
        <span aria-live="polite">{chosen.length} selected</span>
      </div>
    </section>
  );
}

function NotificationMutationError({ errors }: { errors: Array<Error | null> }) {
  const error = errors.find(Boolean);
  if (!error) return null;
  return (
    <p className="form-banner form-banner--error" role="alert">
      {error instanceof ApiError ? error.message : "The notification change could not be saved."}
    </p>
  );
}

function NotificationResults({
  items,
  selected,
  toggle,
}: {
  items: PersonalNotification[];
  selected: Set<string>;
  toggle: (id: string) => void;
}) {
  if (items.length === 0)
    return (
      <PageState kind="empty" title="No notifications in this view">
        Change a filter or return when new work is assigned.
      </PageState>
    );
  return <NotificationRegister items={items} selected={selected} toggle={toggle} />;
}

function NotificationLoadMore({ list }: { list: ReturnType<typeof useNotificationsPage>["list"] }) {
  if (!list.hasNextPage) return null;
  return (
    <button
      className="button work-load-more"
      disabled={list.isFetchingNextPage}
      onClick={() => void list.fetchNextPage()}
      type="button"
    >
      {list.isFetchingNextPage ? "Loading…" : "Load more"}
    </button>
  );
}

function NotificationError({ error, retry }: { error: Error; retry: () => void }) {
  const denied = error instanceof ApiError && error.status === 403;
  return (
    <PageState
      action={
        denied ? undefined : (
          <button className="button" onClick={retry}>
            Try again
          </button>
        )
      }
      kind="error"
      title={denied ? "Notification access ended" : "Notifications could not be loaded"}
    >
      {denied
        ? "Your current role no longer permits this notification view."
        : "Check your connection and try again."}
    </PageState>
  );
}
