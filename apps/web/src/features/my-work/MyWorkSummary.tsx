import type { ActionWorkspace } from "../../lib/api/actionNotificationTypes";
import {
  actionSections,
  freshnessMessage,
  humaniseCode,
  sectionCountKeys,
  sectionLabels,
} from "./myWorkModel";
import { useMyWorkPage } from "./useMyWorkPage";

export function WorkCounts({
  filters,
  first,
  setFilters,
}: Pick<ReturnType<typeof useMyWorkPage>, "filters" | "setFilters"> & { first: ActionWorkspace }) {
  const count = Object.values(first.counts).reduce((sum, value) => sum + value, 0);
  return (
    <>
      <p className="sr-only" aria-live="polite">
        {count} work items across all sections.
      </p>
      <div className="work-counts" aria-label="Work counts" role="group">
        {actionSections.map((section) => (
          <button
            aria-label={`${sectionLabels[section]} ${first.counts[sectionCountKeys[section]]}`}
            className={
              filters.sections[0] === section ? "work-count work-count--active" : "work-count"
            }
            key={section}
            onClick={() =>
              setFilters((current) => ({
                ...current,
                sections: current.sections[0] === section ? [] : [section],
              }))
            }
            type="button"
          >
            <span>{sectionLabels[section]}</span>
            <strong>{first.counts[sectionCountKeys[section]]}</strong>
          </button>
        ))}
      </div>
    </>
  );
}

export function FreshnessBanner({ first }: { first: ActionWorkspace }) {
  const count = Object.values(first.counts).reduce((sum, value) => sum + value, 0);
  const awaiting = isAwaitingInitialCheckpoint(first, count);
  const message = awaiting
    ? "No action update checkpoint has been recorded yet. This view will keep checking for changes."
    : freshnessMessage(first.freshness);
  if (!message) return null;
  const label = awaiting
    ? "Starting"
    : first.freshness.pendingCount
      ? "Updating"
      : humaniseCode(first.freshness.status);
  return (
    <p className="freshness-banner" role="status">
      <strong>{label}</strong> {message}
    </p>
  );
}

function isAwaitingInitialCheckpoint(first: ActionWorkspace, count: number) {
  return (
    count === 0 &&
    first.freshness.status === "DEGRADED" &&
    first.freshness.projectedAt === null &&
    first.freshness.sourceChangedAt === null
  );
}
