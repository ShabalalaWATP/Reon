import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocation, useNavigate, useParams } from "react-router";

import { api } from "../../lib/api/client";
import type { AdminUserWriteInput } from "../../lib/api/types";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import { isSessionElevated, useAuth } from "../../lib/auth/AuthProvider";

export function useAdminUserPageController(create: boolean) {
  const { session } = useAuth();
  const queryKeys = protectedQueryKeys(session);
  const { userId } = useParams();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const user = useQuery({
    enabled: !create,
    queryFn: () => api.adminUser(requireUserId(userId)),
    queryKey: queryKeys.adminUser(userId),
  });
  const units = useQuery({
    queryFn: api.organisationUnits,
    queryKey: queryKeys.organisationUnits(),
  });
  const save = useMutation({
    mutationFn: (input: AdminUserWriteInput) =>
      saveUser(create, input, userId, user.data?.version, session!.csrfToken),
    onSuccess: (saved) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.adminUsersRoot() });
      queryClient.setQueryData(queryKeys.adminUser(saved.id), saved);
      if (create)
        void navigate(`/admin/users/${saved.id}`, { replace: true, state: { created: true } });
    },
  });
  const status = useMutation({
    mutationFn: (isActive: boolean) =>
      api.updateAdminUserStatus(
        requireUserId(userId),
        { isActive, expectedVersion: requireVersion(user.data?.version) },
        session!.csrfToken,
      ),
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKeys.adminUser(saved.id), saved);
      void queryClient.invalidateQueries({ queryKey: queryKeys.adminUsersRoot() });
    },
  });

  return {
    create,
    currentUserId: session!.user.id,
    elevated: isSessionElevated(session),
    justCreated: Boolean((location.state as { created?: boolean } | null)?.created),
    save,
    status,
    units,
    user,
  };
}

function saveUser(
  create: boolean,
  input: AdminUserWriteInput,
  userId: string | undefined,
  version: number | undefined,
  csrfToken: string,
) {
  if (create) return api.createAdminUser(input, csrfToken);
  return api.updateAdminUser(
    requireUserId(userId),
    { ...input, expectedVersion: requireVersion(version) },
    csrfToken,
  );
}

function requireUserId(userId: string | undefined) {
  if (!userId) throw new Error("A managed user identifier is required.");
  return userId;
}

function requireVersion(version: number | undefined) {
  if (version === undefined) throw new Error("The managed user version is unavailable.");
  return version;
}
