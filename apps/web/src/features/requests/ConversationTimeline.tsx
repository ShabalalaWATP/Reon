import { Reply } from "lucide-react";

import type { ConversationMessage, RequestConversation } from "../../lib/api/types";
import { roleLabels } from "../../lib/routes";
import { formatDate } from "../../lib/status";

export type ReplySelection = {
  conversation: RequestConversation;
  message: ConversationMessage;
};

type Props = {
  conversations: RequestConversation[];
  loadingConversationId: string | null;
  messageLoadErrorId: string | null;
  onLoadOlder: (conversation: RequestConversation) => void;
  onMarkReadRetry: (conversationId: string) => void;
  onReply?: (selection: ReplySelection) => void;
  readErrorIds: ReadonlySet<string>;
};

export function ConversationTimeline({
  conversations,
  loadingConversationId,
  messageLoadErrorId,
  onLoadOlder,
  onMarkReadRetry,
  onReply,
  readErrorIds,
}: Props) {
  if (conversations.length === 0) {
    return <p className="conversation-empty">No messages have been recorded in this view.</p>;
  }
  return (
    <ol aria-label="Recorded conversations" className="conversation-list">
      {conversations.map((conversation) => (
        <li className="conversation-thread" key={conversation.id}>
          <header>
            <div>
              <h3>{conversation.subject}</h3>
              <p>
                To {conversation.targetLabel} · {visibilityLabel(conversation.visibility)}
              </p>
            </div>
            {conversation.unreadCount > 0 ? (
              <span className="conversation-unread">{conversation.unreadCount} unread</span>
            ) : null}
          </header>
          {readErrorIds.has(conversation.id) ? (
            <p className="conversation-inline-state" role="alert">
              Read status could not be updated.
              <button onClick={() => onMarkReadRetry(conversation.id)} type="button">
                Try again
              </button>
            </p>
          ) : null}
          {conversation.messagesNextCursor ? (
            <button
              aria-label={`Load older messages in ${conversation.subject}`}
              className="conversation-load-more"
              disabled={loadingConversationId === conversation.id}
              onClick={() => onLoadOlder(conversation)}
              type="button"
            >
              {loadingConversationId === conversation.id ? "Loading…" : "Load older messages"}
            </button>
          ) : null}
          {messageLoadErrorId === conversation.id ? (
            <p className="conversation-inline-state" role="alert">
              Older messages could not be loaded. Try again.
            </p>
          ) : null}
          <ol className="conversation-messages">
            {[...conversation.messages]
              .sort((left, right) => left.createdAt.localeCompare(right.createdAt))
              .map((message) => (
                <li key={message.id}>
                  <div className="conversation-message__meta">
                    <strong>{message.senderDisplayName}</strong>
                    <span>{roleLabels[message.senderRole]}</span>
                    <time dateTime={message.createdAt}>{formatDate(message.createdAt, true)}</time>
                  </div>
                  <p>{message.body}</p>
                  {message.replyToMessageId === null && onReply ? (
                    <button
                      aria-label={`Reply to ${message.senderDisplayName}`}
                      className="conversation-reply"
                      onClick={() => onReply({ conversation, message })}
                      type="button"
                    >
                      <Reply aria-hidden="true" size={14} /> Reply
                    </button>
                  ) : null}
                </li>
              ))}
          </ol>
        </li>
      ))}
    </ol>
  );
}

function visibilityLabel(visibility: RequestConversation["visibility"]) {
  return visibility === "CUSTOMER_AND_STAFF" ? "Customer-visible" : "Internal";
}
