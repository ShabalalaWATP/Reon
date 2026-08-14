import { LoadMoreButton } from "../../components/LoadMoreButton";
import type { WorkItem } from "../../lib/api/types";
import { elapsedTime } from "../../lib/serviceTiming";
import { statusLabels } from "../../lib/status";

type WorkQueueListProps = {
  currentUserId: string;
  hasMore: boolean;
  items: WorkItem[];
  loadingMore: boolean;
  onLoadMore: () => void;
  onSelect: (id: string) => void;
  selectedId?: string;
  splitQualityStages?: boolean;
};

export function WorkQueueList({
  currentUserId,
  hasMore,
  items,
  loadingMore,
  onLoadMore,
  onSelect,
  selectedId,
  splitQualityStages = false,
}: WorkQueueListProps) {
  if (splitQualityStages) {
    return (
      <aside className="queue-list" aria-label="QC Team work items">
        <QualityQueueSection
          currentUserId={currentUserId}
          items={items.filter((item) => item.stage === "QUALITY_REVIEW")}
          label="Needs QC review"
          onSelect={onSelect}
          selectedId={selectedId}
        />
        <QualityQueueSection
          currentUserId={currentUserId}
          items={items.filter((item) => item.stage === "READY_FOR_RELEASE")}
          label="Ready for dissemination"
          onSelect={onSelect}
          selectedId={selectedId}
        />
        <LoadMoreButton hasMore={hasMore} loading={loadingMore} onLoad={onLoadMore} />
      </aside>
    );
  }
  return (
    <aside className="queue-list" aria-label="Work items">
      {items.map((item) => (
        <QueueRow
          currentUserId={currentUserId}
          item={item}
          key={item.id}
          onSelect={() => onSelect(item.id)}
          selected={item.id === selectedId}
        />
      ))}
      <LoadMoreButton hasMore={hasMore} loading={loadingMore} onLoad={onLoadMore} />
    </aside>
  );
}

function QualityQueueSection({
  currentUserId,
  items,
  label,
  onSelect,
  selectedId,
}: {
  currentUserId: string;
  items: WorkItem[];
  label: string;
  onSelect: (id: string) => void;
  selectedId?: string;
}) {
  return (
    <section aria-label={label} className="queue-stage-section">
      <header className="queue-stage-section__heading">
        <strong>{label}</strong>
        <span aria-label={`${items.length} items`}>{items.length}</span>
      </header>
      {items.length ? (
        items.map((item) => (
          <QueueRow
            currentUserId={currentUserId}
            item={item}
            key={item.id}
            onSelect={() => onSelect(item.id)}
            selected={item.id === selectedId}
          />
        ))
      ) : (
        <p className="queue-stage-section__empty">No items in this section.</p>
      )}
    </section>
  );
}

function QueueRow({
  currentUserId,
  item,
  onSelect,
  selected,
}: {
  currentUserId: string;
  item: WorkItem;
  onSelect: () => void;
  selected: boolean;
}) {
  const assignedToCurrentUser =
    Boolean(item.assignedToCurrentUser) || item.assigneeId === currentUserId;
  const analystLabel = item.assignmentRole === "LEAD_ANALYST" ? "Lead Analyst" : "Assigned Analyst";
  const ownership = assignedToCurrentUser
    ? `Assigned to you${item.assignmentRole ? ` · ${analystLabel}` : ""}`
    : !item.assigneeId
      ? "Available"
      : item.assigneeId === currentUserId
        ? "Assigned to you"
        : `Assigned to ${item.assigneeDisplayName ?? "team member"}`;
  return (
    <button
      aria-current={selected ? "true" : undefined}
      className={`queue-row${selected ? " queue-row--selected" : ""}`}
      onClick={onSelect}
      type="button"
    >
      <span className="queue-row__indicator" aria-hidden="true" />
      <span className="mono-ref">{item.requestReference}</span>
      <strong>{item.title}</strong>
      <small>{statusLabels[item.stage]}</small>
      <span>{ownership}</span>
      <time dateTime={item.createdAt}>Waiting {elapsedTime(item.createdAt)}</time>
    </button>
  );
}
