import type {
  ActionColumn,
  ActionSection,
  ProjectionFreshness,
} from "../../lib/api/actionNotificationTypes";

export const actionSections: ActionSection[] = [
  "NEEDS_MY_ACTION",
  "WAITING",
  "DUE_SOON",
  "RECENTLY_COMPLETED",
];
export const sectionLabels: Record<ActionSection, string> = {
  NEEDS_MY_ACTION: "Needs attention",
  WAITING: "Waiting",
  DUE_SOON: "Due soon",
  RECENTLY_COMPLETED: "Recently completed",
};
export const sectionCountKeys = {
  NEEDS_MY_ACTION: "needsMyAction",
  WAITING: "waiting",
  DUE_SOON: "dueSoon",
  RECENTLY_COMPLETED: "recentlyCompleted",
} as const;

export const actionColumns: ActionColumn[] = [
  "REFERENCE",
  "TITLE",
  "CURRENT_OWNER",
  "REQUIRED_BY",
  "AGE",
  "LAST_CHANGED",
];
export const columnLabels: Record<ActionColumn, string> = {
  REFERENCE: "Reference",
  TITLE: "Title",
  CURRENT_OWNER: "Current owner",
  REQUIRED_BY: "Required date",
  AGE: "Age",
  LAST_CHANGED: "Last changed",
};

const allowedRoots = [
  "/my-work",
  "/requests",
  "/triage",
  "/coordination",
  "/allocation",
  "/delivery",
  "/quality-release",
  "/admin",
  "/organisation",
  "/teams",
  "/calendar",
  "/statistics",
  "/notifications",
];

export function safeWorkspaceHref(value: string | null) {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\"))
    return null;
  const url = new URL(value, "https://istari.local");
  if (url.origin !== "https://istari.local") return null;
  return allowedRoots.some((root) => url.pathname === root || url.pathname.startsWith(`${root}/`))
    ? `${url.pathname}${url.search}${url.hash}`
    : null;
}

export function humaniseCode(value: string) {
  return value
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/^./, (letter) => letter.toUpperCase());
}

const actionTypeLabels: Partial<Record<string, string>> = {
  CHOOSE_OPS_GROUP: "New request requires attention",
};

export function actionTypeLabel(value: string) {
  return actionTypeLabels[value] ?? humaniseCode(value);
}

export function availableToLabel(value: string | null) {
  return value?.replace(/ · Awaiting owner$/u, "") ?? "your unit";
}

export function formatActionDate(value: string | null) {
  return value
    ? new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric" }).format(
        new Date(value),
      )
    : "Not set";
}

export function freshnessMessage(freshness: ProjectionFreshness) {
  if (freshness.pendingCount > 0)
    return `${freshness.pendingCount} update${freshness.pendingCount === 1 ? " is" : "s are"} still being applied.`;
  if (freshness.status === "CURRENT") return null;
  if (freshness.status === "DEGRADED")
    return "Live updates are unavailable. This view will keep checking for changes.";
  if (freshness.lagSeconds === null) return "This view may be out of date.";
  const minutes = Math.max(1, Math.ceil(freshness.lagSeconds / 60));
  return `This view is about ${minutes} minute${minutes === 1 ? "" : "s"} behind.`;
}
