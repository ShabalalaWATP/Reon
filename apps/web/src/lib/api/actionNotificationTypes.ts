export type ActionSection =
  | "NEEDS_MY_ACTION"
  | "WAITING"
  | "DUE_SOON"
  | "RECENTLY_COMPLETED";

export type ActionColumn =
  | "REFERENCE"
  | "TITLE"
  | "CURRENT_OWNER"
  | "REQUIRED_BY"
  | "AGE"
  | "LAST_CHANGED";

export type ActionFilters = {
  sections: ActionSection[];
  actionTypes: string[];
  dueBefore: string | null;
};

export type PersonalAction = {
  id: string;
  section: ActionSection;
  actionAccess: "PERSONAL" | "SHARED";
  actionType: string;
  sourceType: string;
  reference: string;
  title: string | null;
  currentOwner: string | null;
  requiredBy: string | null;
  ageDays: number;
  lastChangedAt: string;
  deepLink: string | null;
  sourceVersion: number;
  isStale: boolean;
};

export type SavedActionView = {
  id: string;
  name: string;
  filters: ActionFilters;
  visibleColumns: ActionColumn[];
  version: number;
};

export type ProjectionFreshness = {
  status: "CURRENT" | "STALE" | "DEGRADED";
  projectedAt: string | null;
  sourceChangedAt: string | null;
  lagSeconds: number | null;
  pendingCount: number;
};

export type ActionWorkspace = {
  items: PersonalAction[];
  counts: {
    needsMyAction: number;
    waiting: number;
    dueSoon: number;
    recentlyCompleted: number;
  };
  savedViews: SavedActionView[];
  nextCursor: string | null;
  freshness: ProjectionFreshness;
};

export type ActionQuery = ActionFilters & { limit?: number; cursor?: string };
export type SavedActionViewInput = Pick<SavedActionView, "name" | "filters" | "visibleColumns">;
export type SavedActionViewUpdate = SavedActionViewInput & { expectedVersion: number };

export type NotificationStateFilter = "UNREAD" | "READ" | "ARCHIVED" | "ACTION_COMPLETED";
export type NotificationStateAction = "MARK_READ" | "MARK_UNREAD" | "ARCHIVE" | "RESTORE" | "COMPLETE_ACTION";

export type PersonalNotification = {
  id: string;
  eventType: string;
  eventGroup: string;
  subject: string;
  occurredAt: string;
  deepLink: string | null;
  isRead: boolean;
  isArchived: boolean;
  isActionCompleted: boolean;
  readAt: string | null;
  archivedAt: string | null;
  actionCompletedAt: string | null;
  version: number;
};

export type NotificationQuery = {
  states: NotificationStateFilter[];
  eventTypes: string[];
  fromDate: string | null;
  toDate: string | null;
  limit?: number;
  cursor?: string;
};

export type NotificationList = {
  items: PersonalNotification[];
  unreadCount: number;
  nextCursor: string | null;
  freshness: ProjectionFreshness;
};

export type NotificationCount = { unreadCount: number; projectedAt: string | null };
export type NotificationStateResult = {
  items: Array<Pick<PersonalNotification, "id" | "isRead" | "isArchived" | "isActionCompleted" | "readAt" | "archivedAt" | "actionCompletedAt" | "version">>;
};
export type NotificationPreference = {
  eventGroup: string;
  enabled: boolean;
  mandatory: boolean;
  reminderDays: number[];
  version: number;
};
export type NotificationPreferences = { groups: NotificationPreference[] };
