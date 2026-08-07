import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { useRef } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { PageState } from "../../components/PageState";
import { ApiError, api } from "../../lib/api/client";
import type { RequestCreateInput, RequestDraftInput } from "../../lib/api/types";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import { useAuth } from "../../lib/auth/AuthProvider";
import { formatDate } from "../../lib/status";
import { RequestForm } from "./RequestForm";

export function NewRequestPage() {
  const { draftId } = useParams();
  const { session } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const submissionKey = useRef(globalThis.crypto.randomUUID());
  const userId = session?.user.id ?? "anonymous";
  const draftQuery = useQuery({
    queryKey: protectedQueryKeys.draft(userId, draftId),
    queryFn: () => api.draft(draftId!),
    enabled: Boolean(session && draftId),
  });
  const invalidateRegisters = () => {
    void queryClient.invalidateQueries({ queryKey: protectedQueryKeys.requests(userId) });
    void queryClient.invalidateQueries({ queryKey: protectedQueryKeys.drafts(userId) });
  };
  const submit = useMutation({
    mutationFn: (input: RequestCreateInput) => draftId
      ? api.submitDraft(draftId, { ...input, expectedVersion: draftQuery.data!.version }, session?.csrfToken ?? "")
      : api.createRequest(input, session?.csrfToken ?? ""),
    onSuccess: (request) => {
      invalidateRegisters();
      void navigate(`/requests/${request.id}`, { replace: true });
    },
  });
  const save = useMutation({
    mutationFn: (input: RequestDraftInput) => draftId
      ? api.updateDraft(draftId, { ...input, expectedVersion: draftQuery.data!.version }, session?.csrfToken ?? "")
      : api.createDraft(input, session?.csrfToken ?? ""),
    onSuccess: (draft) => {
      queryClient.setQueryData(protectedQueryKeys.draft(userId, draft.id), draft);
      void queryClient.invalidateQueries({ queryKey: protectedQueryKeys.drafts(userId) });
      if (!draftId) void navigate(`/requests/drafts/${draft.id}`, { replace: true });
    },
  });
  const remove = useMutation({
    mutationFn: () => api.deleteDraft(draftId!, draftQuery.data!.version, session?.csrfToken ?? ""),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: protectedQueryKeys.drafts(userId) });
      void navigate("/requests", { replace: true });
    },
  });

  if (!session) return null;
  if (draftId && draftQuery.isPending) return <PageState kind="loading" title="Loading your draft" />;
  if (draftId && draftQuery.isError) return <PageState action={<Link className="button" to="/requests">Return to requests</Link>} kind="error" title="Draft could not be loaded">It may have been submitted, deleted or changed in another session.</PageState>;
  const error = submit.error ?? save.error ?? remove.error;
  const busyWithDraft = save.isPending || remove.isPending;

  return (
    <main className="page-stack page-stack--narrow">
      <Link className="back-link" to="/requests"><ArrowLeft aria-hidden="true" size={16} />My requests</Link>
      <header className="page-heading"><div><span>Structured Customer request</span><h1>{draftId ? "Edit request draft" : "New service request"}</h1><p>Provide enough context for routing users and the production team to understand and fulfil the request.</p>{draftQuery.data ? <small>Private draft, last saved {formatDate(draftQuery.data.updatedAt, true)}</small> : null}</div></header>
      {error ? <p className="form-banner form-banner--error" role="alert">{error instanceof ApiError ? error.message : "The request could not be saved. Try again."}</p> : null}
      {save.isSuccess && !save.isPending ? <p className="form-banner form-banner--success" role="status">Draft saved privately.</p> : null}
      <RequestForm
        businessArea={session.user.scope}
        disabled={submit.isPending}
        draftDisabled={busyWithDraft}
        hasDraft={Boolean(draftId)}
        initialValues={draftQuery.data}
        onDeleteDraft={() => remove.mutate()}
        onSaveDraft={(input) => save.mutate(input)}
        onSubmit={(input) => submit.mutate({ ...input, submissionKey: submissionKey.current })}
      />
    </main>
  );
}
