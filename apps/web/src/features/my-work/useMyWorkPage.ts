import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { actionNotificationApi } from "../../lib/api/actionNotificationClient";
import type {
  ActionColumn,
  ActionFilters,
  SavedActionView,
} from "../../lib/api/actionNotificationTypes";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import { useAuth } from "../../lib/auth/AuthProvider";
import { actionColumns } from "./myWorkModel";

const allFilters: ActionFilters = { sections: [], actionTypes: [], dueBefore: null };

export function useMyWorkPage() {
  const { session } = useAuth();
  const queryKeys = protectedQueryKeys(session);
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState<ActionFilters>(allFilters);
  const [columns, setColumns] = useState<ActionColumn[]>(actionColumns);
  const [selectedView, setSelectedView] = useState("");
  const query = useInfiniteQuery({
    queryKey: queryKeys.actions(JSON.stringify(filters)),
    queryFn: ({ pageParam }) =>
      actionNotificationApi.actions({ ...filters, cursor: pageParam ?? undefined }),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.nextCursor,
    refetchInterval: 30_000,
  });
  const invalidate = () => queryClient.invalidateQueries({ queryKey: queryKeys.actionsRoot() });
  const createView = useMutation({
    mutationFn: (name: string) =>
      actionNotificationApi.createActionView(
        { name, filters, visibleColumns: columns },
        session!.csrfToken,
      ),
    onSuccess: () => void invalidate(),
  });
  const updateView = useMutation({
    mutationFn: (view: SavedActionView) =>
      actionNotificationApi.updateActionView(
        view.id,
        { name: view.name, filters, visibleColumns: columns, expectedVersion: view.version },
        session!.csrfToken,
      ),
    onSuccess: () => void invalidate(),
  });
  const deleteView = useMutation({
    mutationFn: (view: SavedActionView) =>
      actionNotificationApi.deleteActionView(view.id, view.version, session!.csrfToken),
    onSuccess: () => {
      setSelectedView("");
      void invalidate();
    },
  });
  const applyView = (view: SavedActionView) => {
    setFilters(view.filters);
    setColumns(view.visibleColumns);
  };
  return {
    applyView,
    columns,
    createView,
    deleteView,
    filters,
    query,
    selectedView,
    session: session!,
    setColumns,
    setFilters,
    setSelectedView,
    updateView,
  };
}
