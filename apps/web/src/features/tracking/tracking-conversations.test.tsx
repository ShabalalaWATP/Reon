import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import {
  enabledCapabilities,
  requestDetail,
  staffSession,
  trackedRequest,
} from "../../test/fixtures";
import { json, mockFeatureFetch, renderApp } from "../../test/render";

describe("route-scoped conversations", () => {
  it("records questions and return requests without claiming work", async () => {
    const commands: Array<Record<string, unknown>> = [];
    let rejectMessage = false;
    let rejectReturn = false;
    mockFeatureFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(staffSession);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith(`/requests/${trackedRequest.id}/conversations`)) {
        return json({
          allowedTargets: [{ type: "CUSTOMER", unitId: null, label: "Customer" }],
          conversations: [],
        });
      }
      if (url.pathname.endsWith(`/tracked-requests/${trackedRequest.id}`)) {
        return json(trackingDetail());
      }
      if (init.method === "POST") {
        if (rejectMessage && url.pathname.endsWith("/conversations/messages")) {
          return json({ detail: "The message could not be recorded." }, 409);
        }
        if (rejectReturn && url.pathname.endsWith("/return-requests")) {
          return json({ detail: "The current owner could not be contacted." }, 409);
        }
        const command = JSON.parse(String(init.body)) as Record<string, unknown>;
        commands.push(command);
        return url.pathname.endsWith("/conversations/messages")
          ? json(messageResult(String(command.body)))
          : json({ event: { id: `event-${commands.length}` } });
      }
      throw new Error(`Unexpected ${url.pathname}`);
    });
    const user = userEvent.setup();
    renderApp(`/tracking/${trackedRequest.id}`);

    await user.type(
      await screen.findByLabelText("Message"),
      "Can the Customer confirm the priority?",
    );
    await user.click(screen.getByRole("button", { name: "Send message" }));
    await user.type(
      screen.getByLabelText("Reason"),
      "CRIOC needs to reconsider the routing decision.",
    );
    await user.click(screen.getByRole("button", { name: "Request return" }));

    expect(commands[0]).toMatchObject({
      targetType: "CUSTOMER",
      body: "Can the Customer confirm the priority?",
    });
    expect(commands[0]).toHaveProperty("clientMutationId");
    expect(commands[1]).toEqual({
      targetUnitId: trackedRequest.route[0].id,
      reason: "CRIOC needs to reconsider the routing decision.",
    });

    rejectReturn = true;
    await user.type(
      screen.getByLabelText("Reason"),
      "This later return request should fail safely.",
    );
    await user.click(screen.getByRole("button", { name: "Request return" }));
    expect(
      await screen.findByText("The current owner could not be contacted."),
    ).toBeInTheDocument();
    rejectMessage = true;
    await user.type(screen.getByLabelText("Message"), "This later message should fail safely.");
    await user.click(screen.getByRole("button", { name: "Send message" }));
    expect(await screen.findByText("The message could not be recorded.")).toBeInTheDocument();
  });
});

function trackingDetail() {
  return {
    ...trackedRequest,
    requesterDisplayName: requestDetail.requester.displayName,
    ...Object.fromEntries(
      [
        "description",
        "questionToAnswer",
        "desiredOutcome",
        "backgroundContext",
        "subjectAreaOrLocation",
        "coverageStart",
        "coverageEnd",
        "customerUrgency",
        "supportedActivityOrDecision",
        "requiredByReason",
        "preferredDeliverableType",
        "successCriteria",
        "constraintsOrCaveats",
        "supportingInformation",
        "sensitivity",
        "handlingInstructions",
      ].map((key) => [key, requestDetail[key as keyof typeof requestDetail]]),
    ),
    events: [],
    eventsNextCursor: null,
  };
}

function messageResult(body: string) {
  return {
    conversation: {
      id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      subject: "Customer message",
      targetType: "CUSTOMER",
      targetUnitId: null,
      targetLabel: "Customer",
      visibility: "CUSTOMER_AND_STAFF",
      createdAt: "2026-08-14T09:00:00Z",
      unreadCount: 0,
      messages: [
        {
          id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
          senderUserId: staffSession.user.id,
          senderDisplayName: staffSession.user.displayName,
          senderRole: staffSession.user.role,
          body,
          replyToMessageId: null,
          createdAt: "2026-08-14T09:00:00Z",
          isRead: true,
        },
      ],
    },
    event: { id: "event-message" },
  };
}
