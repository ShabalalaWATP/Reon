import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type Dispatch, type SetStateAction, useMemo, useState } from "react";
import { useSearchParams } from "react-router";

import { ModalDrawer } from "../../components/ModalDrawer";
import { PageState } from "../../components/PageState";
import { boardApi } from "../../lib/api/boardClient";
import type { BoardColumn, BoardFilters, BoardItem } from "../../lib/api/boardTypes";
import { ApiError, api } from "../../lib/api/client";
import { planningEvolutionApi } from "../../lib/api/planningEvolutionClient";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import type { Session } from "../../lib/api/types";
import { useAuth } from "../../lib/auth/AuthProvider";
import { BoardSettings } from "./BoardSettings";
import { BoardSurface } from "./BoardSurface";
import { BoardToolbar } from "./BoardToolbar";
import {
  activeBoardColumns,
  archiveBoardColumns,
  boardPresetFilters,
  exceptionBoardColumns,
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
  const [cursors, setCursors] = useState<Array<string | null>>([null]);
  const [mode, setMode] = useState<"board" | "table">("board");
  const [viewName, setViewName] = useState("");
  const [selected, setSelected] = useState<BoardItem | null>(null);
  const [creating, setCreating] = useState(false);
  const [settings, setSettings] = useState(false);
  const [showExceptions, setShowExceptions] = useState(false);
  const [showArchive, setShowArchive] = useState(false);
  const cursor = cursors.at(-1) ?? null;
  const effectiveFilters = useMemo(() => ({
    ...filters,
    columns: filters.columns.length || mode === "table"
      ? filters.columns
      : [
        ...activeBoardColumns,
        ...(showExceptions ? exceptionBoardColumns : []),
        ...(showArchive ? archiveBoardColumns : []),
      ],
  }), [filters, mode, showArchive, showExceptions]);
  const queryKey = protectedQueryKeys.teamBoard(userId, access.teamId, JSON.stringify({ filters: effectiveFilters, cursor }));
  const board = useQuery({ queryKey, queryFn: () => boardApi.board(access.teamId, effectiveFilters, { cursor, limit: 100 }) });
  const people = useQuery({ queryKey: protectedQueryKeys.teamPeople(userId, access.teamId), queryFn: () => api.teamPeople(access.teamId) });
  const iterations = useQuery({ queryKey: protectedQueryKeys.teamIterations(userId, access.teamId), queryFn: () => boardApi.iterations(access.teamId) });
  const packages = useQuery({ queryKey: protectedQueryKeys.teamPackages(userId, access.teamId), queryFn: () => boardApi.packages(access.teamId) });
  const planning = useQuery({
    queryKey: protectedQueryKeys.teamPlanningCockpit(userId, access.teamId),
    queryFn: () => planningEvolutionApi.cockpit(access.teamId),
    enabled: Boolean(access.views?.includes("PLANNING")),
  });
  const refresh = () => Promise.all([
    client.invalidateQueries({ queryKey: ["protected", userId, "team-board", access.teamId] }),
    client.invalidateQueries({ queryKey: protectedQueryKeys.teamPackages(userId, access.teamId) }),
    client.invalidateQueries({ queryKey: protectedQueryKeys.teamPlanningCockpit(userId, access.teamId) }),
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
      if (!access.grantId || !board.data) throw new Error("Board management authority is required.");
      return boardApi.configure(access.teamId, { grantId: access.grantId, expectedVersion: board.data.configurationVersion, wipLimits: limits }, session.csrfToken);
    },
    onSuccess: () => { setSettings(false); void refresh(); },
  });
  const changeFilters = (next: BoardFilters) => { setFilters(next); setCursors([null]); };
  const toggleExceptions = () => { setShowExceptions((value) => !value); setCursors([null]); };
  const toggleArchive = () => { setShowArchive((value) => !value); setCursors([null]); };
  if (board.isPending || people.isPending || iterations.isPending || packages.isPending) return <PageState kind="loading" title="Loading team delivery" />;
  if (board.isError || people.isError || iterations.isError || packages.isError) return <PageState action={<button className="button" onClick={() => void Promise.all([board.refetch(), people.refetch(), iterations.refetch(), packages.refetch()])}>Try again</button>} kind="error" title="Team delivery could not be loaded">Board, roster, package and iteration data must be available before planning changes can be made.</PageState>;
  const mutationError = save.error ?? remove.error ?? move.error;
  const canManage = Boolean(access.grantId && access.permissions.includes("BOARD"));
  return (
    <div className="board-page page-stack">
      <BoardToolbar
        canManage={canManage}
        filters={filters}
        mode={mode}
        onChange={changeFilters}
        onDeleteView={(view) => remove.mutate(view)}
        onModeChange={(value) => { setMode(value); setCursors([null]); }}
        onNewPackage={() => setCreating(true)}
        onOpenSettings={() => setSettings(true)}
        onSaveView={() => save.mutate()}
        onViewNameChange={setViewName}
        people={people.data.items}
        savedViews={board.data.savedViews}
        saving={save.isPending}
        userId={userId}
        viewName={viewName}
      />
      {mutationError ? <p className="form-banner form-banner--error" role="alert">{errorMessage(mutationError)}</p> : null}
      {planning.isError ? <p className="form-banner" role="status">Planning context is temporarily unavailable. Core board records remain current.</p> : null}
      <BoardSurface
        columnCounts={board.data.columnCounts}
        context={{ packages: packages.data.items, planning: planning.data }}
        filteredColumns={filters.columns}
        items={board.data.items}
        mode={mode}
        onInspect={setSelected}
        onShowArchive={toggleArchive}
        onShowExceptions={toggleExceptions}
        showArchive={showArchive}
        showExceptions={showExceptions}
        totalCount={board.data.totalCount}
        wipLimits={board.data.wipLimits}
      />
      <BoardPagination cursors={cursors} nextCursor={board.data.nextCursor} onChange={setCursors} />
      {board.data.totalCount === 0 ? <PageState kind="empty" title="No work matches this view">Clear or change the current filters.</PageState> : null}
      <ModalDrawer label="Create work package" onClose={() => setCreating(false)} open={creating}>
        <WorkPackageForm access={access} iterations={iterations.data.items} members={people.data.items} onCreated={() => { setCreating(false); void refresh(); }} session={session} />
      </ModalDrawer>
      <ModalDrawer label="Board settings" onClose={() => setSettings(false)} open={settings}>
        <BoardSettings current={board.data.wipLimits} error={configure.error} onSave={(limits) => configure.mutate(limits)} pending={configure.isPending} />
      </ModalDrawer>
      <WorkItemInspector item={selected} moving={move.isPending} onClose={() => setSelected(null)} onMove={(item, target, reason) => move.mutate({ item, target, reason })} packages={packages.data.items} planning={planning.data} teamId={access.teamId} userId={userId} />
    </div>
  );
}

function BoardPagination({ cursors, nextCursor, onChange }: { cursors: Array<string | null>; nextCursor: string | null; onChange: Dispatch<SetStateAction<Array<string | null>>> }) {
  if (cursors.length === 1 && !nextCursor) return null;
  return <nav aria-label="Board pages" className="board-pages"><button className="button button--quiet" disabled={cursors.length === 1} onClick={() => onChange((value) => value.slice(0, -1))} type="button">Previous page</button><span>Page {cursors.length}</span><button className="button button--quiet" disabled={!nextCursor} onClick={() => nextCursor && onChange((value) => [...value, nextCursor])} type="button">Next page</button></nav>;
}

function errorMessage(error: Error | null) {
  return error instanceof ApiError ? error.message : error?.message ?? "The board change could not be saved.";
}
