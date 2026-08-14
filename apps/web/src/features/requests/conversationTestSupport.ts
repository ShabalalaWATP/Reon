import type { ConversationWorkspace, RequestConversation, Session } from "../../lib/api/types";
import { enabledCapabilities, requestDetail, staffSession } from "../../test/fixtures";
import { json, mockFeatureFetch } from "../../test/render";

export const customerConversation: RequestConversation = {
  id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  subject: "Delivery timing",
  targetType: "CUSTOMER",
  targetUnitId: null,
  targetLabel: "Customer",
  visibility: "CUSTOMER_AND_STAFF",
  createdAt: "2026-08-14T09:00:00Z",
  messagesNextCursor: null,
  unreadCount: 0,
  messages: [
    {
      id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      senderUserId: staffSession.user.id,
      senderDisplayName: "Ben Doak",
      senderRole: "DELIVERY_SPECIALIST",
      body: "Can you confirm the preferred delivery time?",
      replyToMessageId: null,
      createdAt: "2026-08-14T09:00:00Z",
      isRead: true,
    },
  ],
};

export const internalConversation: RequestConversation = {
  ...customerConversation,
  id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
  subject: "Manager guidance",
  targetType: "TEAM_MANAGERS",
  targetLabel: "SSG Team Managers",
  visibility: "STAFF_ONLY",
  messages: [
    {
      ...customerConversation.messages[0],
      id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
      body: "Please confirm the analytical approach.",
    },
  ],
};

export const conversationWorkspace: ConversationWorkspace = {
  allowedTargets: [
    { type: "CUSTOMER", unitId: null, label: "Customer" },
    { type: "TEAM_MANAGERS", unitId: null, label: "SSG Team Managers" },
    {
      type: "ROUTE_UNIT",
      unitId: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
      label: "ACSA-B Ops",
    },
  ],
  conversations: [internalConversation, customerConversation],
  conversationsNextCursor: null,
};

export function mockConversationDetail(
  session: Session,
  workspace: ConversationWorkspace,
  override?: (url: URL, init: RequestInit) => Response | Promise<Response> | undefined,
) {
  mockFeatureFetch((url, init) => {
    const overridden = override?.(url, init);
    if (overridden) return overridden;
    if (url.pathname.endsWith("/auth/me")) return json(session);
    if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
    if (url.pathname.endsWith("/read")) {
      return json({ conversationId: "conversation", unreadCount: 0 });
    }
    if (url.pathname.endsWith(`/requests/${requestDetail.id}/conversations`)) {
      return json(workspace);
    }
    if (url.pathname.endsWith(`/tracked-requests/${requestDetail.id}`)) return json({});
    if (url.pathname.endsWith(`/requests/${requestDetail.id}`)) return json(requestDetail);
    throw new Error(`Unexpected ${url.pathname}`);
  });
}
