import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { FeedbackInput, Session } from "../../lib/api/types";
import { requestDetailPollInterval } from "./requestPolling";

export function useRequestDetail(requestId: string, session: Session | null) {
  const queryKeys = protectedQueryKeys(session);
  const queryClient = useQueryClient();
  const request = useQuery({
    queryKey: queryKeys.request(requestId),
    queryFn: () => api.request(requestId),
    enabled: Boolean(session && requestId),
    refetchInterval: (currentQuery) => requestDetailPollInterval(currentQuery.state.data),
  });
  const feedback = useMutation({
    mutationFn: (input: FeedbackInput) => api.feedback(requestId, input, session?.csrfToken ?? ""),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: queryKeys.request(requestId) }),
  });
  return { feedback, request };
}
