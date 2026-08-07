import { useQuery } from "@tanstack/react-query";

import { capabilityApi, disabledCapabilities } from "../api/capabilityClient";
import { protectedQueryKeys } from "../api/queryKeys";
import { useAuth } from "../auth/AuthProvider";

export function useCapabilities() {
  const { session } = useAuth();
  const query = useQuery({
    queryKey: protectedQueryKeys.capabilities(session?.user.id ?? "anonymous"),
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
