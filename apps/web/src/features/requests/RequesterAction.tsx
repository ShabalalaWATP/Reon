import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, ApiError } from "../../lib/api/client";
import type { ClarificationThread, WorkAction } from "../../lib/api/types";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import { useAuth } from "../../lib/auth/AuthProvider";
import { WorkActionPanel } from "../work/WorkActionPanel";
import { clarificationTaskPollInterval } from "./requestPolling";

export function RequesterAction({
  clarification,
  requestId,
}: {
  clarification?: ClarificationThread;
  requestId: string;
}) {
  const { session } = useAuth();
  const userId = session?.user.id ?? "anonymous";
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: protectedQueryKeys.workItems(userId),
    queryFn: () => api.workItems(),
    enabled: Boolean(session),
    refetchInterval: (currentQuery) =>
      clarificationTaskPollInterval(currentQuery.state.data, requestId),
  });
  const item = query.data?.items.find((candidate) => candidate.requestId === requestId);
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: protectedQueryKeys.request(userId, requestId),
      }),
      queryClient.invalidateQueries({ queryKey: protectedQueryKeys.requests(userId) }),
      queryClient.invalidateQueries({ queryKey: protectedQueryKeys.workItems(userId) }),
    ]);
  };
  const claim = useMutation({ mutationFn: () => api.claimWorkItem(item!.id, session!.csrfToken), onSuccess: refresh });
  const complete = useMutation({ mutationFn: (action: WorkAction) => api.completeWorkItem(item!.id, action, session!.csrfToken), onSuccess: refresh });
  if (query.isPending) return <p className="inline-loading">Loading the requested response…</p>;
  if (query.isError) return <p className="form-banner form-banner--error" role="alert">The requested response could not be loaded.</p>;
  if (!item || !session) return <p className="inline-empty">No response task is currently available.</p>;
  const error = claim.error ?? complete.error;
  return <>{error ? <p className="form-banner form-banner--error" role="alert">{error instanceof ApiError ? error.message : "The outcome could not be recorded."}</p> : null}<WorkActionPanel clarification={clarification} currentUserId={session.user.id} disabled={claim.isPending || complete.isPending} item={item} onClaim={() => claim.mutate()} onComplete={(action) => complete.mutate(action)} /></>;
}
