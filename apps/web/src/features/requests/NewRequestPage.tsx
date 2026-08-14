import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router";

import { PageState } from "../../components/PageState";
import { ApiError } from "../../lib/api/client";
import { useAuth } from "../../lib/auth/AuthProvider";
import { formatDate } from "../../lib/status";
import { RequestForm } from "./RequestForm";
import { useRequestDraftEditor } from "./useRequestDraftEditor";

export function NewRequestPage() {
  const { draftId } = useParams();
  const { session } = useAuth();
  const editor = useRequestDraftEditor(draftId, session);
  if (!session) return null;
  if (draftId && editor.draft.isPending) {
    return <PageState kind="loading" title="Loading your draft" />;
  }
  if (draftId && editor.draft.isError) return <DraftUnavailable />;

  return (
    <main className="page-stack page-stack--narrow">
      <Link className="back-link" to="/requests">
        <ArrowLeft aria-hidden="true" size={16} />
        My requests
      </Link>
      <RequestDraftHeading draftId={draftId} updatedAt={editor.draft.data?.updatedAt} />
      <EditorError error={editor.error} />
      <DraftSaved saved={editor.save.isSuccess && !editor.save.isPending} />
      <RequestForm
        disabled={editor.submitPending}
        draftDisabled={editor.busyWithDraft}
        hasDraft={Boolean(draftId)}
        initialValues={editor.draft.data}
        onDeleteDraft={() => editor.remove.mutate()}
        onSaveDraft={(input) => editor.save.mutate(input)}
        onSubmit={editor.submit}
      />
    </main>
  );
}

function DraftUnavailable() {
  return (
    <PageState
      action={
        <Link className="button" to="/requests">
          Return to requests
        </Link>
      }
      kind="error"
      title="Draft could not be loaded"
    >
      It may have been submitted, deleted or changed in another session.
    </PageState>
  );
}

function RequestDraftHeading({ draftId, updatedAt }: { draftId?: string; updatedAt?: string }) {
  return (
    <header className="page-heading">
      <div>
        <span>Structured Customer request</span>
        <h1>{draftId ? "Edit request draft" : "New service request"}</h1>
        <p>
          Provide enough context for routing users and the production team to understand and fulfil
          the request.
        </p>
        {updatedAt ? <small>Private draft, last saved {formatDate(updatedAt, true)}</small> : null}
      </div>
    </header>
  );
}

function EditorError({ error }: { error: Error | null }) {
  if (!error) return null;
  return (
    <p className="form-banner form-banner--error" role="alert">
      {error instanceof ApiError ? error.message : "The request could not be saved. Try again."}
    </p>
  );
}

function DraftSaved({ saved }: { saved: boolean }) {
  if (!saved) return null;
  return (
    <p className="form-banner form-banner--success" role="status">
      Draft saved privately.
    </p>
  );
}
