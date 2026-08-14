import { useQuery } from "@tanstack/react-query";

import { capabilityApi, disabledCapabilities } from "../api/capabilityClient";
import { protectedQueryKeys } from "../api/queryKeys";
import { useAuth } from "../auth/AuthProvider";

export function useCapabilities() {
  const { session } = useAuth();
  const queryKeys = protectedQueryKeys(session);
  const query = useQuery({
    queryKey: queryKeys.capabilities(),
    queryFn: capabilityApi.capabilities,
    enabled: Boolean(session),
    retry: false,
    staleTime: 60_000,
  });
  return {
    capabilities: query.data ?? disabledCapabilities,
    isPending: Boolean(session) && query.isPending,
  };
}
