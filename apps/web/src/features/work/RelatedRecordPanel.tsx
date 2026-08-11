import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, RotateCcw, Search } from "lucide-react";
import { type FormEvent, useState } from "react";

import { PageState } from "../../components/PageState";
import { api, ApiError } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type {
  RelatedRecordMatch,
  RequestLinkType,
  RequestLinkWorkspace,
} from "../../lib/api/types";
import { formatDate, statusLabels } from "../../lib/status";
import { comparisonSummary } from "./relatedRecordPresentation";
import "./RelatedRecordPanel.css";

type Props = {
  csrfToken: string;
  userId: string;
  workItemId: string;
};

const linkLabels: Record<RequestLinkType, string> = {
  POSSIBLE_DUPLICATE: "Possible duplicate",
  RELATED_REQUEST: "Related request",
  EXISTING_OUTPUT: "Existing released product",
  NOT_RELEVANT: "Not relevant after review",
};

export function RelatedRecordPanel({ csrfToken, userId, workItemId }: Props) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState(false);
  const [selected, setSelected] = useState<RelatedRecordMatch | null>(null);
  const [linkType, setLinkType] = useState<RequestLinkType>("RELATED_REQUEST");
  const [reason, setReason] = useState("");
  const linksKey = protectedQueryKeys.requestLinks(userId, workItemId);
  const links = useQuery({
    queryKey: linksKey,
    queryFn: () => api.requestLinks(workItemId),
  });
  const results = useQuery({
    queryKey: protectedQueryKeys.relatedRecords(userId, workItemId, query),
    queryFn: () => api.relatedRecords(workItemId, query),
  });
  const create = useMutation({
    mutationFn: () => api.createRequestLink(workItemId, {
      expectedVersion: links.data!.sourceVersion,
      targetRequestId: selected!.id,
      linkType,
      reason,
    }, csrfToken),
    onSuccess: (workspace) => {
      queryClient.setQueryData<RequestLinkWorkspace>(linksKey, workspace);
      setSelected(null);
      setReason("");
      setLinkType("RELATED_REQUEST");
    },
  });
  const submitSearch = (event: FormEvent) => {
    event.preventDefault();
    const value = draft.trim();
    if (value.length >= 2) {
      setSelected(null);
      setQuery(value);
    }
  };
  const submitLink = (event: FormEvent) => {
    event.preventDefault();
    if (selected && links.data && reason.trim().length >= 10) create.mutate();
  };
  const summary = comparisonSummary(
    query,
    results.isPending,
    results.isError,
    results.data?.items,
  );

  return (
    <section
      aria-labelledby="related-record-title"
      className={`related-record-panel${expanded ? " related-record-panel--expanded" : ""}`}
    >
      <header className="related-record-heading">
        <div>
          <span>Request history</span>
          <h2 id="related-record-title">Previous request matches</h2>
          <p aria-live="polite">{summary}</p>
        </div>
        <button
          aria-controls="related-record-content"
          aria-expanded={expanded}
          aria-label={`${expanded ? "Hide" : "Review"} previous request matches`}
          className="related-record-toggle"
          onClick={() => setExpanded((current) => !current)}
          type="button"
        >
          <span>{expanded ? "Hide" : "Review"}</span>
          <ChevronDown aria-hidden="true" size={16} />
        </button>
      </header>
      {expanded ? (
        <div className="related-record-content" id="related-record-content">
          <p className="related-record-intro">
            All submitted fields are compared with earlier requests you are authorised to view. Scores are suggestions for human review and never change the route.
          </p>
          {links.isPending ? <PageState kind="loading" title="Loading recorded links" /> : null}
          {links.isError ? <PageState action={<button className="button" onClick={() => void links.refetch()}>Try again</button>} kind="error" title="Recorded links could not be loaded" /> : null}
          <form className="related-record-search" onSubmit={submitSearch} role="search">
            <label className="form-field"><span>Search request history</span><input minLength={2} onChange={(event) => setDraft(event.target.value)} placeholder="Add terms or a request reference" required value={draft} /></label>
            <button className="button button--quiet" type="submit"><Search aria-hidden="true" size={15} /> Search records</button>
            {query ? <button className="button button--quiet" onClick={() => { setDraft(""); setQuery(""); setSelected(null); }} type="button"><RotateCcw aria-hidden="true" size={14} /> Automatic matches</button> : null}
          </form>
          {results.isPending ? <p className="specialist-state" role="status">Comparing authorised request records…</p> : null}
          {results.isError ? <p className="form-banner form-banner--error" role="alert">Request comparison could not be completed.</p> : null}
          {results.data ? <p className="related-record-mode">{query ? `Results for “${query}”` : "Automatic comparison"} · {results.data.mode === "HYBRID" ? "semantic, full-text and field matching" : "full-text and field matching"}</p> : null}
          {results.data && results.data.items.length === 0 ? <p className="inline-empty">{query ? "No authorised request matches those terms." : "No credible match was found in the authorised request history."}</p> : null}
          {results.data?.items.length ? (
            <div aria-label="Previous request match results" className="related-record-scroll" role="region" tabIndex={0}>
              <MatchResults items={results.data.items} onSelect={(item) => { setSelected(item); if (!item.productAvailable && linkType === "EXISTING_OUTPUT") setLinkType("RELATED_REQUEST"); }} selectedId={selected?.id} />
            </div>
          ) : null}
          {selected && links.data ? (
            <div className="related-record-review">
              <div><span>Why it matched</span><strong>{selected.reference}: {selected.title}</strong></div>
              <ul>{selected.evidence.map((item) => <li key={`${item.field}-${item.reason}`}><strong>{item.field}</strong><span>{item.reason}</span>{item.excerpt ? <p>{item.excerpt}</p> : null}</li>)}</ul>
              <form className="related-record-form" onSubmit={submitLink}>
                <p>Record your decision. The comparison score is supporting evidence only.</p>
                <label className="form-field"><span>Decision <strong aria-hidden="true">*</strong></span><select onChange={(event) => setLinkType(event.target.value as RequestLinkType)} required value={linkType}><option value="POSSIBLE_DUPLICATE">Possible duplicate</option><option value="RELATED_REQUEST">Related request</option><option disabled={!selected.productAvailable} value="EXISTING_OUTPUT">Existing released product</option><option value="NOT_RELEVANT">Not relevant after review</option></select></label>
                <label className="form-field"><span>Reason <strong aria-hidden="true">*</strong></span><textarea minLength={10} onChange={(event) => setReason(event.target.value)} required rows={3} value={reason} /></label>
                {create.isError ? <p className="form-banner form-banner--error" role="alert">{create.error instanceof ApiError ? create.error.message : "The decision could not be recorded."}</p> : null}
                <button className="button button--primary" disabled={create.isPending} type="submit">{create.isPending ? "Recording…" : "Record decision"}</button>
              </form>
            </div>
          ) : null}
          {links.data ? <RecordedLinks workspace={links.data} /> : null}
        </div>
      ) : null}
    </section>
  );
}

