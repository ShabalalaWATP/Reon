import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { PageState } from "../../components/PageState";
import { actionNotificationApi } from "../../lib/api/actionNotificationClient";
import type { ActionColumn, ActionFilters, SavedActionView } from "../../lib/api/actionNotificationTypes";
import { ApiError } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import { useAuth } from "../../lib/auth/AuthProvider";
import { roleLabels } from "../../lib/routes";
import { ActionRegister } from "./ActionRegister";
import { SavedViewControls } from "./SavedViewControls";
import { actionColumns, actionSections, actionTypeLabel, columnLabels, freshnessMessage, humaniseCode, sectionCountKeys, sectionLabels } from "./myWorkModel";

const allFilters: ActionFilters = { sections: [], actionTypes: [], dueBefore: null };

export function MyWorkPage() {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState<ActionFilters>(allFilters);
  const [columns, setColumns] = useState<ActionColumn[]>(actionColumns);
  const [selectedView, setSelectedView] = useState("");
  const userId = session!.user.id;
  const filtersKey = JSON.stringify(filters);
  const query = useInfiniteQuery({
    queryKey: protectedQueryKeys.actions(userId, filtersKey),
    queryFn: ({ pageParam }) => actionNotificationApi.actions({ ...filters, cursor: pageParam ?? undefined }),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.nextCursor,
    refetchInterval: 30_000,
  });
  const createView = useMutation({ mutationFn: (name: string) => actionNotificationApi.createActionView({ name, filters, visibleColumns: columns }, session!.csrfToken), onSuccess: () => void invalidate() });
  const updateView = useMutation({ mutationFn: (view: SavedActionView) => actionNotificationApi.updateActionView(view.id, { name: view.name, filters, visibleColumns: columns, expectedVersion: view.version }, session!.csrfToken), onSuccess: () => void invalidate() });
  const deleteView = useMutation({ mutationFn: (view: SavedActionView) => actionNotificationApi.deleteActionView(view.id, view.version, session!.csrfToken), onSuccess: () => { setSelectedView(""); void invalidate(); } });
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["protected", userId, "my-actions"] });
  if (query.isPending) return <PageState kind="loading" title="Loading your work" />;
  if (query.isError) return <WorkspaceError error={query.error} retry={() => void query.refetch()} />;
  const first = query.data.pages[0];
  const items = query.data.pages.flatMap((page) => page.items);
  const actionTypes = [...new Set([...items.map((item) => item.actionType), ...filters.actionTypes])].sort();
  const mutationError = createView.error ?? updateView.error ?? deleteView.error;
  const applyView = (view: SavedActionView) => { setFilters(view.filters); setColumns(view.visibleColumns); };
  const countAnnouncement = Object.values(first.counts).reduce((sum, value) => sum + value, 0);
  const awaitingInitialCheckpoint = countAnnouncement === 0
    && first.freshness.status === "DEGRADED"
    && first.freshness.projectedAt === null
    && first.freshness.sourceChangedAt === null;
  const freshness = awaitingInitialCheckpoint
    ? "No action update checkpoint has been recorded yet. This view will keep checking for changes."
    : freshnessMessage(first.freshness);
  return <main className="page-stack my-work-page">
    <header className="page-heading"><div><span>{roleLabels[session!.user.role]}</span><h1>My actions</h1><p>Work assigned to you, actions available to your unit and recent authorised progress.</p></div><Link className="button button--quiet" to="/notifications">Notifications</Link></header>
    <p className="sr-only" aria-live="polite">{countAnnouncement} work items across all sections.</p>
    <div className="work-counts" aria-label="Work counts" role="group">{actionSections.map((section) => <button className={filters.sections[0] === section ? "work-count work-count--active" : "work-count"} key={section} onClick={() => setFilters((current) => ({ ...current, sections: current.sections[0] === section ? [] : [section] }))} type="button"><span>{sectionLabels[section]}</span><strong>{first.counts[sectionCountKeys[section]]}</strong></button>)}</div>
    {freshness ? <p className="freshness-banner" role="status"><strong>{awaitingInitialCheckpoint ? "Starting" : first.freshness.pendingCount ? "Updating" : humaniseCode(first.freshness.status)}</strong> {freshness}</p> : null}
    <section className="work-tools" aria-label="Work view controls">
      <SavedViewControls columns={columns} filters={filters} onApply={applyView} onCreate={(name) => createView.mutate(name)} onDelete={(view) => deleteView.mutate(view)} onUpdate={(view) => updateView.mutate(view)} pending={createView.isPending || updateView.isPending || deleteView.isPending} selectedId={selectedView} setSelectedId={setSelectedView} views={first.savedViews} />
      <div className="work-filters"><label className="form-field"><span>Action type</span><select onChange={(event) => setFilters((current) => ({ ...current, actionTypes: event.target.value ? [event.target.value] : [] }))} value={filters.actionTypes[0] ?? ""}><option value="">All action types</option>{actionTypes.map((type) => <option key={type} value={type}>{actionTypeLabel(type)}</option>)}</select></label><label className="form-field"><span>Due before</span><input onChange={(event) => setFilters((current) => ({ ...current, dueBefore: event.target.value || null }))} type="date" value={filters.dueBefore ?? ""} /></label><fieldset className="column-picker"><legend>Visible columns</legend>{actionColumns.map((column) => <label key={column}><input checked={columns.includes(column)} disabled={columns.length === 1 && columns[0] === column} onChange={() => setColumns((current) => current.includes(column) ? current.filter((value) => value !== column) : [...current, column])} type="checkbox" />{columnLabels[column]}</label>)}</fieldset></div>
    </section>
    {mutationError ? <p className="form-banner form-banner--error" role="alert">{mutationError instanceof ApiError ? mutationError.message : "The saved view could not be changed."}</p> : null}
    {items.length === 0 ? <PageState kind="empty" title="No work in this view">Choose another section or saved view to broaden the result.</PageState> : actionSections.filter((section) => filters.sections.length === 0 || filters.sections.includes(section)).map((section) => { const grouped = items.filter((item) => item.section === section); return grouped.length ? <section className="work-section" key={section} aria-labelledby={`work-${section}`}><div className="section-heading"><span>{grouped.length} item{grouped.length === 1 ? "" : "s"}</span><h2 id={`work-${section}`}>{sectionLabels[section]}</h2></div><ActionRegister columns={columns} items={grouped} label={`${sectionLabels[section]} action register`} /></section> : null; })}
    {query.hasNextPage ? <button className="button work-load-more" disabled={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()} type="button">{query.isFetchingNextPage ? "Loading…" : "Load more"}</button> : null}
  </main>;
}

function WorkspaceError({ error, retry }: { error: Error; retry: () => void }) {
  const denied = error instanceof ApiError && error.status === 403;
  const conflict = error instanceof ApiError && error.status === 409;
  return <PageState action={denied ? undefined : <button className="button" onClick={retry}>Refresh</button>} kind="error" title={denied ? "Your access has changed" : conflict ? "This work view changed" : "Your work could not be loaded"}>{denied ? "Return to your home page or ask an Administrator to review your access." : conflict ? "Refresh to use the latest work state." : "Check your connection and try again."}</PageState>;
}
