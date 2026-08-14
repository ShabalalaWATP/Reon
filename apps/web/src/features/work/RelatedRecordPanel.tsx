import { ChevronDown, RotateCcw, Search } from "lucide-react";

import { PageState } from "../../components/PageState";
import { ApiError } from "../../lib/api/client";
import type {
  RelatedRecordMatch,
  RequestLinkType,
  RequestLinkWorkspace,
  Session,
} from "../../lib/api/types";
import { formatDate, statusLabels } from "../../lib/status";
import { useRelatedRecordPanel, type RelatedRecordPanelController } from "./useRelatedRecordPanel";
import "./RelatedRecordPanel.css";

type Props = { session: Session; workItemId: string };

const linkLabels: Record<RequestLinkType, string> = {
  POSSIBLE_DUPLICATE: "Possible duplicate",
  RELATED_REQUEST: "Related request",
  EXISTING_OUTPUT: "Existing released product",
  NOT_RELEVANT: "Not relevant after review",
};

export function RelatedRecordPanel({ session, workItemId }: Props) {
  const controller = useRelatedRecordPanel(session, workItemId);
  return (
    <section
      aria-labelledby="related-record-title"
      className={`related-record-panel${controller.expanded ? " related-record-panel--expanded" : ""}`}
    >
      <RelatedRecordHeading controller={controller} />
      {controller.expanded ? <RelatedRecordContent controller={controller} /> : null}
    </section>
  );
}

function RelatedRecordHeading({ controller }: { controller: RelatedRecordPanelController }) {
  return (
    <header className="related-record-heading">
      <div>
        <span>Request history</span>
        <h2 id="related-record-title">Previous request matches</h2>
        <p aria-live="polite">{controller.summary}</p>
      </div>
      <button
        aria-controls="related-record-content"
        aria-expanded={controller.expanded}
        aria-label={`${controller.expanded ? "Hide" : "Review"} previous request matches`}
        className="related-record-toggle"
        onClick={() => controller.setExpanded((current) => !current)}
        type="button"
      >
        <span>{controller.expanded ? "Hide" : "Review"}</span>
        <ChevronDown aria-hidden="true" size={16} />
      </button>
    </header>
  );
}

function RelatedRecordContent({ controller }: { controller: RelatedRecordPanelController }) {
  return (
    <div className="related-record-content" id="related-record-content">
      <p className="related-record-intro">
        All submitted fields are compared with earlier requests you are authorised to view. Scores
        are suggestions for human review and never change the route.
      </p>
      <RecordedLinkLoadState controller={controller} />
      <RelatedRecordSearch controller={controller} />
      <ComparisonResults controller={controller} />
      <SelectedMatchReview controller={controller} />
      {controller.links.data ? <RecordedLinks workspace={controller.links.data} /> : null}
    </div>
  );
}

function RecordedLinkLoadState({ controller }: { controller: RelatedRecordPanelController }) {
  if (controller.links.isPending)
    return <PageState kind="loading" title="Loading recorded links" />;
  if (controller.links.isError)
    return (
      <PageState
        action={
          <button className="button" onClick={() => void controller.links.refetch()}>
            Try again
          </button>
        }
        kind="error"
        title="Recorded links could not be loaded"
      />
    );
  return null;
}

function RelatedRecordSearch({ controller }: { controller: RelatedRecordPanelController }) {
  return (
    <form className="related-record-search" onSubmit={controller.submitSearch} role="search">
      <label className="form-field">
        <span>Search request history</span>
        <input
          minLength={2}
          onChange={(event) => controller.setDraft(event.target.value)}
          placeholder="Add terms or a request reference"
          required
          value={controller.draft}
        />
      </label>
      <button className="button button--quiet" type="submit">
        <Search aria-hidden="true" size={15} /> Search records
      </button>
      {controller.query ? (
        <button className="button button--quiet" onClick={controller.resetSearch} type="button">
          <RotateCcw aria-hidden="true" size={14} /> Automatic matches
        </button>
      ) : null}
    </form>
  );
}

function ComparisonResults({ controller }: { controller: RelatedRecordPanelController }) {
  const result = controller.results;
  return (
    <>
      {result.isPending ? (
        <p className="specialist-state" role="status">
          Comparing authorised request records…
        </p>
      ) : null}
      {result.isError ? (
        <p className="form-banner form-banner--error" role="alert">
          Request comparison could not be completed.
        </p>
      ) : null}
      <ComparisonMode controller={controller} />
      <EmptyComparison controller={controller} />
      {result.data?.items.length ? (
        <div
          aria-label="Previous request match results"
          className="related-record-scroll"
          role="region"
          tabIndex={0}
        >
          <MatchResults
            items={result.data.items}
            onSelect={controller.selectMatch}
            selectedId={controller.selected?.id}
          />
        </div>
      ) : null}
    </>
  );
}

