import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useParams } from "react-router";

import { configurationApi } from "../../lib/api/configurationClient";
import type { ConfigurationDraftInput } from "../../lib/api/configurationTypes";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import { isSessionElevated, useAuth } from "../../lib/auth/AuthProvider";

export function useConfigurationPageController() {
  const { configurationId } = useParams();
  const navigate = useNavigate();
  const { session } = useAuth();
  const queryKeys = protectedQueryKeys(session);
  const [selectedUnitId, setSelectedUnitId] = useState<string | null>(null);
  const [treeSearch, setTreeSearch] = useState("");
  const versions = useQuery({
    queryFn: configurationApi.versions,
    queryKey: queryKeys.configurationVersions(),
  });
  const selectedId = configurationId ?? versions.data?.items[0]?.id;
  const version = useQuery({
    enabled: Boolean(selectedId),
    queryFn: () => configurationApi.version(requireId(selectedId)),
    queryKey: queryKeys.configurationVersion(selectedId),
  });
  const definitions = useQuery({
    queryFn: configurationApi.workflowDefinitions,
    queryKey: queryKeys.workflowDefinitions(),
  });
  const preview = useQuery({
    enabled: Boolean(selectedId),
    queryFn: () => configurationApi.preview(requireId(selectedId)),
    queryKey: queryKeys.configurationPreview(selectedId, version.data?.version),
  });
  const refresh = () => Promise.all([version.refetch(), versions.refetch(), preview.refetch()]);
  const replace = useMutation({
    mutationFn: (draft: ConfigurationDraftInput) =>
      configurationApi.replace(
        requireId(selectedId),
        { ...draft, expectedVersion: requireVersion(version.data?.version) },
        session!.csrfToken,
      ),
    onSuccess: refresh,
  });
  const focusUnit = (unitId: string) => {
    setTreeSearch("");
    setSelectedUnitId(unitId);
    requestAnimationFrame(() => document.getElementById(`configuration-unit-${unitId}`)?.focus());
  };

  return {
    definitions,
    editable: isSessionElevated(session) && version.data?.status === "DRAFT",
    elevated: isSessionElevated(session),
    focusUnit,
    navigate,
    preview,
    refresh,
    replace,
    selectedId,
    selectedUnitId,
    setSelectedUnitId,
    setTreeSearch,
    treeSearch,
    version,
    versions,
  };
}

function requireId(configurationId: string | undefined) {
  if (!configurationId) throw new Error("A configuration identifier is required.");
  return configurationId;
}

function requireVersion(version: number | undefined) {
  if (version === undefined) throw new Error("The configuration version is unavailable.");
  return version;
}
