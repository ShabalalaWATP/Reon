import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router";

import { boardApi } from "../../lib/api/boardClient";
import type { BoardColumn, BoardFilters, BoardItem } from "../../lib/api/boardTypes";
import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import type { Session } from "../../lib/api/types";
import {
  archiveBoardColumns,
  boardPresetFilters,
  serviceRequestBoardColumns,
  serviceRequestExceptionColumns,
  workPackageBoardColumns,
} from "./boardPresentation";

export function useTeamBoardController(access: TeamWorkspaceAccess, session: Session) {
  const queryKeys = protectedQueryKeys(session);
  const client = useQueryClient();
  const [searchParams] = useSearchParams();
  const [filters, setFilters] = useState<BoardFilters>(() =>
    boardPresetFilters(searchParams.get("preset"), session.user.id),
  );
  const [requestCursors, setRequestCursors] = useState<Array<string | null>>([null]);
  const [packageCursors, setPackageCursors] = useState<Array<string | null>>([null]);
  const [mode, setMode] = useState<"board" | "table">("board");
  const [viewName, setViewName] = useState("");
  const [selected, setSelected] = useState<BoardItem | null>(null);
  const [creating, setCreating] = useState(false);
  const [settings, setSettings] = useState(false);
  const [showExceptions, setShowExceptions] = useState(false);
  const [showRequestArchive, setShowRequestArchive] = useState(false);
  const [showPackageArchive, setShowPackageArchive] = useState(false);
  const [packagesOpen, setPackagesOpen] = useState(false);
  const [handledDeepLink, setHandledDeepLink] = useState<string | null>(null);
  const requestCursor = requestCursors.at(-1) ?? null;
  const packageCursor = packageCursors.at(-1) ?? null;
  const deepLinkedItemId = searchParams.get("itemId");
  const requestFilters = useMemo(
    () => buildRequestFilters(filters, mode, showExceptions, showRequestArchive),
    [filters, mode, showExceptions, showRequestArchive],
  );
  const packageFilters = useMemo(
    () => buildPackageFilters(filters, mode, showPackageArchive),
    [filters, mode, showPackageArchive],
  );
  const requestBoard = useQuery({
    queryKey: queryKeys.teamBoard(
      access.teamId,
      JSON.stringify({ filters: requestFilters, cursor: requestCursor }),
    ),
    queryFn: () =>
      boardApi.board(access.teamId, requestFilters, { cursor: requestCursor, limit: 100 }),
  });
  const packageBoard = useQuery({
    enabled: packagesOpen,
    queryKey: queryKeys.teamBoard(
      access.teamId,
      JSON.stringify({ filters: packageFilters, cursor: packageCursor }),
    ),
    queryFn: () =>
      boardApi.board(access.teamId, packageFilters, { cursor: packageCursor, limit: 100 }),
  });
  const people = useQuery({
    queryKey: queryKeys.teamPeople(access.teamId),
    queryFn: () => api.teamPeople(access.teamId),
  });
  const iterations = useQuery({
    queryKey: queryKeys.teamIterations(access.teamId),
    queryFn: () => boardApi.iterations(access.teamId),
  });
  const packages = useQuery({
    queryKey: queryKeys.teamPackages(access.teamId),
    queryFn: () => boardApi.packages(access.teamId),
  });
  const deepLinkedRequest = useQuery({
    queryKey: queryKeys.teamBoardRequest(access.teamId, deepLinkedItemId),
    queryFn: () => boardApi.boardRequest(access.teamId, deepLinkedItemId!),
    enabled: Boolean(deepLinkedItemId),
  });
  useDeepLinkedRequest(
    deepLinkedItemId,
    deepLinkedRequest.data,
    handledDeepLink,
    setHandledDeepLink,
    setSelected,
  );

  const refresh = () =>
    Promise.all([
      client.invalidateQueries({ queryKey: queryKeys.teamBoardRoot(access.teamId) }),
      client.invalidateQueries({ queryKey: queryKeys.teamPackages(access.teamId) }),
    ]);
  const move = useMutation({
    mutationFn: ({
      item,
      reason,
      target,
    }: {
      item: BoardItem;
      reason: string;
      target: BoardColumn;
    }) =>
      boardApi.moveItem(
        access.teamId,
        {
          grantId: access.grantId,
          itemType: item.itemType,
          itemId: item.id,
          target,
          expectedVersion: item.version,
          reason,
        },
        session.csrfToken,
      ),
    onSuccess: () => {
      setSelected(null);
      void refresh();
    },
  });
  const save = useMutation({
    mutationFn: () =>
      boardApi.createView(access.teamId, { name: viewName, filters }, session.csrfToken),
    onSuccess: () => {
      setViewName("");
      void refresh();
    },
  });
  const remove = useMutation({
    mutationFn: ({ id, version }: { id: string; version: number }) =>
      boardApi.deleteView(access.teamId, id, version, session.csrfToken),
    onSuccess: refresh,
  });
  const configure = useMutation({
    mutationFn: (limits: Record<string, number>) =>
      configureBoard(access, requestBoard.data?.configurationVersion, limits, session.csrfToken),
    onSuccess: () => {
      setSettings(false);
      void refresh();
    },
  });

  const changeFilters = (next: BoardFilters) => {
    setFilters(next);
    setRequestCursors([null]);
    setPackageCursors([null]);
    if (next.itemTypes.length === 1 && next.itemTypes[0] === "WORK_PACKAGE") setPackagesOpen(true);
  };
  const changeMode = (next: "board" | "table") => {
    setMode(next);
    setRequestCursors([null]);
    setPackageCursors([null]);
  };
  const toggleExceptions = () => resetCursorToggle(setShowExceptions, setRequestCursors);
  const toggleRequestArchive = () => resetCursorToggle(setShowRequestArchive, setRequestCursors);
  const togglePackageArchive = () => resetCursorToggle(setShowPackageArchive, setPackageCursors);
  const retryRequiredData = () =>
    Promise.all([
      requestBoard.refetch(),
      people.refetch(),
      iterations.refetch(),
      packages.refetch(),
    ]);

  return {
    access,
    canManage: Boolean(access.grantId && access.permissions.includes("BOARD")),
    changeFilters,
    changeMode,
    configure,
    creating,
    deepLinkedRequest,
    filters,
    isError: requestBoard.isError || people.isError || iterations.isError || packages.isError,
    isPending:
      requestBoard.isPending || people.isPending || iterations.isPending || packages.isPending,
    iterations,
    mode,
    move,
    packageBoard,
    packageCursors,
    packages,
    packagesOpen,
    people,
    refresh,
    remove,
    requestBoard,
    requestCursors,
    retryRequiredData,
    save,
    selected,
    session,
    setCreating,
    setPackageCursors,
    setPackagesOpen,
    setRequestCursors,
    setSelected,
    setSettings,
    setViewName,
    settings,
    showPackageArchive,
    showPackages: filters.itemTypes.length === 0 || filters.itemTypes.includes("WORK_PACKAGE"),
    showRequestArchive,
    showRequests: filters.itemTypes.length === 0 || filters.itemTypes.includes("SERVICE_REQUEST"),
    showExceptions,
    toggleExceptions,
    togglePackageArchive,
    toggleRequestArchive,
    viewName,
  };
}

