import type { UserRole } from "./coreTypes";
import type { RequestEvent } from "./requestTypes";

export type ConversationTargetType =
  "CUSTOMER" | "CURRENT_OWNER" | "TEAM_MANAGERS" | "ASSIGNED_ANALYSTS" | "ROUTE_UNIT" | "QC_TEAM";

export type ConversationVisibility = "CUSTOMER_AND_STAFF" | "STAFF_ONLY";

export type ConversationTarget = {
  type: ConversationTargetType;
  unitId: string | null;
  label: string;
};

export type ConversationMessage = {
  id: string;
  senderUserId: string;
  senderDisplayName: string;
  senderRole: UserRole;
  body: string;
  replyToMessageId: string | null;
  createdAt: string;
  isRead: boolean;
};

export type RequestConversation = {
  id: string;
  subject: string;
  targetType: ConversationTargetType;
  targetUnitId: string | null;
  targetLabel: string;
  visibility: ConversationVisibility;
  createdAt: string;
  messages: ConversationMessage[];
  messagesNextCursor: string | null;
  unreadCount: number;
};

export type ConversationWorkspace = {
  allowedTargets: ConversationTarget[];
  conversations: RequestConversation[];
  conversationsNextCursor: string | null;
};

export type ConversationReadResult = {
  conversationId: string;
  unreadCount: number;
};

export type ConversationMessageInput = {
  body: string;
  clientMutationId: string;
  subject?: string;
  targetType?: ConversationTargetType;
  targetUnitId?: string;
  conversationId?: string;
  replyToMessageId?: string;
};

export type ConversationMutationResult = {
  conversation: RequestConversation;
  event: RequestEvent;
};
