import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";

import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type {
  RelatedRecordMatch,
  RequestLinkType,
  RequestLinkWorkspace,
  Session,
} from "../../lib/api/types";
import { comparisonSummary } from "./relatedRecordPresentation";

export function useRelatedRecordPanel(session: Session, workItemId: string) {
  const queryKeys = protectedQueryKeys(session);
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState(false);
  const [selected, setSelected] = useState<RelatedRecordMatch | null>(null);
  const [linkType, setLinkType] = useState<RequestLinkType>("RELATED_REQUEST");
  const [reason, setReason] = useState("");
  const linksKey = queryKeys.requestLinks(workItemId);
  const links = useQuery({
    queryKey: linksKey,
    queryFn: () => api.requestLinks(workItemId),
  });
  const results = useQuery({
    queryKey: queryKeys.relatedRecords(workItemId, query),
    queryFn: () => api.relatedRecords(workItemId, query),
  });
  const create = useMutation({
    mutationFn: () =>
      api.createRequestLink(
        workItemId,
        {
          expectedVersion: links.data!.sourceVersion,
          targetRequestId: selected!.id,
          linkType,
          reason,
        },
        session.csrfToken,
      ),
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
    if (value.length < 2) return;
    setSelected(null);
    setQuery(value);
  };
  const submitLink = (event: FormEvent) => {
    event.preventDefault();
    if (selected && links.data && reason.trim().length >= 10) create.mutate();
  };
  const resetSearch = () => {
    setDraft("");
    setQuery("");
    setSelected(null);
  };
  const selectMatch = (item: RelatedRecordMatch) => {
    setSelected(item);
    if (!item.productAvailable && linkType === "EXISTING_OUTPUT") {
      setLinkType("RELATED_REQUEST");
    }
  };

  return {
    create,
    draft,
    expanded,
    linkType,
    links,
    query,
    reason,
    resetSearch,
    results,
    selectMatch,
    selected,
    setDraft,
    setExpanded,
    setLinkType,
    setReason,
    submitLink,
    submitSearch,
    summary: comparisonSummary(query, results.isPending, results.isError, results.data?.items),
  };
}

export type RelatedRecordPanelController = ReturnType<typeof useRelatedRecordPanel>;
