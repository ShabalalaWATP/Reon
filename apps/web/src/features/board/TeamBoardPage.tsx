import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { PageState } from "../../components/PageState";
import { boardApi } from "../../lib/api/boardClient";
import type { BoardColumn, BoardFilters, BoardItem, BoardItemType } from "../../lib/api/boardTypes";
import { ApiError, api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import type { Session } from "../../lib/api/types";
import { useAuth } from "../../lib/auth/AuthProvider";
import { WorkPackageForm } from "./WorkPackageForm";

const emptyFilters: BoardFilters = { search: "", columns: [], priorities: [], ownerUserId: null, itemTypes: [], dueBefore: null };
const columns = ["AWAITING_ASSIGNMENT", "BACKLOG", "READY", "IN_PROGRESS", "BLOCKED", "MANAGER_REVIEW", "QUALITY_REVIEW", "REWORK", "ON_HOLD", "COMPLETED", "CANCELLED"] as const;

export function TeamBoardPage({ access }: { access: TeamWorkspaceAccess }) {
  const { session } = useAuth();
  if (!session) return <PageState kind="error" title="Sign in is required" />;
  return <AuthenticatedTeamBoard access={access} session={session} />;
}

function AuthenticatedTeamBoard({ access, session }: { access: TeamWorkspaceAccess; session: Session }) {
  const userId = session.user.id;
  const client = useQueryClient();
  const [filters, setFilters] = useState<BoardFilters>(emptyFilters);
  const [cursors, setCursors] = useState<Array<string | null>>([null]);
  const [mode, setMode] = useState<"board" | "table">("board");
  const [viewName, setViewName] = useState("");
  const cursor = cursors.at(-1) ?? null;
  const queryKey = protectedQueryKeys.teamBoard(userId, access.teamId, JSON.stringify({ filters, cursor }));
  const board = useQuery({ queryKey, queryFn: () => boardApi.board(access.teamId, filters, { cursor, limit: 25 }) });
  const people = useQuery({ queryKey: protectedQueryKeys.teamPeople(userId, access.teamId), queryFn: () => api.teamPeople(access.teamId) });
  const iterations = useQuery({ queryKey: protectedQueryKeys.teamIterations(userId, access.teamId), queryFn: () => boardApi.iterations(access.teamId) });
  const refresh = () => Promise.all([
    client.invalidateQueries({ queryKey: ["protected", userId, "team-board", access.teamId] }),
    client.invalidateQueries({ queryKey: protectedQueryKeys.teamPackages(userId, access.teamId) }),
  ]);
  const move = useMutation({
    mutationFn: ({ item, target }: { item: BoardItem; target: BoardItem["column"] }) => {
      return boardApi.moveItem(access.teamId, { grantId: access.grantId, itemType: item.itemType, itemId: item.id, target, expectedVersion: item.version, reason: "The team deliberately moved this package in its delivery plan." }, session.csrfToken);
    },
    onSuccess: refresh,
  });
  const save = useMutation({
    mutationFn: () => {
      return boardApi.createView(access.teamId, { name: viewName, filters }, session.csrfToken);
    },
    onSuccess: () => { setViewName(""); void refresh(); },
  });
  const remove = useMutation({
    mutationFn: ({ id, version }: { id: string; version: number }) => {
      return boardApi.deleteView(access.teamId, id, version, session.csrfToken);
    },
    onSuccess: refresh,
  });
  const configure = useMutation({
    mutationFn: (limits: Record<string, number>) => {
      if (!access.grantId || !board.data) throw new Error("Board management authority is required.");
      return boardApi.configure(access.teamId, { grantId: access.grantId, expectedVersion: board.data.configurationVersion, wipLimits: limits }, session.csrfToken);
    },
    onSuccess: refresh,
  });
  const changeFilters = (next: BoardFilters) => { setFilters(next); setCursors([null]); };
  if (board.isPending) return <PageState kind="loading" title="Loading workflow board" />;
  if (board.isError) return <PageState action={<button className="button" onClick={() => void board.refetch()}>Try again</button>} kind="error" title="Workflow board could not be loaded" />;
  return (
    <div className="board-page page-stack">
      <section className="board-toolbar" aria-label="Board controls">
        <header><span>Camunda-derived service work</span><h2>Workflow board</h2><p>Request cards are read-only projections. Only named workflow actions can move them. Team package moves are explicit and audited.</p></header>
        <div className="board-filter-grid">
          <label className="form-field">Search<input onChange={(event) => changeFilters({ ...filters, search: event.target.value })} placeholder="Reference or title" value={filters.search} /></label>
          <label className="form-field">Item type<select onChange={(event) => changeFilters({ ...filters, itemTypes: event.target.value ? [event.target.value as BoardItemType] : [] })} value={filters.itemTypes[0] ?? ""}><option value="">All items</option><option value="SERVICE_REQUEST">Service requests</option><option value="WORK_PACKAGE">Work packages</option></select></label>
          <label className="form-field">Status<select onChange={(event) => changeFilters({ ...filters, columns: event.target.value ? [event.target.value as BoardColumn] : [] })} value={filters.columns[0] ?? ""}><option value="">All statuses</option>{columns.map((column) => <option key={column} value={column}>{label(column)}</option>)}</select></label>
          <label className="form-field">Priority<select onChange={(event) => changeFilters({ ...filters, priorities: event.target.value ? [event.target.value] : [] })} value={filters.priorities[0] ?? ""}><option value="">All priorities</option>{["LOW", "MEDIUM", "HIGH", "URGENT"].map((priority) => <option key={priority}>{priority}</option>)}</select></label>
          <label className="form-field">Owner<select onChange={(event) => changeFilters({ ...filters, ownerUserId: event.target.value || null })} value={filters.ownerUserId ?? ""}><option value="">All owners</option>{people.data?.items.filter((item) => item.state === "CURRENT").map((item) => <option key={item.accountId} value={item.accountId}>{item.displayName}</option>)}</select></label>
          <label className="form-field">Due by<input onChange={(event) => changeFilters({ ...filters, dueBefore: event.target.value || null })} type="date" value={filters.dueBefore ?? ""} /></label>
          <div className="board-mode" aria-label="Board presentation"><button aria-pressed={mode === "board"} onClick={() => setMode("board")} type="button">Board</button><button aria-pressed={mode === "table"} onClick={() => setMode("table")} type="button">Table</button></div>
        </div>
        <div className="saved-view-row">
          <label className="form-field">Saved view name<input minLength={3} onChange={(event) => setViewName(event.target.value)} value={viewName} /></label>
          <button className="button" disabled={viewName.length < 3 || save.isPending} onClick={() => save.mutate()} type="button">Save current view</button>
          {board.data.savedViews.map((view) => <span className="saved-view" key={view.id}><button onClick={() => changeFilters(view.filters)} type="button">{view.name}</button><button aria-label={`Delete ${view.name}`} onClick={() => remove.mutate(view)} type="button">×</button></span>)}
        </div>
        {save.isError || remove.isError || move.isError ? <p role="alert">{errorMessage(save.error ?? remove.error ?? move.error)}</p> : null}
      </section>
      {mode === "board" ? <BoardColumns items={board.data.items} moving={move.isPending} onMove={(item, target) => move.mutate({ item, target })} /> : <BoardTable items={board.data.items} />}
      <nav aria-label="Board pages" className="board-pages"><button className="button button--quiet" disabled={cursors.length === 1} onClick={() => setCursors((value) => value.slice(0, -1))} type="button">Previous page</button><span>Page {cursors.length}</span><button className="button button--quiet" disabled={!board.data.nextCursor} onClick={() => board.data.nextCursor && setCursors((value) => [...value, board.data.nextCursor])} type="button">Next page</button></nav>
      {board.data.items.length === 0 ? <PageState kind="empty" title="No board items match">Clear or change the current filters.</PageState> : null}
      {access.grantId && access.permissions.includes("BOARD") ? <WipForm current={board.data.wipLimits} error={configure.error} pending={configure.isPending} onSave={(limits) => configure.mutate(limits)} /> : null}
      <WorkPackageForm access={access} iterations={iterations.data?.items ?? []} members={people.data?.items ?? []} onCreated={() => { void refresh(); }} session={session} />
    </div>
  );
}

function BoardColumns({ items, moving, onMove }: { items: BoardItem[]; moving: boolean; onMove: (item: BoardItem, target: BoardItem["column"]) => void }) {
  return <section className="kanban" aria-label="Team Kanban board">{columns.map((column) => { const cards = items.filter((item) => item.column === column); return <section className="kanban-column" key={column}><header><h3>{label(column)}</h3><span>{cards.length}</span></header>{cards.map((item) => <BoardCard item={item} key={`${item.itemType}-${item.id}`} moving={moving} onMove={onMove} />)}</section>; })}</section>;
}

function BoardCard({ item, moving, onMove }: { item: BoardItem; moving: boolean; onMove: (item: BoardItem, target: BoardItem["column"]) => void }) {
  return <article className="board-card"><span>{item.itemType === "SERVICE_REQUEST" ? "Service request" : "Work package"}</span><h4>{item.title}</h4><p>{item.reference} · {item.priority}</p><dl><div><dt>Owner</dt><dd>{item.ownerDisplayName ?? "Unassigned"}</dd></div><div><dt>Due</dt><dd>{item.dueOn}</dd></div></dl>{item.linkedRequestId ? <Link to={`/requests/${item.linkedRequestId}`}>Open request</Link> : null}{item.availableColumns.length ? <div className="card-actions" aria-label={`Move ${item.title}`}>{item.availableColumns.map((target) => <button disabled={moving} key={target} onClick={() => onMove(item, target)} type="button">Move to {label(target)}</button>)}</div> : <small>Use the named workflow action to change status.</small>}</article>;
}

function BoardTable({ items }: { items: BoardItem[] }) {
  return <div className="team-table-wrap"><table className="team-table"><caption>Filtered team work</caption><thead><tr><th>Reference</th><th>Title</th><th>Type</th><th>Status</th><th>Owner</th><th>Due</th></tr></thead><tbody>{items.map((item) => <tr key={`${item.itemType}-${item.id}`}><th>{item.reference}</th><td>{item.title}</td><td>{label(item.itemType)}</td><td>{label(item.column)}</td><td>{item.ownerDisplayName ?? "Unassigned"}</td><td>{item.dueOn}</td></tr>)}</tbody></table></div>;
}

function WipForm({ current, error, onSave, pending }: { current: Record<string, number>; error: Error | null; onSave: (value: Record<string, number>) => void; pending: boolean }) {
  return <section className="wip-panel"><header><span>Flow control</span><h2>Work in progress limits</h2></header><form onSubmit={(event) => { event.preventDefault(); const data = new FormData(event.currentTarget); onSave(Object.fromEntries(["READY", "IN_PROGRESS", "BLOCKED"].map((key) => [key, Number(data.get(key))]))); }}>{["READY", "IN_PROGRESS", "BLOCKED"].map((key) => <label className="form-field" key={key}>{label(key)}<input defaultValue={current[key] ?? 5} max={100} min={1} name={key} required type="number" /></label>)}<button className="button" disabled={pending} type="submit">Save limits</button></form>{error ? <p role="alert">{errorMessage(error)}</p> : null}</section>;
}

function label(value: string) { return value.replaceAll("_", " ").toLowerCase().replace(/(^| )\w/g, (letter) => letter.toUpperCase()); }
function errorMessage(error: Error | null) { return error instanceof ApiError ? error.message : error?.message ?? "The board change could not be saved."; }
