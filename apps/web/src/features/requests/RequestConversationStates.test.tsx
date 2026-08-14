import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { requestDetail, requesterSession } from "../../test/fixtures";
import { json, renderApp } from "../../test/render";
import {
  conversationWorkspace as workspace,
  mockConversationDetail,
} from "./conversationTestSupport";

describe("structured request conversations", () => {
  it("shows a safe empty composer when the server provides no authorised target", async () => {
    mockConversationDetail(requesterSession, {
      allowedTargets: [],
      conversations: [],
      conversationsNextCursor: null,
    });
    renderApp(`/requests/${requestDetail.id}`);

    expect(
      await screen.findByText("No messages have been recorded in this view."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("No authorised message destinations are available at this stage."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Send message" })).not.toBeInTheDocument();
  });

  it("offers an accessible retry when the ledger cannot be loaded", async () => {
    let failed = true;
    mockConversationDetail(requesterSession, workspace, (url) => {
      if (url.pathname.endsWith("/conversations")) {
        return failed ? json({ detail: "Unavailable" }, 503) : json(workspace);
      }
      return undefined;
    });
    const user = userEvent.setup();
    renderApp(`/requests/${requestDetail.id}`);
    expect(await screen.findByText("Conversations could not be loaded.")).toBeInTheDocument();
    failed = false;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(
      await screen.findByText("Can you confirm the preferred delivery time?"),
    ).toBeInTheDocument();
  });
});
