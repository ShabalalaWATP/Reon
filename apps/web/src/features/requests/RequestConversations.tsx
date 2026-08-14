import { MessageSquareText } from "lucide-react";
import { useState } from "react";

import { ConversationComposer } from "./ConversationComposer";
import { ConversationTimeline, type ReplySelection } from "./ConversationTimeline";
import type { ConversationView } from "./conversationWorkspaceModel";
import { useRequestConversations } from "./useRequestConversations";
import { useCapabilities } from "../../lib/capabilities/useCapabilities";
import "./conversations.css";

type Props = {
  activityHref?: string;
  requestId: string;
};

export function RequestConversations({ activityHref, requestId }: Props) {
  const { capabilities, isPending } = useCapabilities();
  if (isPending || !capabilities.conversationReads) return null;
  return (
    <EnabledRequestConversations
      activityHref={activityHref}
      requestId={requestId}
      writesEnabled={capabilities.conversationWrites}
    />
  );
}

function EnabledRequestConversations({
  activityHref,
  requestId,
  writesEnabled,
}: Props & { writesEnabled: boolean }) {
  const [view, setView] = useState<ConversationView>("CUSTOMER");
  const [reply, setReply] = useState<ReplySelection | null>(null);
  const workspace = useRequestConversations(requestId, view, writesEnabled);

  const changeView = (next: ConversationView) => {
    setView(next);
    setReply(null);
  };

  return (
    <section
      aria-labelledby={`conversations-title-${requestId}`}
      className="detail-section request-conversations"
    >
      <div className="section-heading conversation-heading">
        <div>
          <span>Recorded correspondence</span>
          <h2 id={`conversations-title-${requestId}`}>Conversations</h2>
        </div>
        <MessageSquareText aria-hidden="true" size={20} />
      </div>
      <p className="conversation-assurance">
        Messages are retained on this request. Workflow decisions and transfers remain in the
        separate {activityHref ? <a href={activityHref}>Activity record</a> : "Activity record"}.
      </p>
      {!workspace.customer ? (
        <div aria-label="Conversation visibility" className="conversation-tabs" role="group">
          <button
            aria-pressed={view === "CUSTOMER"}
            disabled={workspace.mutation.isPending}
            onClick={() => changeView("CUSTOMER")}
            type="button"
          >
            Customer
          </button>
          <button
            aria-pressed={view === "INTERNAL"}
            disabled={workspace.mutation.isPending}
            onClick={() => changeView("INTERNAL")}
            type="button"
          >
            Internal
          </button>
        </div>
      ) : null}
      {workspace.query.isPending ? (
        <p className="conversation-state" role="status">
          Loading conversations…
        </p>
      ) : null}
      {workspace.query.isError ? (
        <div aria-live="polite" className="conversation-state">
          <p>Conversations could not be loaded.</p>
          <button className="button" onClick={() => void workspace.query.refetch()} type="button">
            Try again
          </button>
        </div>
      ) : null}
      {workspace.query.isSuccess ? (
        <>
          <ConversationTimeline
            conversations={workspace.visibleConversations}
            loadingConversationId={
              workspace.messagePage.isPending
                ? workspace.messagePage.variables.conversationId
                : null
            }
            messageLoadErrorId={
              workspace.messagePage.isError ? workspace.messagePage.variables.conversationId : null
            }
            onLoadOlder={(conversation) => {
              if (conversation.messagesNextCursor) {
                workspace.messagePage.mutate({
                  conversationId: conversation.id,
                  cursor: conversation.messagesNextCursor,
                });
              }
            }}
            onMarkReadRetry={workspace.markReadAgain}
            onReply={writesEnabled ? setReply : undefined}
            readErrorIds={workspace.readErrorIds}
          />
          <ConversationPageControl workspace={workspace} />
          {writesEnabled ? (
            <ConversationComposer
              error={workspace.mutation.error}
              isSending={workspace.mutation.isPending}
              onCancelReply={() => setReply(null)}
              onSend={(input) => workspace.mutation.mutateAsync(input).then(() => undefined)}
              reply={reply}
              targets={workspace.targets}
            />
          ) : null}
        </>
      ) : null}
    </section>
  );
}

function ConversationPageControl({
  workspace,
}: {
  workspace: ReturnType<typeof useRequestConversations>;
}) {
  const cursor = workspace.workspace.conversationsNextCursor;
  if (!cursor) return null;
  return (
    <div className="conversation-page-control">
      <button
        className="button button--quiet"
        disabled={workspace.conversationPage.isPending}
        onClick={() => workspace.conversationPage.mutate(cursor)}
        type="button"
      >
        {workspace.conversationPage.isPending ? "Loading…" : "Load more conversations"}
      </button>
      {workspace.conversationPage.isError ? (
        <p role="alert">More conversations could not be loaded. Try again.</p>
      ) : null}
    </div>
  );
}
