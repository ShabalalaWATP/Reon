import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { requestDetail, requesterSession } from "../../test/fixtures";
import { json, mockFeatureFetch, renderApp } from "../../test/render";

describe("request coordination message", () => {
  it("lets a Customer message the current owner and reports a later failure", async () => {
    const sent: unknown[] = [];
    let fail = false;
    let release: (() => void) | undefined;
    mockFeatureFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith(`/requests/${requestDetail.id}/coordination`)) {
        if (fail) return json({ detail: "The message could not be accepted." }, 409);
        sent.push(JSON.parse(String(init.body)));
        return new Promise<Response>((resolve) => {
          release = () => resolve(json({ event: requestDetail.events[0] }));
        });
      }
      if (url.pathname.endsWith(`/requests/${requestDetail.id}`)) return json(requestDetail);
      throw new Error(url.pathname);
    });
    const user = userEvent.setup();
    renderApp(`/requests/${requestDetail.id}`);
    const field = await screen.findByLabelText("Question or information");

    await user.type(field, "Please confirm the current expected delivery date.");
    await user.click(screen.getByRole("button", { name: "Send message" }));
    expect(await screen.findByRole("button", { name: "Sending…" })).toBeDisabled();
    release!();
    expect(sent).toEqual([{
      audience: "CURRENT_OWNER",
      body: "Please confirm the current expected delivery date.",
    }]);
    await screen.findByRole("button", { name: "Send message" });
    expect(field).toHaveValue("");

    fail = true;
    await user.type(field, "This second synthetic message should fail safely.");
    await user.click(screen.getByRole("button", { name: "Send message" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The message could not be accepted.",
    );
  });
});
