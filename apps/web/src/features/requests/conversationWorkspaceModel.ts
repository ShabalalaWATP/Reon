import type {
  ConversationMessage,
  ConversationWorkspace,
  RequestConversation,
} from "../../lib/api/types";

export type ConversationView = "CUSTOMER" | "INTERNAL";

export function normaliseWorkspace(
  value: ConversationWorkspace | undefined,
): ConversationWorkspace {
  return {
    allowedTargets: Array.isArray(value?.allowedTargets) ? value.allowedTargets : [],
    conversations: Array.isArray(value?.conversations)
      ? value.conversations.map((conversation) => ({
          ...conversation,
          messagesNextCursor: conversation.messagesNextCursor ?? null,
        }))
      : [],
    conversationsNextCursor: value?.conversationsNextCursor ?? null,
  };
}

export function conversationsForView(
  workspace: ConversationWorkspace,
  customer: boolean,
  view: ConversationView,
) {
  return workspace.conversations.filter((conversation) =>
    customer ? conversation.visibility === "CUSTOMER_AND_STAFF" : viewMatches(conversation, view),
  );
}

export function targetsForView(
  workspace: ConversationWorkspace,
  customer: boolean,
  view: ConversationView,
) {
  if (customer) return workspace.allowedTargets;
  return workspace.allowedTargets.filter((target) =>
    view === "CUSTOMER" ? target.type === "CUSTOMER" : target.type !== "CUSTOMER",
  );
}

export function replaceConversation(
  current: RequestConversation[],
  updated: RequestConversation,
  retainCurrentCursor: boolean,
) {
  const existing = current.find((conversation) => conversation.id === updated.id);
  const merged = existing
    ? {
        ...updated,
        messages: mergeMessages(existing.messages, updated.messages),
        messagesNextCursor: retainCurrentCursor
          ? existing.messagesNextCursor
          : updated.messagesNextCursor,
      }
    : updated;
  return [merged, ...current.filter((conversation) => conversation.id !== updated.id)].sort(
    (left, right) => right.createdAt.localeCompare(left.createdAt),
  );
}

export function mergeWorkspacePage(current: ConversationWorkspace, page: ConversationWorkspace) {
  return {
    allowedTargets: current.allowedTargets,
    conversations: page.conversations.reduce(
      (conversations, conversation) => replaceConversation(conversations, conversation, false),
      current.conversations,
    ),
    conversationsNextCursor: page.conversationsNextCursor,
  };
}

export function markConversationRead(
  workspace: ConversationWorkspace | undefined,
  conversationId: string,
) {
  const current = normaliseWorkspace(workspace);
  return {
    ...current,
    conversations: current.conversations.map((conversation) =>
      conversation.id === conversationId
        ? {
            ...conversation,
            messages: conversation.messages.map((message) => ({
              ...message,
              isRead: true,
            })),
            unreadCount: 0,
          }
        : conversation,
    ),
  };
}

export function unreadWatermark(conversation: RequestConversation) {
  if (conversation.unreadCount <= 0) return null;
  const latestUnread = conversation.messages
    .filter((message) => !message.isRead)
    .sort((left, right) => left.createdAt.localeCompare(right.createdAt))
    .at(-1);
  return [
    conversation.unreadCount,
    latestUnread?.createdAt ?? "outside-page",
    latestUnread?.id ?? "outside-page",
  ].join(":");
}

function viewMatches(conversation: RequestConversation, view: ConversationView) {
  return view === "CUSTOMER"
    ? conversation.visibility === "CUSTOMER_AND_STAFF"
    : conversation.visibility === "STAFF_ONLY";
}

function mergeMessages(current: ConversationMessage[], incoming: ConversationMessage[]) {
  return [
    ...new Map([...current, ...incoming].map((message) => [message.id, message])).values(),
  ].sort((left, right) => left.createdAt.localeCompare(right.createdAt));
}
