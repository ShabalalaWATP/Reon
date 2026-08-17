import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";

import { adminSession, organisationUnits } from "../../test/fixtures";
import { json, mockFetch, renderApp } from "../../test/render";

describe("platform administrator access", () => {
  it("reviews pending Customer account requests", async () => {
    const decisions: string[] = [];
    const items = [
      {
        id: "account-request-1",
        displayName: "Synthetic Customer",
        contactEmail: "customer@example.test?bcc=attacker@example.test",
        reason: "Access is needed for a fictional service request.",
        status: "PENDING",
        decisionNote: null,
        createdUserId: null,
        version: 1,
        createdAt: "2026-08-09T09:00:00Z",
        updatedAt: "2026-08-09T09:00:00Z",
        reviewedAt: null,
      },
      {
        id: "account-request-2",
        displayName: "Second Customer",
        contactEmail: "second@example.test",
        reason: "Another fictional access request.",
        status: "PENDING",
        decisionNote: null,
        createdUserId: null,
        version: 1,
        createdAt: "2026-08-09T10:00:00Z",
        updatedAt: "2026-08-09T10:00:00Z",
        reviewedAt: null,
      },
    ];
    mockFetch(
      (url, init) => {
        if (url.pathname.endsWith("/auth/me")) return json(adminSession);
        if (url.pathname.endsWith("/admin/users")) return json({ items: [] });
        if (url.pathname.endsWith("/admin/account-requests") && !init.method)
          return json({ items });
        if (url.pathname.endsWith("/approve") && init.method === "POST") {
          decisions.push("approve");
          const reviewed = items.shift();
          return json({ ...reviewed, status: "APPROVED" });
        }
        if (url.pathname.endsWith("/reject") && init.method === "POST") {
          decisions.push("reject");
          const reviewed = items.pop();
          return json({ ...reviewed, status: "REJECTED" });
        }
        throw new Error(`${init.method ?? "GET"} ${url.pathname}`);
      },
      true,
      true,
      true,
      true,
      true,
      true,
      false,
    );
    const user = userEvent.setup();
    renderApp("/admin/users");
    expect(await screen.findByText("Synthetic Customer")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "customer@example.test?bcc=attacker@example.test" }),
    ).toHaveAttribute("href", "mailto:customer%40example.test%3Fbcc%3Dattacker%40example.test");
    await user.type(
      screen.getAllByLabelText("Rejection reason")[1],
      "Access need not established.",
    );
    await user.click(screen.getAllByRole("button", { name: "Reject" })[1]);
    await waitFor(() => expect(screen.queryByText("Second Customer")).not.toBeInTheDocument());
    await user.click(await screen.findByRole("button", { name: "Approve Customer account" }));
    expect(decisions).toEqual(["reject", "approve"]);
  });

  it("unlocks sensitive controls only after fresh password confirmation", async () => {
    const unelevated = { ...adminSession, elevatedUntil: null };
    let confirmedPassword: string | undefined;
    mockFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(unelevated);
      if (url.pathname.endsWith("/auth/elevate") && init.method === "POST") {
        confirmedPassword = JSON.parse(String(init.body)).password;
        return json({ elevatedUntil: "2099-01-01T00:05:00Z" });
      }
      if (url.pathname.endsWith("/organisation/units")) return json({ items: organisationUnits });
      throw new Error(`${init.method ?? "GET"} ${url.pathname}`);
    });
    const user = userEvent.setup();
    const view = renderApp("/admin/users/new");
    const create = await screen.findByText("Create user", { selector: "button" });
    expect(create).toBeDisabled();
    expect(view.container.querySelector('input[autocomplete="username"]')).toHaveAttribute(
      "tabindex",
      "-1",
    );
    await user.type(screen.getByLabelText(/^Current password/), "admin");
    await user.click(screen.getByRole("button", { name: "Confirm password" }));
    expect(await screen.findByText("Sensitive changes enabled")).toBeInTheDocument();
    expect(create).toBeEnabled();
    expect(confirmedPassword).toBe("admin");
    expect(await axe(view.container)).toHaveNoViolations();
  });

  it("relocks idle sensitive controls when step-up expires", async () => {
    const expiring = { ...adminSession, elevatedUntil: new Date(Date.now() + 5_000).toISOString() };
    const nativeSetTimeout = window.setTimeout.bind(window);
    let expire: (() => void) | undefined;
    vi.spyOn(window, "setTimeout").mockImplementation(
      (handler, timeout, ...arguments_): ReturnType<typeof setTimeout> => {
        if (typeof handler === "function" && Number(timeout) >= 4_000 && Number(timeout) <= 6_000)
          expire = () => handler();
        return nativeSetTimeout(handler, timeout, ...arguments_) as unknown as ReturnType<
          typeof setTimeout
        >;
      },
    );
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(expiring);
      if (url.pathname.endsWith("/organisation/units")) return json({ items: organisationUnits });
      throw new Error(url.pathname);
    });
    renderApp("/admin/users/new");
    const create = await screen.findByText("Create user", { selector: "button" });
    expect(await screen.findByText("Sensitive changes enabled")).toBeInTheDocument();
    expect(create).toBeEnabled();
    expect(expire).toBeTypeOf("function");
    act(() => expire?.());
    const password = await screen.findByLabelText(/^Current password/);
    await waitFor(() => expect(password).toHaveFocus());
    expect(create).toBeDisabled();
  });

  it("keeps sensitive controls locked when password confirmation fails", async () => {
    const unelevated = { ...adminSession, elevatedUntil: "2000-01-01T00:00:00Z" };
    mockFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(unelevated);
      if (url.pathname.endsWith("/auth/elevate") && init.method === "POST") {
        return json({ detail: { message: "Unable to confirm that password." } }, 401);
      }
      if (url.pathname.endsWith("/organisation/units")) return json({ items: organisationUnits });
      throw new Error(url.pathname);
    });
    const user = userEvent.setup();
    renderApp("/admin/users/new");
    const create = await screen.findByText("Create user", { selector: "button" });
    await user.type(screen.getByLabelText(/^Current password/), "wrong");
    await user.click(screen.getByRole("button", { name: "Confirm password" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to confirm that password.");
    expect(screen.getByLabelText(/^Current password/)).toHaveValue("");
    expect(create).toBeDisabled();
  });
});