export type TeamBoardController = ReturnType<typeof useTeamBoardController>;

function buildRequestFilters(
  filters: BoardFilters,
  mode: "board" | "table",
  showExceptions: boolean,
  showArchive: boolean,
): BoardFilters {
  const defaultColumns = [
    ...serviceRequestBoardColumns,
    ...(showExceptions ? serviceRequestExceptionColumns : []),
    ...(showArchive ? archiveBoardColumns : []),
  ];
  return {
    ...filters,
    itemTypes: ["SERVICE_REQUEST"],
    columns: filters.columns.length || mode === "table" ? filters.columns : defaultColumns,
  };
}

function buildPackageFilters(
  filters: BoardFilters,
  mode: "board" | "table",
  showArchive: boolean,
): BoardFilters {
  return {
    ...filters,
    itemTypes: ["WORK_PACKAGE"],
    columns:
      filters.columns.length || mode === "table"
        ? filters.columns
        : [...workPackageBoardColumns, ...(showArchive ? archiveBoardColumns : [])],
  };
}

function useDeepLinkedRequest(
  itemId: string | null,
  item: BoardItem | undefined,
  handledItemId: string | null,
  setHandledItemId: (value: string) => void,
  setSelected: (value: BoardItem) => void,
) {
  useEffect(() => {
    if (!itemId || handledItemId === itemId || !item) return;
    setSelected(item);
    setHandledItemId(itemId);
  }, [handledItemId, item, itemId, setHandledItemId, setSelected]);
}

function configureBoard(
  access: TeamWorkspaceAccess,
  version: number | undefined,
  limits: Record<string, number>,
  csrfToken: string,
) {
  if (!access.grantId || version === undefined)
    throw new Error("Board management authority is required.");
  return boardApi.configure(
    access.teamId,
    {
      grantId: access.grantId,
      expectedVersion: version,
      wipLimits: limits,
    },
    csrfToken,
  );
}

function resetCursorToggle(
  toggle: React.Dispatch<React.SetStateAction<boolean>>,
  resetCursors: React.Dispatch<React.SetStateAction<Array<string | null>>>,
) {
  toggle((value) => !value);
  resetCursors([null]);
}
