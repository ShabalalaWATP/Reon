import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";

import { adminManagedUser, adminSession, organisationUnit, organisationUnits, requesterSession } from "../../test/fixtures";
import { json, mockFetch, renderApp } from "../../test/render";
import { AdminUserForm } from "./AdminUserForm";

describe("platform administrator workspace", () => {
  it("reviews pending Customer account requests", async () => {
    const decisions: string[] = [];
    const items = [{
      id: "account-request-1", displayName: "Synthetic Customer", contactEmail: "customer@example.test",
      reason: "Access is needed for a fictional service request.", status: "PENDING", decisionNote: null,
      createdUserId: null, version: 1, createdAt: "2026-08-09T09:00:00Z",
      updatedAt: "2026-08-09T09:00:00Z", reviewedAt: null,
    }, {
      id: "account-request-2", displayName: "Second Customer", contactEmail: "second@example.test",
      reason: "Another fictional access request.", status: "PENDING", decisionNote: null,
      createdUserId: null, version: 1, createdAt: "2026-08-09T10:00:00Z",
      updatedAt: "2026-08-09T10:00:00Z", reviewedAt: null,
    }];
    mockFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(adminSession);
      if (url.pathname.endsWith("/admin/users")) return json({ items: [] });
      if (url.pathname.endsWith("/admin/account-requests") && !init.method) return json({ items });
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
    }, true, true, true, true, true, true, false);
    const user = userEvent.setup();
    renderApp("/admin/users");
    expect(await screen.findByText("Synthetic Customer")).toBeInTheDocument();
    await user.type(screen.getAllByLabelText("Rejection reason")[1], "Access need not established.");
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
    expect(view.container.querySelector('input[autocomplete="username"]')).toHaveAttribute("tabindex", "-1");
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
    vi.spyOn(window, "setTimeout").mockImplementation((handler, timeout, ...arguments_): ReturnType<typeof setTimeout> => {
      if (
        typeof handler === "function"
        && Number(timeout) >= 4_000
        && Number(timeout) <= 6_000
      ) expire = () => handler();
      return nativeSetTimeout(handler, timeout, ...arguments_) as unknown as ReturnType<typeof setTimeout>;
    });
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

  it("lists, searches and clears account metadata without request content", async () => {
    const paths: string[] = [];
    mockFetch((url) => {
      paths.push(`${url.pathname}${url.search}`);
      if (url.pathname.endsWith("/auth/me")) return json(adminSession);
      if (url.pathname.endsWith("/admin/users")) return json({ items: url.searchParams.get("query") ? [] : [{ ...adminManagedUser, role: "DELIVERY_SPECIALIST", memberships: [{ organisationUnitId: organisationUnit("SSG_TEAM").id, organisationUnitName: "SSG Team", organisationUnitKind: "TEAM" }] }, { ...adminManagedUser, id: "inactive", username: "admin3", displayName: "Erin Cuthbert", isActive: false }] });
      throw new Error(`Unexpected ${url.pathname}`);
    });
    const user = userEvent.setup();
    const view = renderApp("/admin/users");
    expect(await screen.findByRole("heading", { name: "User accounts" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Manage John McGinn" })).toBeInTheDocument();
    expect(screen.getByText("SSG Team")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Manage Erin Cuthbert" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "User accounts" })).toHaveClass("nav-link--active");
    expect(screen.queryByText("My requests")).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("Search accounts"), "nobody");
    await user.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByRole("heading", { name: "No accounts match this search" })).toBeInTheDocument();
    expect(paths.at(-1)).toBe("/api/v1/admin/users?query=nobody");
    await user.click(screen.getByRole("button", { name: "Clear" }));
    expect(await screen.findByRole("link", { name: "Manage John McGinn" })).toBeInTheDocument();
    expect(await axe(view.container)).toHaveNoViolations();
  });

  it("applies the global classification with optimistic version protection", async () => {
    let classification = "OFFICIAL";
    let fail = false;
    let version = 1;
    let submitted: Record<string, unknown> | undefined;
    mockFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(adminSession);
      if (url.pathname.endsWith("/admin/users")) return json({ items: [] });
      if (url.pathname.endsWith("/admin/platform/classification") && init.method === "PATCH") {
        if (fail) return json({ detail: "Stale version" }, 409);
        const body = JSON.parse(String(init.body)) as Record<string, unknown>;
        submitted = body;
        classification = String(body.classification);
        version += 1;
        return json({ classification, version, updatedAt: "2026-08-10T10:00:00Z" });
      }
      throw new Error(`${init.method ?? "GET"} ${url.pathname}`);
    });
    const user = userEvent.setup();
    const view = renderApp("/admin/users");

    expect(await screen.findByRole("heading", { name: "Platform classification" })).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Classification"), "OFFICIAL-SENSITIVE");
    await user.click(screen.getByRole("button", { name: "Apply to everyone" }));

    expect(await screen.findByText("Classification updated for every workspace.")).toHaveAttribute("role", "status");
    expect(screen.getByRole("note", { name: "Security classification: OFFICIAL-SENSITIVE" })).toBeInTheDocument();
    expect(submitted).toEqual({ classification: "OFFICIAL-SENSITIVE", expectedVersion: 1 });
    expect(await axe(view.container)).toHaveNoViolations();
    fail = true;
    await user.selectOptions(screen.getByLabelText("Classification"), "SECRET");
    await user.click(screen.getByRole("button", { name: "Apply to everyone" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("changed elsewhere");
  });

  it("recovers from a list error and reports an empty register", async () => {
    let fail = true;
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(adminSession);
      if (url.pathname.endsWith("/admin/users")) return fail ? json({ detail: "Unavailable" }, 503) : json({ items: [] });
      throw new Error(url.pathname);
    });
    const user = userEvent.setup();
    renderApp("/admin/users");
    expect(await screen.findByRole("heading", { name: "User accounts could not be loaded" })).toBeInTheDocument();
    fail = false;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: "No user accounts" })).toBeInTheDocument();
  });

  it("creates a generated account with compatible team membership", async () => {
    let created = false;
    let posted: Record<string, unknown> | undefined;
    const saved = { ...adminManagedUser, id: "new-user", username: "admin100", displayName: "Billy Gilmour", role: "DELIVERY_SPECIALIST" as const, scope: "Cedar Team", memberships: [{ organisationUnitId: organisationUnit("CEDAR_TEAM").id, organisationUnitName: "Cedar Team", organisationUnitKind: "TEAM" as const, workspacePosition: "MEMBER" as const }] };
    mockFetch(async (url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(adminSession);
      if (url.pathname.endsWith("/organisation/units")) return json({ items: organisationUnits });
      if (url.pathname.endsWith("/admin/users") && init.method === "POST") { posted = JSON.parse(String(init.body)); created = true; return json(saved, 201); }
      if (url.pathname.endsWith("/admin/users/new-user") && created) return json(saved);
      throw new Error(`${init.method ?? "GET"} ${url.pathname}`);
    });
    const user = userEvent.setup();
    const view = renderApp("/admin/users/new");
    await screen.findByRole("heading", { name: "Create user" });
    await user.type(screen.getByLabelText("Name"), "Billy Gilmour");
    await user.type(screen.getByLabelText("Work email"), "billy@example.test");
    await user.selectOptions(screen.getByLabelText("Representative role"), "DELIVERY_SPECIALIST");
    await user.type(screen.getByLabelText("Scope"), "Cedar Team");
    await user.click(screen.getByLabelText(/Cedar Team/));
    await user.click(screen.getByRole("button", { name: "Create user" }));
    expect(await screen.findByRole("heading", { name: "Billy Gilmour" })).toBeInTheDocument();
    expect(screen.getByText(/Account created\. Username:/)).toHaveTextContent("Account created. Username: admin100");
    expect(screen.getByDisplayValue("admin100")).toBeInTheDocument();
    expect(posted).toMatchObject({ displayName: "Billy Gilmour", role: "DELIVERY_SPECIALIST", organisationUnitIds: [organisationUnit("CEDAR_TEAM").id] });
    expect(await axe(view.container)).toHaveNoViolations();
  });

  it("edits and reversibly deactivates an account with version checks", async () => {
    let managed = adminManagedUser;
    const bodies: Record<string, unknown>[] = [];
    mockFetch(async (url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(adminSession);
      if (url.pathname.endsWith("/organisation/units")) return json({ items: organisationUnits });
      if (url.pathname.endsWith(`/admin/users/${managed.id}/status`)) { const body = JSON.parse(String(init.body)); bodies.push(body); managed = { ...managed, isActive: body.isActive, version: managed.version + 1 }; return json(managed); }
      if (url.pathname.endsWith(`/admin/users/${managed.id}`) && init.method === "PATCH") { const body = JSON.parse(String(init.body)); bodies.push(body); managed = { ...managed, ...body, version: managed.version + 1 }; return json(managed); }
      if (url.pathname.endsWith(`/admin/users/${managed.id}`)) return json(managed);
      throw new Error(`${init.method ?? "GET"} ${url.pathname}`);
    });
    const user = userEvent.setup();
    renderApp(`/admin/users/${managed.id}`);
    expect(await screen.findByRole("heading", { name: "John McGinn" })).toBeInTheDocument();
    await user.clear(screen.getByLabelText("Name"));
    await user.type(screen.getByLabelText("Name"), "John McGinn Updated");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByText("Account details saved.")).toBeInTheDocument();
    expect(bodies[0]).toMatchObject({ expectedVersion: 1, displayName: "John McGinn Updated" });
    await user.click(screen.getByRole("button", { name: "Deactivate account" }));
    await user.click(screen.getByRole("button", { name: "Confirm deactivation" }));
    expect(await screen.findByRole("button", { name: "Reactivate account" })).toBeInTheDocument();
    expect(bodies[1]).toEqual({ isActive: false, expectedVersion: 2 });
    await user.click(screen.getByRole("button", { name: "Reactivate account" }));
    expect(await screen.findByRole("button", { name: "Deactivate account" })).toBeInTheDocument();
  });

  it("conceals administrator routes from other roles and prevents self-deactivation", async () => {
    let requesterCalls = 0;
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/requests")) { requesterCalls += 1; return json({ items: [] }); }
      throw new Error(url.pathname);
    });
    renderApp("/admin/users");
    expect(await screen.findByRole("heading", { name: "No requests yet" })).toBeInTheDocument();
    expect(requesterCalls).toBe(1);
  });

  it("enforces compatible memberships and clears them when the role changes", async () => {
    const submit = vi.fn();
    const user = userEvent.setup();
    render(<AdminUserForm disabled={false} onSubmit={submit} units={organisationUnits} />);
    await user.type(screen.getByLabelText("Name"), "Kieran Tierney");
    await user.type(screen.getByLabelText("Work email"), "kieran@example.test");
    await user.type(screen.getByLabelText("Scope"), "SSG Team");
    await user.selectOptions(screen.getByLabelText("Representative role"), "DELIVERY_TEAM_LEAD");
    await user.click(screen.getByRole("button", { name: "Create user" }));
    expect(await screen.findByText("Select at least one compatible organisation unit.")).toBeInTheDocument();
    await user.click(screen.getByLabelText(/SSG Team/));
    await user.selectOptions(screen.getByLabelText("Representative role"), "REQUESTER");
    expect(screen.getByText("This role does not require an organisation membership.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Create user" }));
    expect(submit).toHaveBeenCalledWith(expect.objectContaining({ organisationUnitIds: [] }), expect.anything());
  });

  it("lets an Administrator appoint a routing-unit Manager explicitly", async () => {
    const submit = vi.fn();
    const user = userEvent.setup();
    render(<AdminUserForm disabled={false} onSubmit={submit} units={organisationUnits} />);
    await user.type(screen.getByLabelText("Name"), "Alan Rough");
    await user.type(screen.getByLabelText("Work email"), "alan@example.test");
    await user.type(screen.getByLabelText("Scope"), "CRIOC");
    await user.selectOptions(screen.getByLabelText("Representative role"), "INTAKE_TRIAGE");
    await user.selectOptions((await screen.findAllByRole("combobox"))[1], "MANAGER");
    await user.click(screen.getByRole("checkbox", { name: /CRIOC/ }));
    await user.click(screen.getByRole("button", { name: "Create user" }));
    expect(submit).toHaveBeenCalledWith(expect.objectContaining({
      organisationUnitIds: [organisationUnit("CRIOC").id],
      role: "INTAKE_TRIAGE",
      workspacePosition: "MANAGER",
    }), expect.anything());
  });

  it("reports editor failures and prevents the current Administrator deactivating themselves", async () => {
    const selfUser = { ...adminManagedUser, ...adminSession.user, isActive: true };
    let failUser = true;
    mockFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(adminSession);
      if (url.pathname.endsWith("/organisation/units")) return json({ items: organisationUnits });
      if (url.pathname.endsWith(`/admin/users/${selfUser.id}`) && init.method === "PATCH") return json({ detail: { message: "Version conflict" } }, 409);
      if (url.pathname.endsWith(`/admin/users/${selfUser.id}`)) return failUser ? json({ detail: "Missing" }, 404) : json(selfUser);
      throw new Error(url.pathname);
    });
    const user = userEvent.setup();
    const view = renderApp(`/admin/users/${selfUser.id}`);
    expect(await screen.findByRole("heading", { name: "User profile could not be loaded" })).toBeInTheDocument();
    failUser = false;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    const deactivate = await screen.findByRole("button", { name: "Deactivate account" });
    expect(deactivate).toBeDisabled();
    await user.clear(screen.getByLabelText("Name"));
    await user.type(screen.getByLabelText("Name"), "Andy Robertson Updated");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Version conflict");
    expect(await axe(view.container)).toHaveNoViolations();

  });

  it("requires organisation metadata before editing", async () => {
    let fail = true;
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(adminSession);
      if (url.pathname.endsWith("/organisation/units")) return fail ? json({ detail: "Unavailable" }, 503) : json({ items: organisationUnits });
      if (url.pathname.endsWith(`/admin/users/${adminManagedUser.id}`)) return json(adminManagedUser);
      throw new Error(url.pathname);
    });
    const user = userEvent.setup();
    renderApp(`/admin/users/${adminManagedUser.id}`);
    expect(await screen.findByRole("heading", { name: "Organisation could not be loaded" })).toBeInTheDocument();
    fail = false;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: "John McGinn" })).toBeInTheDocument();
  });
});
