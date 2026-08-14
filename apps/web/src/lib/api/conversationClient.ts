import type {
  ConversationMessageInput,
  ConversationMutationResult,
  ConversationReadResult,
  RequestConversation,
  ConversationWorkspace,
} from "./conversationTypes";
import { apiRequest } from "./transport";

export const conversationApi = {
  requestConversations: (requestId: string, cursor?: string) =>
    apiRequest<ConversationWorkspace>(conversationWorkspacePath(requestId, cursor)),
  conversationMessages: (requestId: string, conversationId: string, cursor: string) =>
    apiRequest<RequestConversation>(
      `/requests/${encodeURIComponent(requestId)}/conversations/${encodeURIComponent(conversationId)}?limit=50&cursor=${encodeURIComponent(cursor)}`,
    ),
  markConversationRead: (requestId: string, conversationId: string, csrfToken: string) =>
    apiRequest<ConversationReadResult>(
      `/requests/${encodeURIComponent(requestId)}/conversations/${encodeURIComponent(conversationId)}/read`,
      { csrfToken, method: "POST" },
    ),
  postConversationMessage: (
    requestId: string,
    input: ConversationMessageInput,
    csrfToken: string,
  ) =>
    apiRequest<ConversationMutationResult>(
      `/requests/${encodeURIComponent(requestId)}/conversations/messages`,
      { body: input, csrfToken, method: "POST" },
    ),
};

function conversationWorkspacePath(requestId: string, cursor?: string) {
  const base = `/requests/${encodeURIComponent(requestId)}/conversations`;
  const query = new URLSearchParams({ limit: "20", messageLimit: "50" });
  if (cursor) query.set("cursor", cursor);
  return `${base}?${query.toString()}`;
}
