import { LoadMoreButton } from "../../components/LoadMoreButton";
import { useActivityPagination } from "../../components/useActivityPagination";
import { api } from "../../lib/api/client";
import type { RequestEvent } from "../../lib/api/types";
import { formatDate } from "../../lib/status";

type RequestActivityProps = {
  initialCursor?: string | null;
  initialEvents: RequestEvent[];
  requestId: string;
};

export function RequestActivity({ initialCursor, initialEvents, requestId }: RequestActivityProps) {
  const { cursor, events, older } = useActivityPagination(initialEvents, initialCursor, (cursor) =>
    api.request(requestId, cursor),
  );
  return (
    <section className="detail-section" aria-labelledby="activity-title" id="request-activity">
      <div className="section-heading">
        <span>Immutable history</span>
        <h2 id="activity-title">Activity</h2>
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
          Older activity could not be loaded.
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
