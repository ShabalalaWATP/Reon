import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type Dispatch, type SetStateAction, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router";

import { ModalDrawer } from "../../components/ModalDrawer";
import { PageState } from "../../components/PageState";
import { boardApi } from "../../lib/api/boardClient";
import type { BoardColumn, BoardFilters, BoardItem } from "../../lib/api/boardTypes";
import { ApiError, api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import type { Session } from "../../lib/api/types";
import { useAuth } from "../../lib/auth/AuthProvider";
import { BoardSettings } from "./BoardSettings";
import { BoardSurface } from "./BoardSurface";
import { BoardToolbar } from "./BoardToolbar";
import {
  archiveBoardColumns,
  boardPresetFilters,
  serviceRequestBoardColumns,
  serviceRequestColumnMeanings,
  serviceRequestExceptionColumns,
  workPackageBoardColumns,
} from "./boardPresentation";
import { WorkItemInspector } from "./WorkItemInspector";
import { WorkPackageForm } from "./WorkPackageForm";

export function TeamBoardPage({ access }: { access: TeamWorkspaceAccess }) {
  const { session } = useAuth();
  if (!session) return <PageState kind="error" title="Sign in is required" />;
  return <AuthenticatedTeamBoard access={access} session={session} />;
}

function AuthenticatedTeamBoard({ access, session }: { access: TeamWorkspaceAccess; session: Session }) {
  const userId = session.user.id;
  const client = useQueryClient();
  const [searchParams] = useSearchParams();
  const [filters, setFilters] = useState<BoardFilters>(() => boardPresetFilters(searchParams.get("preset"), userId));
  const [requestCursors, setRequestCursors] = useState<Array<string | null>>([null]);
  const [packageCursors, setPackageCursors] = useState<Array<string | null>>([null]);
  const [mode, setMode] = useState<"board" | "table">("board");
  const [viewName, setViewName] = useState("");
  const [selected, setSelected] = useState<BoardItem | null>(null);
  const [creating, setCreating] = useState(false);
  const [settings, setSettings] = useState(false);
  const [handledDeepLink, setHandledDeepLink] = useState<string | null>(null);
  const [showExceptions, setShowExceptions] = useState(false);
  const [showRequestArchive, setShowRequestArchive] = useState(false);
  const [showPackageArchive, setShowPackageArchive] = useState(false);
  const [packagesOpen, setPackagesOpen] = useState(false);
  const requestCursor = requestCursors.at(-1) ?? null;
  const packageCursor = packageCursors.at(-1) ?? null;
  const deepLinkedItemId = searchParams.get("itemId");
  const requestFilters = useMemo(() => ({
    ...filters,
    itemTypes: ["SERVICE_REQUEST" as const],
    columns: filters.columns.length || mode === "table"
      ? filters.columns
      : [
        ...serviceRequestBoardColumns,
        ...(showExceptions ? serviceRequestExceptionColumns : []),
        ...(showRequestArchive ? archiveBoardColumns : []),
      ],
  }), [filters, mode, showExceptions, showRequestArchive]);
  const packageFilters = useMemo(() => ({
    ...filters,
    itemTypes: ["WORK_PACKAGE" as const],
    columns: filters.columns.length || mode === "table"
      ? filters.columns
      : [...workPackageBoardColumns, ...(showPackageArchive ? archiveBoardColumns : [])],
  }), [filters, mode, showPackageArchive]);
  const requestQueryKey = protectedQueryKeys.teamBoard(userId, access.teamId, JSON.stringify({ filters: requestFilters, cursor: requestCursor }));
  const packageQueryKey = protectedQueryKeys.teamBoard(userId, access.teamId, JSON.stringify({ filters: packageFilters, cursor: packageCursor }));
  const requestBoard = useQuery({ queryKey: requestQueryKey, queryFn: () => boardApi.board(access.teamId, requestFilters, { cursor: requestCursor, limit: 100 }) });
  const packageBoard = useQuery({ enabled: packagesOpen, queryKey: packageQueryKey, queryFn: () => boardApi.board(access.teamId, packageFilters, { cursor: packageCursor, limit: 100 }) });
  const people = useQuery({ queryKey: protectedQueryKeys.teamPeople(userId, access.teamId), queryFn: () => api.teamPeople(access.teamId) });
  const iterations = useQuery({ queryKey: protectedQueryKeys.teamIterations(userId, access.teamId), queryFn: () => boardApi.iterations(access.teamId) });
  const packages = useQuery({ queryKey: protectedQueryKeys.teamPackages(userId, access.teamId), queryFn: () => boardApi.packages(access.teamId) });
  const deepLinkedRequest = useQuery({
    queryKey: protectedQueryKeys.teamBoardRequest(
      userId,
      access.teamId,
      deepLinkedItemId,
    ),
    queryFn: () => boardApi.boardRequest(access.teamId, deepLinkedItemId!),
    enabled: Boolean(deepLinkedItemId),
  });
  useEffect(() => {
    if (
      !deepLinkedItemId
      || handledDeepLink === deepLinkedItemId
      || !deepLinkedRequest.data
    ) return;
    setSelected(deepLinkedRequest.data);
    setHandledDeepLink(deepLinkedItemId);
  }, [deepLinkedItemId, deepLinkedRequest.data, handledDeepLink]);
  const refresh = () => Promise.all([
    client.invalidateQueries({ queryKey: ["protected", userId, "team-board", access.teamId] }),
    client.invalidateQueries({ queryKey: protectedQueryKeys.teamPackages(userId, access.teamId) }),
  ]);
  const move = useMutation({
    mutationFn: ({ item, reason, target }: { item: BoardItem; reason: string; target: BoardColumn }) => boardApi.moveItem(access.teamId, {
      grantId: access.grantId,
      itemType: item.itemType,
      itemId: item.id,
      target,
      expectedVersion: item.version,
      reason,
    }, session.csrfToken),
    onSuccess: () => { setSelected(null); void refresh(); },
  });
  const save = useMutation({
    mutationFn: () => boardApi.createView(access.teamId, { name: viewName, filters }, session.csrfToken),
    onSuccess: () => { setViewName(""); void refresh(); },
  });
  const remove = useMutation({
    mutationFn: ({ id, version }: { id: string; version: number }) => boardApi.deleteView(access.teamId, id, version, session.csrfToken),
    onSuccess: refresh,
  });
  const configure = useMutation({
    mutationFn: (limits: Record<string, number>) => {
      if (!access.grantId || !requestBoard.data) throw new Error("Board management authority is required.");
      return boardApi.configure(access.teamId, { grantId: access.grantId, expectedVersion: requestBoard.data.configurationVersion, wipLimits: limits }, session.csrfToken);
    },
    onSuccess: () => { setSettings(false); void refresh(); },
  });
  const changeFilters = (next: BoardFilters) => {
    setFilters(next);
    setRequestCursors([null]);
    setPackageCursors([null]);
    if (next.itemTypes.length === 1 && next.itemTypes[0] === "WORK_PACKAGE") setPackagesOpen(true);
  };
  const toggleExceptions = () => { setShowExceptions((value) => !value); setRequestCursors([null]); };
  const toggleRequestArchive = () => { setShowRequestArchive((value) => !value); setRequestCursors([null]); };
  const togglePackageArchive = () => { setShowPackageArchive((value) => !value); setPackageCursors([null]); };
  if (requestBoard.isPending || people.isPending || iterations.isPending || packages.isPending) return <PageState kind="loading" title="Loading team delivery" />;
  if (requestBoard.isError || people.isError || iterations.isError || packages.isError) return <PageState action={<button className="button" onClick={() => void Promise.all([requestBoard.refetch(), people.refetch(), iterations.refetch(), packages.refetch()])}>Try again</button>} kind="error" title="Team delivery could not be loaded">Board, roster, package and iteration data must be available before planning changes can be made.</PageState>;
  const mutationError = save.error ?? remove.error ?? move.error;
  const canManage = Boolean(access.grantId && access.permissions.includes("BOARD"));
  const showRequests = filters.itemTypes.length === 0 || filters.itemTypes.includes("SERVICE_REQUEST");
  const showPackages = filters.itemTypes.length === 0 || filters.itemTypes.includes("WORK_PACKAGE");
  return (
    <div className="board-page page-stack">
      {deepLinkedRequest.isError ? (
        <p className="form-banner form-banner--error" role="alert">
          The linked request could not be opened. It may no longer be available
          to this team.
        </p>
      ) : null}
      <BoardToolbar
        canManage={canManage}
        filters={filters}
        mode={mode}
        onChange={changeFilters}
        onDeleteView={(view) => remove.mutate(view)}
        onModeChange={(value) => { setMode(value); setRequestCursors([null]); setPackageCursors([null]); }}
        onOpenSettings={() => setSettings(true)}
        onSaveView={() => save.mutate()}
        onViewNameChange={setViewName}
        people={people.data.items}
        savedViews={requestBoard.data.savedViews}
        saving={save.isPending}
        userId={userId}
        viewName={viewName}
      />
      {mutationError ? <p className="form-banner form-banner--error" role="alert">{errorMessage(mutationError)}</p> : null}
      {showRequests ? <section aria-labelledby="service-request-board-title" className="board-workstream">
        <header className="board-workstream__header">
          <span>Customer workflow</span>
          <h2 id="service-request-board-title">Service request board</h2>
          <p>Requests move through these stages when Analysts, Managers and QC complete their named workflow actions.</p>
        </header>
        <BoardSurface
          activeColumns={serviceRequestBoardColumns}
          ariaLabel="Service request workflow board"
          archiveColumns={archiveBoardColumns}
          columnCounts={requestBoard.data.columnCounts}
          columnDescriptions={serviceRequestColumnMeanings}
          columnFilterActive={filters.columns.length > 0}
          context={{}}
          exceptionColumns={serviceRequestExceptionColumns}
          filteredColumns={filters.columns.filter((column) => [...serviceRequestBoardColumns, ...serviceRequestExceptionColumns, ...archiveBoardColumns].includes(column))}
          items={requestBoard.data.items.filter((item) => item.itemType === "SERVICE_REQUEST")}
          mode={mode}
          onInspect={setSelected}
          onShowArchive={toggleRequestArchive}
          onShowExceptions={toggleExceptions}
          resultNote="Service requests cannot be dragged. Their stage changes through assignment, Analyst submission, Manager review, QC and dissemination."
          showArchive={showRequestArchive}
          showExceptions={showExceptions}
          totalCount={requestBoard.data.totalCount}
          wipLimits={requestBoard.data.wipLimits}
        />
        <BoardPagination ariaLabel="Service request pages" cursors={requestCursors} nextCursor={requestBoard.data.nextCursor} onChange={setRequestCursors} />
        {requestBoard.data.totalCount === 0 ? <PageState kind="empty" title="No service requests match this view">Clear or change the current filters.</PageState> : null}
      </section> : null}
      {showPackages ? <details className="board-workstream board-workstream--packages" onToggle={(event) => setPackagesOpen(event.currentTarget.open)} open={packagesOpen}>
        <summary>
          <span className="board-workstream__chevron" aria-hidden="true">›</span>
          <span className="board-workstream__summary-copy"><small>Analyst team planning</small><strong>Work package Kanban</strong><span>Expand to create and move internal team cards.</span></span>
          <span className="board-workstream__summary-action">{packagesOpen ? "Collapse" : "Expand"}</span>
        </summary>
        <div className="board-workstream__body">
          <header className="board-workstream__actions">
            <div><strong>Internal team cards</strong><span>Create scratch tasks, assign contributors and move the work without changing the Customer request.</span></div>
            <button className="button button--primary" onClick={() => setCreating(true)} type="button">Create internal card</button>
          </header>
          {packageBoard.isPending ? <PageState kind="loading" title="Loading work package Kanban" /> : null}
          {packageBoard.isError ? <PageState action={<button className="button" onClick={() => void packageBoard.refetch()}>Try again</button>} kind="error" title="Work package Kanban could not be loaded" /> : null}
          {packageBoard.data ? <>
            <BoardSurface
              activeColumns={workPackageBoardColumns}
              ariaLabel="Work package Kanban"
              archiveColumns={archiveBoardColumns}
              columnCounts={packageBoard.data.columnCounts}
              columnFilterActive={filters.columns.length > 0}
              context={{ packages: packages.data.items }}
              exceptionColumns={[]}
              filteredColumns={filters.columns.filter((column) => [...workPackageBoardColumns, ...archiveBoardColumns].includes(column))}
              items={packageBoard.data.items.filter((item) => item.itemType === "WORK_PACKAGE")}
              mode={mode}
              moving={move.isPending}
              onInspect={setSelected}
              onMove={(item, target, reason) => move.mutateAsync({ item, target, reason }).then(() => undefined)}
              onShowArchive={togglePackageArchive}
              onShowExceptions={() => undefined}
              resultNote="Drag a work-package card to move it. Each manual move requires a reason and is recorded in its activity history."
              showArchive={showPackageArchive}
              showExceptions={false}
              totalCount={packageBoard.data.totalCount}
              wipLimits={packageBoard.data.wipLimits}
            />
            <BoardPagination ariaLabel="Work package pages" cursors={packageCursors} nextCursor={packageBoard.data.nextCursor} onChange={setPackageCursors} />
            {packageBoard.data.totalCount === 0 ? <PageState kind="empty" title="No work packages match this view">Clear or change the current filters.</PageState> : null}
          </> : null}
        </div>
      </details> : null}
      <ModalDrawer label="Create internal card" onClose={() => setCreating(false)} open={creating}>
        <WorkPackageForm access={access} iterations={iterations.data.items} members={people.data.items} onCreated={() => { setCreating(false); void refresh(); }} session={session} />
      </ModalDrawer>
      <ModalDrawer label="Board settings" onClose={() => setSettings(false)} open={settings}>
        <BoardSettings current={requestBoard.data.wipLimits} error={configure.error} onSave={(limits) => configure.mutate(limits)} pending={configure.isPending} />
      </ModalDrawer>
      <WorkItemInspector access={access} item={selected} moving={move.isPending} onClose={() => setSelected(null)} onMove={(item, target, reason) => move.mutate({ item, target, reason })} packages={packages.data.items} session={session} userId={userId} />
    </div>
  );
}

function BoardPagination({ ariaLabel, cursors, nextCursor, onChange }: { ariaLabel: string; cursors: Array<string | null>; nextCursor: string | null; onChange: Dispatch<SetStateAction<Array<string | null>>> }) {
  if (cursors.length === 1 && !nextCursor) return null;
  return <nav aria-label={ariaLabel} className="board-pages"><button className="button button--quiet" disabled={cursors.length === 1} onClick={() => onChange((value) => value.slice(0, -1))} type="button">Previous page</button><span>Page {cursors.length}</span><button className="button button--quiet" disabled={!nextCursor} onClick={() => nextCursor && onChange((value) => [...value, nextCursor])} type="button">Next page</button></nav>;
}

function errorMessage(error: Error | null) {
  return error instanceof ApiError ? error.message : error?.message ?? "The board change could not be saved.";
}
