import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import { json, mockFetch, renderApp } from "../../test/render";

describe("password assistance", () => {
  it("notifies an administrator without revealing whether an account exists", async () => {
    let fail = false;
    let submitted: Record<string, string> | undefined;
    mockFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json({ detail: "Signed out" }, 401);
      if (url.pathname.endsWith("/auth/password-assistance") && init.method === "POST") {
        if (fail) return json({ detail: "Unavailable" }, 503);
        submitted = JSON.parse(String(init.body));
        return json({
          status: "accepted",
          message: "If an active account matches that email, an administrator has been notified.",
        }, 202);
      }
      throw new Error(url.pathname);
    });
    const user = userEvent.setup();
    const view = renderApp("/login");

    await user.click(await screen.findByRole("button", { name: "Forgotten password?" }));
    expect(screen.getByRole("heading", { name: "Forgotten password" })).toBeInTheDocument();
    expect(screen.getByLabelText(/Work email/)).toHaveFocus();
    const submit = screen.getByRole("button", { name: "Notify administrator" });
    expect(submit).toBeDisabled();
    await user.type(screen.getByLabelText(/Work email/), "not-an-email");
    expect(await screen.findByRole("alert")).toHaveTextContent("Enter a valid work email.");
    await user.clear(screen.getByLabelText(/Work email/));
    await user.type(screen.getByLabelText(/Work email/), "  ADMIN2@ISTARI.EXAMPLE.TEST  ");
    await user.click(submit);

    expect(await screen.findByRole("status")).toHaveTextContent("If an active account matches that email");
    expect(submitted).toEqual({ email: "ADMIN2@ISTARI.EXAMPLE.TEST" });
    expect(await axe(view.container)).toHaveNoViolations();
    await user.click(screen.getByRole("button", { name: "Back to sign in" }));
    expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Forgotten password?" }));
    await user.type(screen.getByLabelText(/Work email/), "admin2@istari.example.test");
    fail = true;
    await user.click(screen.getByRole("button", { name: "Notify administrator" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to send the request");
  });
});
