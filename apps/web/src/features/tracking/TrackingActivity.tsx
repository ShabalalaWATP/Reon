import { LoadMoreButton } from "../../components/LoadMoreButton";
import { useActivityPagination } from "../../components/useActivityPagination";
import { api } from "../../lib/api/client";
import type { TrackedRequestEvent } from "../../lib/api/types";
import { formatDate, trackingStatusLabel } from "../../lib/status";

type Props = {
  initialCursor?: string | null;
  initialEvents: TrackedRequestEvent[];
  requestId: string;
};

export function TrackingActivity({ initialCursor, initialEvents, requestId }: Props) {
  const { cursor, events, older } = useActivityPagination(initialEvents, initialCursor, (cursor) =>
    api.trackedRequest(requestId, cursor),
  );
  return (
    <section
      aria-labelledby="tracking-activity-title"
      className="detail-section"
      id="tracking-activity"
    >
      <div className="section-heading">
        <span>Immutable ticket history</span>
        <h2 id="tracking-activity-title">Travel and interactions</h2>
      </div>
      {events.length === 0 ? (
        <p className="inline-empty">No activity has been recorded yet.</p>
      ) : (
        <ol className="activity-list">
          {events.map((event) => (
            <li key={event.id}>
              <span aria-hidden="true" />
              <div>
                <strong>{event.message}</strong>
                {event.priorStatus && event.nextStatus && event.priorStatus !== event.nextStatus ? (
                  <p>
                    {trackingStatusLabel(event.priorStatus)} →{" "}
                    {trackingStatusLabel(event.nextStatus)}
                  </p>
                ) : null}
                <small>
                  {event.actorDisplayName ?? "Mist service"} ·{" "}
                  <time dateTime={event.createdAt}>{formatDate(event.createdAt, true)}</time>
                </small>
              </div>
            </li>
          ))}
        </ol>
      )}
      {older.isError ? (
        <p className="form-banner form-banner--error" role="alert">
          Older ticket history could not be loaded.
        </p>
      ) : null}
      <LoadMoreButton
        hasMore={Boolean(cursor)}
        loading={older.isPending}
        onLoad={() => older.mutate()}
      />
    </section>
  );
}