function MatchResults({ items, onSelect, selectedId }: { items: RelatedRecordMatch[]; onSelect: (item: RelatedRecordMatch) => void; selectedId?: string }) {
  return <ul aria-label="Candidate matches" className="related-record-results">{items.map((item) => <li key={item.id}><button aria-pressed={selectedId === item.id} onClick={() => onSelect(item)} type="button"><span className={`match-score match-score--${item.matchBand.toLowerCase()}`}><strong>{item.matchStrength}</strong><small>match</small></span><span className="match-copy"><span><span className="mono-ref">{item.reference}</span><em>{item.matchBand.toLowerCase()}</em></span><strong>{item.title}</strong><small>{statusLabels[item.status]} · due {formatDate(item.requiredBy)}{item.productAvailable ? " · released product" : ""}</small><span>{item.reasons[0] ?? "Open to review the comparison evidence."}</span></span></button></li>)}</ul>;
}

function RecordedLinks({ workspace }: { workspace: RequestLinkWorkspace }) {
  if (workspace.items.length === 0) return <p className="inline-empty">No comparison decisions recorded.</p>;
  return <details className="related-record-decisions"><summary>Recorded decisions <span>{workspace.items.length}</span></summary><ul className="related-record-links">{workspace.items.map((link) => <li key={link.id}><span>{linkLabels[link.linkType]}</span><strong>{link.target.reference}: {link.target.title}</strong><p>{link.reason}</p><small>{link.actorDisplayName} · {formatDate(link.createdAt, true)}</small></li>)}</ul></details>;
}
