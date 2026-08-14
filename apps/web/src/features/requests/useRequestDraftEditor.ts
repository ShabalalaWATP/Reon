import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";
import { useNavigate } from "react-router";

import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { RequestCreateInput, RequestDraftInput, Session } from "../../lib/api/types";

export function useRequestDraftEditor(draftId: string | undefined, session: Session | null) {
  const queryKeys = protectedQueryKeys(session);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const submissionKey = useRef(globalThis.crypto.randomUUID());
  const draft = useQuery({
    queryKey: queryKeys.draft(draftId),
    queryFn: () => api.draft(draftId!),
    enabled: Boolean(session && draftId),
  });
  const invalidateRegisters = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.requests() });
    void queryClient.invalidateQueries({ queryKey: queryKeys.drafts() });
  };
  const submit = useMutation({
    mutationFn: (input: RequestCreateInput) =>
      draftId
        ? api.submitDraft(
            draftId,
            { ...input, expectedVersion: draft.data!.version },
            session?.csrfToken ?? "",
          )
        : api.createRequest(input, session?.csrfToken ?? ""),
    onSuccess: (request) => {
      invalidateRegisters();
      void navigate(`/requests/${request.id}`, { replace: true });
    },
  });
  const save = useMutation({
    mutationFn: (input: RequestDraftInput) =>
      draftId
        ? api.updateDraft(
            draftId,
            { ...input, expectedVersion: draft.data!.version },
            session?.csrfToken ?? "",
          )
        : api.createDraft(input, session?.csrfToken ?? ""),
    onSuccess: (savedDraft) => {
      queryClient.setQueryData(queryKeys.draft(savedDraft.id), savedDraft);
      void queryClient.invalidateQueries({ queryKey: queryKeys.drafts() });
      if (!draftId) {
        void navigate(`/requests/drafts/${savedDraft.id}`, { replace: true });
      }
    },
  });
  const remove = useMutation({
    mutationFn: () => api.deleteDraft(draftId!, draft.data!.version, session?.csrfToken ?? ""),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.drafts() });
      void navigate("/requests", { replace: true });
    },
  });

  return {
    busyWithDraft: save.isPending || remove.isPending,
    draft,
    error: submit.error ?? save.error ?? remove.error,
    remove,
    save,
    submit: (input: RequestCreateInput) =>
      submit.mutate({ ...input, submissionKey: submissionKey.current }),
    submitPending: submit.isPending,
  };
}
