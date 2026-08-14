import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import type { Session, WorkItem } from "../../lib/api/types";
import {
  enabledCapabilities,
  requestDetail,
  requesterSession,
  staffSession,
  workItem,
} from "../../test/fixtures";
import { json, mockFeatureFetch, renderApp } from "../../test/render";
import {
  conversationWorkspace as workspace,
  customerConversation,
  internalConversation,
  mockConversationDetail,
} from "./conversationTestSupport";

describe("structured request conversations", () => {
  it("does not call conversation endpoints when reads are disabled", async () => {
    const fetchMock = mockFeatureFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/me/capabilities")) {
        return json({ ...enabledCapabilities, conversationReads: false });
      }
      if (url.pathname.endsWith(`/requests/${requestDetail.id}`)) return json(requestDetail);
      throw new Error(`Unexpected ${url.pathname}`);
    });

    renderApp(`/requests/${requestDetail.id}`);

    expect(await screen.findByRole("heading", { name: requestDetail.title })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Conversations" })).not.toBeInTheDocument();
    expect(
      fetchMock.mock.calls
        .map(([input]) => String(input))
        .some((path) => path.includes("/conversations")),
    ).toBe(false);
  });

  it("allows reads but calls no write endpoint when conversation writes are disabled", async () => {
    const readOnlyWorkspace = {
      ...workspace,
      conversations: [{ ...customerConversation, unreadCount: 2 }],
    };
    const fetchMock = mockFeatureFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/me/capabilities")) {
        return json({ ...enabledCapabilities, conversationWrites: false });
      }
      if (url.pathname.endsWith(`/requests/${requestDetail.id}/conversations`)) {
        return json(readOnlyWorkspace);
      }
      if (url.pathname.endsWith(`/requests/${requestDetail.id}`)) return json(requestDetail);
      throw new Error(`Unexpected ${url.pathname}`);
    });

    renderApp(`/requests/${requestDetail.id}`);

    expect(
      await screen.findByText("Can you confirm the preferred delivery time?"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Reply to/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Send message" })).not.toBeInTheDocument();
    const requests = fetchMock.mock.calls.map(([input, init]) => ({
      method: init?.method ?? "GET",
      path: String(input),
    }));
    expect(
      requests.some(({ method, path }) => method === "POST" && path.includes("/conversations")),
    ).toBe(false);
  });

  it("shows the Analyst ledger, sends to an allowed internal target and renders it immediately", async () => {
    const analystSession: Session = {
      ...staffSession,
      user: { ...staffSession.user, role: "DELIVERY_SPECIALIST", displayName: "Ben Doak" },
    };
    const assignedItem: WorkItem = {
      ...workItem,
      stage: "IN_PROGRESS",
      status: "CLAIMED",
      assigneeId: analystSession.user.id,
      assigneeDisplayName: analystSession.user.displayName,
      assignedToCurrentUser: true,
      availableActions: ["submit"],
      deliveryTeam: "SSG Team",
    };
    let submitted: Record<string, unknown> | undefined;
    let releaseMessage: (() => void) | undefined;
    mockFeatureFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(analystSession);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/work-items")) return json({ items: [assignedItem] });
      if (url.pathname.endsWith(`/requests/${requestDetail.id}/conversations/messages`)) {
        submitted = JSON.parse(String(init.body)) as Record<string, unknown>;
        const conversation = {
          ...internalConversation,
          id: "ffffffff-ffff-4fff-8fff-ffffffffffff",
          subject: "Evidence check",
          messages: [
            {
              ...internalConversation.messages[0],
              id: "99999999-9999-4999-8999-999999999999",
              senderDisplayName: "Ben Doak",
              body: "Can you validate the evidence source?",
            },
          ],
        };
        return new Promise<Response>((resolve) => {
          releaseMessage = () => resolve(json({ conversation, event: requestDetail.events[0] }));
        });
      }
      if (url.pathname.endsWith(`/requests/${requestDetail.id}/conversations`))
        return json(workspace);
      if (url.pathname.endsWith(`/tracked-requests/${requestDetail.id}`)) return json({});
      if (url.pathname.endsWith(`/requests/${requestDetail.id}`)) return json(requestDetail);
      throw new Error(`Unexpected ${url.pathname}`);
    });
    const user = userEvent.setup();
    const view = renderApp("/delivery/my-work");

    expect(
      await screen.findByText("Can you confirm the preferred delivery time?"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Internal" }));
    expect(screen.getByText("Please confirm the analytical approach.")).toBeInTheDocument();
    expect(
      screen.queryByText("Can you confirm the preferred delivery time?"),
    ).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Send to"), "TEAM_MANAGERS:");
    await user.type(screen.getByLabelText(/Subject/), "Evidence check");
    await user.type(screen.getByLabelText("Message"), "Can you validate the evidence source?");
    await user.click(screen.getByRole("button", { name: "Send message" }));
    expect(await screen.findByRole("button", { name: "Sending…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Customer" })).toBeDisabled();
    expect(screen.getByLabelText("Send to")).toBeDisabled();
    expect(screen.getByLabelText(/Subject/)).toBeDisabled();
    expect(screen.getByLabelText("Message")).toBeDisabled();
    releaseMessage!();

    await waitFor(() =>
      expect(submitted).toMatchObject({
        body: "Can you validate the evidence source?",
        subject: "Evidence check",
        targetType: "TEAM_MANAGERS",
      }),
    );
    expect(submitted?.clientMutationId).toEqual(expect.any(String));
    expect(await screen.findByText("Can you validate the evidence source?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Customer" })).toBeEnabled();
    expect(screen.getAllByText("Team Analyst").length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: "Customer" }));
    expect(screen.getByText("Can you confirm the preferred delivery time?")).toBeInTheDocument();
    expect(await axe(view.container)).toHaveNoViolations();
  });

  it("records a reply in the selected thread without resending its target", async () => {
    let submitted: Record<string, unknown> | undefined;
    const replied = {
      ...customerConversation,
      messages: [
        ...customerConversation.messages,
        {
          ...customerConversation.messages[0],
          id: "12121212-1212-4212-8212-121212121212",
          senderUserId: requesterSession.user.id,
          senderDisplayName: requesterSession.user.displayName,
          senderRole: "REQUESTER" as const,
          body: "Delivery at 16:00 would be best.",
          replyToMessageId: customerConversation.messages[0].id,
        },
      ],
    };
    mockConversationDetail(
      requesterSession,
      {
        allowedTargets: [{ type: "CURRENT_OWNER", unitId: null, label: "Current owner" }],
        conversations: [customerConversation],
        conversationsNextCursor: null,
      },
      (url, init) => {
        if (url.pathname.endsWith("/conversations/messages")) {
          submitted = JSON.parse(String(init.body)) as Record<string, unknown>;
          return json({ conversation: replied, event: requestDetail.events[0] });
        }
        return undefined;
      },
    );
    const user = userEvent.setup();
    renderApp(`/requests/${requestDetail.id}`);
    await user.click(await screen.findByRole("button", { name: "Reply to Ben Doak" }));
    await user.type(screen.getByLabelText("Reply"), "Delivery at 16:00 would be best.");
    await user.click(screen.getByRole("button", { name: "Send reply" }));

    await waitFor(() =>
      expect(submitted).toMatchObject({
        conversationId: customerConversation.id,
        replyToMessageId: customerConversation.messages[0].id,
      }),
    );
    expect(submitted).not.toHaveProperty("targetType");
    expect(await screen.findByText("Delivery at 16:00 would be best.")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: `Reply to ${requesterSession.user.displayName}` }),
    ).not.toBeInTheDocument();
  });

  it("never renders an internal conversation to a Customer and records visible messages as read", async () => {
    let readCount = 0;
    let readFails = true;
    mockConversationDetail(
      requesterSession,
      {
        ...workspace,
        conversations: [{ ...customerConversation, unreadCount: 2 }, internalConversation],
      },
      (url, init) => {
        if (url.pathname.endsWith(`/conversations/${customerConversation.id}/read`)) {
          readCount += 1;
          expect(init.method).toBe("POST");
          if (readFails) return json({ detail: "Unavailable" }, 503);
          return json({ conversationId: customerConversation.id, unreadCount: 0 });
        }
        return undefined;
      },
    );
    renderApp(`/requests/${requestDetail.id}`);

    const conversations = await screen.findByText("Can you confirm the preferred delivery time?");
    const section = conversations.closest("section")!;
    expect(
      within(section).getByText("Can you confirm the preferred delivery time?"),
    ).toBeInTheDocument();
    expect(
      within(section).queryByText("Please confirm the analytical approach."),
    ).not.toBeInTheDocument();
    expect(within(section).queryByRole("button", { name: "Internal" })).not.toBeInTheDocument();
    expect(
      await within(section).findByText("Read status could not be updated."),
    ).toBeInTheDocument();
    readFails = false;
    await userEvent.setup().click(within(section).getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(readCount).toBe(2));
    expect(within(section).queryByText("2 unread")).not.toBeInTheDocument();
  });

  it("loads older conversations and messages from their opaque cursors", async () => {
    const conversationCursor = "older conversations/+=";
    const messageCursor = "older messages/+=";
    const current = { ...customerConversation, messagesNextCursor: messageCursor };
    const olderConversation = {
      ...customerConversation,
      id: "34343434-3434-4434-8434-343434343434",
      subject: "Earlier customer query",
      createdAt: "2026-08-13T09:00:00Z",
    };
    const requestedCursors: string[] = [];
    let messageAttempt = 0;
    let releaseConversation: (() => void) | undefined;
    let releaseMessages: (() => void) | undefined;
    mockConversationDetail(
      requesterSession,
      {
        ...workspace,
        conversations: [current],
        conversationsNextCursor: conversationCursor,
      },
      (url) => {
        if (url.pathname.endsWith(`/conversations/${current.id}`)) {
          requestedCursors.push(url.searchParams.get("cursor") ?? "");
          messageAttempt += 1;
          if (messageAttempt === 1) return json({ detail: "Unavailable" }, 503);
          const response = json({
            ...current,
            messages: [
              {
                ...current.messages[0],
                id: "45454545-4545-4454-8454-454545454545",
                body: "This is the older message.",
                createdAt: "2026-08-13T08:00:00Z",
              },
            ],
            messagesNextCursor: null,
          });
          return new Promise<Response>((resolve) => {
            releaseMessages = () => resolve(response);
          });
        }
        if (url.pathname.endsWith("/conversations") && url.searchParams.has("cursor")) {
          requestedCursors.push(url.searchParams.get("cursor") ?? "");
          const response = json({
            allowedTargets: workspace.allowedTargets,
            conversations: [olderConversation],
            conversationsNextCursor: null,
          });
          return new Promise<Response>((resolve) => {
            releaseConversation = () => resolve(response);
          });
        }
        return undefined;
      },
    );
    const user = userEvent.setup();
    renderApp(`/requests/${requestDetail.id}`);

    const olderMessagesButton = await screen.findByRole("button", {
      name: `Load older messages in ${current.subject}`,
    });
    await user.click(olderMessagesButton);
    expect(
      await screen.findByText("Older messages could not be loaded. Try again."),
    ).toBeInTheDocument();
    await user.click(olderMessagesButton);
    expect(olderMessagesButton).toBeDisabled();
    releaseMessages!();
    expect(await screen.findByText("This is the older message.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Load more conversations" }));
    expect(await screen.findByRole("button", { name: "Loading…" })).toBeDisabled();
    releaseConversation!();
    expect(await screen.findByText("Earlier customer query")).toBeInTheDocument();
    expect(requestedCursors).toEqual([messageCursor, messageCursor, conversationCursor]);
  });
});
