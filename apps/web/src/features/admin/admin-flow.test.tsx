import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";

import { adminManagedUser, adminSession, organisationUnit, organisationUnits, requesterSession } from "../../test/fixtures";
import { json, mockFetch, renderApp } from "../../test/render";
import { AdminUserForm } from "./AdminUserForm";

describe("platform administrator workspace", () => {
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
    await user.type(screen.getByLabelText(/^Current password/), "admin");
    await user.click(screen.getByRole("button", { name: "Confirm password" }));
    expect(await screen.findByText("Sensitive changes enabled")).toBeInTheDocument();
    expect(create).toBeEnabled();
    expect(confirmedPassword).toBe("admin");
    expect(await axe(view.container)).toHaveNoViolations();
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
    expect(create).toBeDisabled();
  });

  it("lists, searches and clears account metadata without request content", async () => {
    const paths: string[] = [];
    mockFetch((url) => {
      paths.push(`${url.pathname}${url.search}`);
      if (url.pathname.endsWith("/auth/me")) return json(adminSession);
      if (url.pathname.endsWith("/admin/users")) return json({ items: url.searchParams.get("query") ? [] : [{ ...adminManagedUser, role: "DELIVERY_SPECIALIST", memberships: [{ organisationUnitId: organisationUnit("OSG_TEAM").id, organisationUnitName: "OSG Team", organisationUnitKind: "TEAM" }] }, { ...adminManagedUser, id: "inactive", username: "admin3", displayName: "Erin Cuthbert", isActive: false }] });
      throw new Error(`Unexpected ${url.pathname}`);
    });
    const user = userEvent.setup();
    const view = renderApp("/admin/users");
    expect(await screen.findByRole("heading", { name: "User accounts" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Manage John McGinn" })).toBeInTheDocument();
    expect(screen.getByText("OSG Team")).toBeInTheDocument();
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
    const saved = { ...adminManagedUser, id: "new-user", username: "admin99", displayName: "Billy Gilmour", role: "DELIVERY_SPECIALIST" as const, scope: "Cedar Team", memberships: [{ organisationUnitId: organisationUnit("CEDAR_TEAM").id, organisationUnitName: "Cedar Team", organisationUnitKind: "TEAM" as const }] };
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
    await user.type(screen.getByLabelText("Display name"), "Billy Gilmour");
    await user.selectOptions(screen.getByLabelText("Representative role"), "DELIVERY_SPECIALIST");
    await user.type(screen.getByLabelText("Scope"), "Cedar Team");
    await user.click(screen.getByLabelText(/Cedar Team/));
    await user.click(screen.getByRole("button", { name: "Create user" }));
    expect(await screen.findByRole("heading", { name: "Billy Gilmour" })).toBeInTheDocument();
    expect(screen.getByText(/Account created\. Username:/)).toHaveTextContent("Account created. Username: admin99");
    expect(screen.getByDisplayValue("admin99")).toBeInTheDocument();
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
    await user.clear(screen.getByLabelText("Display name"));
    await user.type(screen.getByLabelText("Display name"), "John McGinn Updated");
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
    await user.type(screen.getByLabelText("Display name"), "Kieran Tierney");
    await user.type(screen.getByLabelText("Scope"), "OSG Team");
    await user.selectOptions(screen.getByLabelText("Representative role"), "DELIVERY_TEAM_LEAD");
    await user.click(screen.getByRole("button", { name: "Create user" }));
    expect(await screen.findByText("Select at least one compatible organisation unit.")).toBeInTheDocument();
    await user.click(screen.getByLabelText(/OSG Team/));
    await user.selectOptions(screen.getByLabelText("Representative role"), "REQUESTER");
    expect(screen.getByText("This role does not require an organisation membership.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Create user" }));
    expect(submit).toHaveBeenCalledWith(expect.objectContaining({ organisationUnitIds: [] }), expect.anything());
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
    await user.clear(screen.getByLabelText("Display name"));
    await user.type(screen.getByLabelText("Display name"), "Andy Robertson Updated");
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
