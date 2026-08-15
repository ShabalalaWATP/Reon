import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { requesterSession } from "../test/fixtures";
import { json, mockFetch, renderApp } from "../test/render";

describe("route announcement", () => {
  it("names the page and moves focus to the main region only after navigating", async () => {
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/requests")) return json({ items: [] });
      throw new Error(`Unexpected ${url.pathname}`);
    });
    const user = userEvent.setup();
    const view = renderApp("/requests");

    expect(await screen.findByRole("heading", { name: "My requests" })).toBeInTheDocument();
    expect(document.title).toBe("My requests · ISTARI Service");
    expect(view.container.querySelector("#main-content")).not.toHaveFocus();

    const navigation = screen.getByRole("navigation", { name: "Primary navigation" });
    await user.click(within(navigation).getByRole("link", { name: "New request" }));

    expect(await screen.findByRole("heading", { name: "New service request" })).toBeInTheDocument();
    expect(document.title).toBe("New request · ISTARI Service");
    expect(view.container.querySelector("#main-content")).toHaveFocus();
  });

  it("names the sign-in page when no shell region exists to receive focus", async () => {
    mockFetch(() => json({ detail: "Signed out" }, 401));
    const view = renderApp("/requests");

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(document.title).toBe("Sign in · ISTARI Service");
    expect(view.container.querySelector("#main-content")).toBeNull();
  });
});
