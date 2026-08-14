import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { RequestConversation } from "../../lib/api/types";
import { ConversationTimeline } from "./ConversationTimeline";

const conversation: RequestConversation = {
  id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  subject: "Evidence query",
  targetType: "TEAM_MANAGERS",
  targetUnitId: null,
  targetLabel: "SSG Team Managers",
  visibility: "STAFF_ONLY",
  createdAt: "2026-08-14T09:00:00Z",
  messagesNextCursor: "older-cursor",
  unreadCount: 1,
  messages: [
    {
      id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      senderUserId: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
      senderDisplayName: "Ben Doak",
      senderRole: "DELIVERY_SPECIALIST",
      body: "Please check the source.",
      replyToMessageId: null,
      createdAt: "2026-08-14T09:00:00Z",
      isRead: false,
    },
  ],
};

describe("conversation timeline states", () => {
  it("shows accessible loading and retry states and invokes their controls", async () => {
    const load = vi.fn();
    const retryRead = vi.fn();
    const view = render(
      <ConversationTimeline
        conversations={[conversation]}
        loadingConversationId={conversation.id}
        messageLoadErrorId={conversation.id}
        onLoadOlder={load}
        onMarkReadRetry={retryRead}
        onReply={vi.fn()}
        readErrorIds={new Set([conversation.id])}
      />,
    );
    const user = userEvent.setup();

    expect(
      screen.getByRole("button", { name: `Load older messages in ${conversation.subject}` }),
    ).toBeDisabled();
    expect(screen.getByText("Older messages could not be loaded. Try again.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(retryRead).toHaveBeenCalledWith(conversation.id);
    view.rerender(
      <ConversationTimeline
        conversations={[conversation]}
        loadingConversationId={null}
        messageLoadErrorId={null}
        onLoadOlder={load}
        onMarkReadRetry={retryRead}
        onReply={vi.fn()}
        readErrorIds={new Set()}
      />,
    );
    await user.click(
      screen.getByRole("button", { name: `Load older messages in ${conversation.subject}` }),
    );
    expect(load).toHaveBeenCalledWith(conversation);
  });
});