function ComparisonMode({ controller }: { controller: RelatedRecordPanelController }) {
  const data = controller.results.data;
  if (!data) return null;
  const method =
    data.mode === "HYBRID"
      ? "semantic, full-text and field matching"
      : "full-text and field matching";
  return (
    <p className="related-record-mode">
      {controller.query ? `Results for “${controller.query}”` : "Automatic comparison"} · {method}
    </p>
  );
}

function EmptyComparison({ controller }: { controller: RelatedRecordPanelController }) {
  if (!controller.results.data || controller.results.data.items.length > 0) return null;
  return (
    <p className="inline-empty">
      {controller.query
        ? "No authorised request matches those terms."
        : "No credible match was found in the authorised request history."}
    </p>
  );
}

function SelectedMatchReview({ controller }: { controller: RelatedRecordPanelController }) {
  const selected = controller.selected;
  if (!selected || !controller.links.data) return null;
  return (
    <div className="related-record-review">
      <div>
        <span>Why it matched</span>
        <strong>
          {selected.reference}: {selected.title}
        </strong>
      </div>
      <ul>
        {selected.evidence.map((item) => (
          <li key={`${item.field}-${item.reason}`}>
            <strong>{item.field}</strong>
            <span>{item.reason}</span>
            {item.excerpt ? <p>{item.excerpt}</p> : null}
          </li>
        ))}
      </ul>
      <form className="related-record-form" onSubmit={controller.submitLink}>
        <p>Record your decision. The comparison score is supporting evidence only.</p>
        <label className="form-field">
          <span>
            Decision <strong aria-hidden="true">*</strong>
          </span>
          <select
            onChange={(event) => controller.setLinkType(event.target.value as RequestLinkType)}
            required
            value={controller.linkType}
          >
            <option value="POSSIBLE_DUPLICATE">Possible duplicate</option>
            <option value="RELATED_REQUEST">Related request</option>
            <option disabled={!selected.productAvailable} value="EXISTING_OUTPUT">
              Existing released product
            </option>
            <option value="NOT_RELEVANT">Not relevant after review</option>
          </select>
        </label>
        <label className="form-field">
          <span>
            Reason <strong aria-hidden="true">*</strong>
          </span>
          <textarea
            minLength={10}
            onChange={(event) => controller.setReason(event.target.value)}
            required
            rows={3}
            value={controller.reason}
          />
        </label>
        {controller.create.isError ? (
          <p className="form-banner form-banner--error" role="alert">
            {controller.create.error instanceof ApiError
              ? controller.create.error.message
              : "The decision could not be recorded."}
          </p>
        ) : null}
        <button
          className="button button--primary"
          disabled={controller.create.isPending}
          type="submit"
        >
          {controller.create.isPending ? "Recording…" : "Record decision"}
        </button>
      </form>
    </div>
  );
}

function MatchResults({
  items,
  onSelect,
  selectedId,
}: {
  items: RelatedRecordMatch[];
  onSelect: (item: RelatedRecordMatch) => void;
  selectedId?: string;
}) {
  return (
    <ul aria-label="Candidate matches" className="related-record-results">
      {items.map((item) => (
        <li key={item.id}>
          <button
            aria-pressed={selectedId === item.id}
            onClick={() => onSelect(item)}
            type="button"
          >
            <span className={`match-score match-score--${item.matchBand.toLowerCase()}`}>
              <strong>{item.matchStrength}</strong>
              <small>match</small>
            </span>
            <span className="match-copy">
              <span>
                <span className="mono-ref">{item.reference}</span>
                <em>{item.matchBand.toLowerCase()}</em>
              </span>
              <strong>{item.title}</strong>
              <small>
                {statusLabels[item.status]} · due {formatDate(item.requiredBy)}
                {item.productAvailable ? " · released product" : ""}
              </small>
              <span>{item.reasons[0] ?? "Open to review the comparison evidence."}</span>
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

function RecordedLinks({ workspace }: { workspace: RequestLinkWorkspace }) {
  if (workspace.items.length === 0)
    return <p className="inline-empty">No comparison decisions recorded.</p>;
  return (
    <details className="related-record-decisions">
      <summary>
        Recorded decisions <span>{workspace.items.length}</span>
      </summary>
      <ul className="related-record-links">
        {workspace.items.map((link) => (
          <li key={link.id}>
            <span>{linkLabels[link.linkType]}</span>
            <strong>
              {link.target.reference}: {link.target.title}
            </strong>
            <p>{link.reason}</p>
            <small>
              {link.actorDisplayName} · {formatDate(link.createdAt, true)}
            </small>
          </li>
        ))}
      </ul>
    </details>
  );
}
