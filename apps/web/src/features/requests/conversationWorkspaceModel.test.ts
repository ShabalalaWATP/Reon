import { describe, expect, it } from "vitest";

import type { ConversationWorkspace, RequestConversation } from "../../lib/api/types";
import {
  conversationsForView,
  markConversationRead,
  mergeWorkspacePage,
  replaceConversation,
  targetsForView,
  unreadWatermark,
} from "./conversationWorkspaceModel";

const customerConversation = conversation({
  id: "customer-conversation",
  visibility: "CUSTOMER_AND_STAFF",
});
const internalConversation = conversation({
  id: "internal-conversation",
  visibility: "STAFF_ONLY",
});
const workspace: ConversationWorkspace = {
  allowedTargets: [
    { label: "Customer", type: "CUSTOMER", unitId: null },
    { label: "Current owner", type: "CURRENT_OWNER", unitId: null },
  ],
  conversations: [customerConversation, internalConversation],
  conversationsNextCursor: "next-page",
};

describe("conversation workspace model", () => {
  it("keeps customer and internal views separate", () => {
    expect(conversationsForView(workspace, false, "CUSTOMER")).toEqual([customerConversation]);
    expect(conversationsForView(workspace, false, "INTERNAL")).toEqual([internalConversation]);
    expect(conversationsForView(workspace, true, "INTERNAL")).toEqual([customerConversation]);
    expect(targetsForView(workspace, false, "CUSTOMER")).toEqual([workspace.allowedTargets[0]]);
    expect(targetsForView(workspace, false, "INTERNAL")).toEqual([workspace.allowedTargets[1]]);
  });

  it("merges bounded pages without duplicating messages or conversations", () => {
    const updated = conversation({
      id: customerConversation.id,
      messages: [
        {
          ...customerConversation.messages[0],
          body: "Updated copy",
        },
        {
          ...customerConversation.messages[0],
          createdAt: "2026-08-14T09:01:00Z",
          id: "message-2",
        },
      ],
      messagesNextCursor: null,
    });
    const replaced = replaceConversation(workspace.conversations, updated, true);

    expect(replaced[0].messages).toHaveLength(2);
    expect(replaced[0].messages[0].body).toBe("Updated copy");
    expect(replaced[0].messagesNextCursor).toBe("older-messages");

    const merged = mergeWorkspacePage(workspace, {
      allowedTargets: [],
      conversations: [updated],
      conversationsNextCursor: null,
    });
    expect(merged.allowedTargets).toEqual(workspace.allowedTargets);
    expect(merged.conversations).toHaveLength(2);
    expect(merged.conversationsNextCursor).toBeNull();
  });

  it("uses the latest unread message as a changing read watermark", () => {
    const first = unreadWatermark(customerConversation);
    const next = unreadWatermark({
      ...customerConversation,
      messages: [
        ...customerConversation.messages,
        {
          ...customerConversation.messages[0],
          createdAt: "2026-08-14T09:02:00Z",
          id: "message-2",
        },
      ],
    });

    expect(first).not.toBeNull();
    expect(next).not.toEqual(first);
    expect(unreadWatermark({ ...customerConversation, unreadCount: 0 })).toBeNull();
  });

  it("marks only the selected conversation and its messages as read", () => {
    const updated = markConversationRead(workspace, customerConversation.id);

    expect(updated.conversations[0].unreadCount).toBe(0);
    expect(updated.conversations[0].messages[0].isRead).toBe(true);
    expect(updated.conversations[1]).toEqual(internalConversation);
  });
});

function conversation(overrides: Partial<RequestConversation>): RequestConversation {
  return {
    createdAt: "2026-08-14T09:00:00Z",
    id: "conversation",
    messages: [
      {
        body: "Message",
        createdAt: "2026-08-14T09:00:00Z",
        id: "message-1",
        isRead: false,
        replyToMessageId: null,
        senderDisplayName: "Ben Doak",
        senderRole: "DELIVERY_SPECIALIST",
        senderUserId: "user-1",
      },
    ],
    messagesNextCursor: "older-messages",
    subject: "Subject",
    targetLabel: "Customer",
    targetType: "CUSTOMER",
    targetUnitId: null,
    unreadCount: 1,
    visibility: "CUSTOMER_AND_STAFF",
    ...overrides,
  };
}
