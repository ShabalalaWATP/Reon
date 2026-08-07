import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link2, Search } from "lucide-react";
import { type FormEvent, useState } from "react";

import { PageState } from "../../components/PageState";
import { api, ApiError } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type {
  RelatedRecordCandidate,
  RequestLinkType,
  RequestLinkWorkspace,
} from "../../lib/api/types";
import { formatDate, statusLabels } from "../../lib/status";

type Props = {
  csrfToken: string;
  userId: string;
  workItemId: string;
};

const linkLabels: Record<RequestLinkType, string> = {
  POSSIBLE_DUPLICATE: "Possible duplicate",
  RELATED_REQUEST: "Related request",
  EXISTING_OUTPUT: "Existing released product",
};

export function RelatedRecordPanel({ csrfToken, userId, workItemId }: Props) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<RelatedRecordCandidate | null>(null);
  const [linkType, setLinkType] = useState<RequestLinkType>("RELATED_REQUEST");
  const [reason, setReason] = useState("");
  const linksKey = protectedQueryKeys.requestLinks(userId, workItemId);
  const links = useQuery({
    queryKey: linksKey,
    queryFn: () => api.requestLinks(workItemId),
    enabled: open,
  });
  const results = useQuery({
    queryKey: protectedQueryKeys.relatedRecords(userId, workItemId, query),
    queryFn: () => api.relatedRecords(workItemId, query),
    enabled: open && query.length >= 2,
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

  if (!open) {
    return (
      <section className="related-record-panel">
        <div><span>Intake evidence</span><h2>Related records</h2></div>
        <p>Search and record a human judgement without changing the route.</p>
        <button className="button button--quiet" onClick={() => setOpen(true)} type="button">
          <Link2 aria-hidden="true" size={16} /> Check related records
        </button>
      </section>
    );
  }

  return (
    <section aria-labelledby="related-record-title" className="related-record-panel">
      <div className="section-heading"><span>Intake evidence</span><h2 id="related-record-title">Related records</h2></div>
      {links.isPending ? <PageState kind="loading" title="Loading recorded links" /> : null}
      {links.isError ? <PageState action={<button className="button" onClick={() => void links.refetch()}>Try again</button>} kind="error" title="Recorded links could not be loaded" /> : null}
      {links.data ? <RecordedLinks workspace={links.data} /> : null}
      <form className="related-record-search" onSubmit={submitSearch} role="search">
        <label className="form-field"><span>Reference or title <strong aria-hidden="true">*</strong></span><input minLength={2} onChange={(event) => setDraft(event.target.value)} required value={draft} /></label>
        <button className="button button--quiet" type="submit"><Search aria-hidden="true" size={15} /> Search</button>
      </form>
      {results.isPending ? <p className="specialist-state" role="status">Searching authorised records…</p> : null}
      {results.isError ? <p className="form-banner form-banner--error" role="alert">Search could not be completed.</p> : null}
      {results.data && results.data.items.length === 0 ? <p className="inline-empty">No authorised records match this search.</p> : null}
      {results.data?.items.length ? <ul className="related-record-results">{results.data.items.map((item) => <li key={item.id}><button aria-pressed={selected?.id === item.id} onClick={() => { setSelected(item); if (!item.productAvailable && linkType === "EXISTING_OUTPUT") setLinkType("RELATED_REQUEST"); }} type="button"><span className="mono-ref">{item.reference}</span><strong>{item.title}</strong><small>{statusLabels[item.status]} · due {formatDate(item.requiredBy)}{item.productAvailable ? " · released product" : ""}</small></button></li>)}</ul> : null}
      {selected && links.data ? (
        <form className="related-record-form" onSubmit={submitLink}>
          <p>Record link to <strong>{selected.reference}</strong></p>
          <label className="form-field"><span>Link type <strong aria-hidden="true">*</strong></span><select onChange={(event) => setLinkType(event.target.value as RequestLinkType)} required value={linkType}><option value="POSSIBLE_DUPLICATE">Possible duplicate</option><option value="RELATED_REQUEST">Related request</option><option disabled={!selected.productAvailable} value="EXISTING_OUTPUT">Existing released product</option></select></label>
          <label className="form-field"><span>Reason <strong aria-hidden="true">*</strong></span><textarea minLength={10} onChange={(event) => setReason(event.target.value)} required rows={3} value={reason} /></label>
          {create.isError ? <p className="form-banner form-banner--error" role="alert">{create.error instanceof ApiError ? create.error.message : "The link could not be recorded."}</p> : null}
          <button className="button button--primary" disabled={create.isPending} type="submit">{create.isPending ? "Recording…" : "Record link"}</button>
        </form>
      ) : null}
    </section>
  );
}

function RecordedLinks({ workspace }: { workspace: RequestLinkWorkspace }) {
  if (workspace.items.length === 0) return <p className="inline-empty">No related-record checks recorded.</p>;
  return <ul className="related-record-links">{workspace.items.map((link) => <li key={link.id}><span>{linkLabels[link.linkType]}</span><strong>{link.target.reference}: {link.target.title}</strong><p>{link.reason}</p><small>{link.actorDisplayName} · {formatDate(link.createdAt, true)}</small></li>)}</ul>;
}
