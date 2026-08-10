import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import {
  organisationUnit,
  organisationUnits,
  adminSession,
  requesterSession,
} from "../../test/fixtures";
import { json, mockFetch, renderApp } from "../../test/render";
import { buildOrganisationTree } from "./organisationTree";

describe("organisation hierarchy", () => {
  it("shows the complete hierarchy and honest staffing states", async () => {
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/organisation/units")) {
        return json({ items: organisationUnits });
      }
      throw new Error(`Unexpected ${url.pathname}`);
    });

    const view = renderApp("/organisation");
    expect(await screen.findByRole("heading", { name: "JIOC routing hierarchy" })).toBeInTheDocument();
    expect(organisationUnits).toHaveLength(40);
    expect(organisationUnits.filter((unit) => unit.kind === "COMMAND")).toHaveLength(3);
    expect(organisationUnits.filter((unit) => unit.kind === "OPS_GROUP")).toHaveLength(9);
    expect(organisationUnits.filter((unit) => unit.kind === "TEAM")).toHaveLength(27);
    expect(
      organisationUnits.filter((unit) => unit.staffingStatus === "STAFFED"),
    ).toHaveLength(27);
    const hierarchy = screen.getByRole("list", { name: "Organisation hierarchy" });
    expect(within(hierarchy).getAllByText("JIOC")).not.toHaveLength(0);
    expect(within(hierarchy).getAllByText("DIGOC")).not.toHaveLength(0);
    expect(within(hierarchy).getAllByText("SYGOC")).not.toHaveLength(0);
    expect(within(hierarchy).getAllByText("MYGOC")).not.toHaveLength(0);
    expect(within(hierarchy).getByText("NCGI-A Ops")).toBeInTheDocument();
    expect(within(hierarchy).getByText("Aurora Ops")).toBeInTheDocument();
    expect(within(hierarchy).getByText("Vertex Ops")).toBeInTheDocument();
    const osg = within(hierarchy).getByText("OSG Team").closest("article")!;
    expect(within(osg).getByText("Team staffed")).toBeInTheDocument();
    const alternative = within(hierarchy).getByText("Cedar Team").closest("article")!;
    expect(within(alternative).getByText("Team staffed")).toBeInTheDocument();
    expect(within(hierarchy).getAllByText("Routing function").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Organisation" })).toHaveClass("nav-link--active");
    expect(await axe(view.container)).toHaveNoViolations();
  });

  it("recovers from an error and reports an empty configuration", async () => {
    let fail = true;
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/organisation/units")) {
        return fail ? json({ detail: "Unavailable" }, 503) : json({ items: [] });
      }
      throw new Error(url.pathname);
    });
    const user = userEvent.setup();
    renderApp("/organisation");
    expect(await screen.findByRole("heading", { name: "Organisation could not be loaded" })).toBeInTheDocument();
    fail = false;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: "No organisation units configured" })).toBeInTheDocument();
  });

  it("allows an Administrator to rename metadata inline without changing stable identity", async () => {
    let reject = true;
    let body: Record<string, unknown> | undefined;
    mockFetch(async (url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(adminSession);
      if (url.pathname.endsWith("/organisation/units") && !url.pathname.includes("/admin/")) return json({ items: organisationUnits });
      if (url.pathname.endsWith(`/admin/organisation/units/${organisationUnit("OSG_TEAM").id}`)) {
        body = JSON.parse(String(init.body));
        return reject ? json({ detail: "Name already exists" }, 409) : json({ ...organisationUnit("OSG_TEAM"), name: "OSG Operations Team", version: 2 });
      }
      throw new Error(`${init.method ?? "GET"} ${url.pathname}`);
    });
    const user = userEvent.setup();
    const view = renderApp("/organisation");
    const hierarchy = await screen.findByRole("list", { name: "Organisation hierarchy" });
    expect(screen.getByRole("link", { name: "User accounts" })).toBeInTheDocument();
    await user.click(within(hierarchy).getByRole("button", { name: "Rename OSG Team" }));
    const input = within(hierarchy).getByLabelText("New name for OSG Team");
    await user.clear(input);
    expect(within(hierarchy).getByRole("alert")).toHaveTextContent("at least two");
    await user.type(input, "OSG Operations Team");
    await user.click(within(hierarchy).getByRole("button", { name: "Save" }));
    expect(await within(hierarchy).findByRole("alert")).toHaveTextContent("Name already exists");
    reject = false;
    await user.click(within(hierarchy).getByRole("button", { name: "Save" }));
    expect((await within(hierarchy).findAllByText("OSG Operations Team")).length).toBeGreaterThan(0);
    expect(body).toEqual({ name: "OSG Operations Team", expectedVersion: 1 });
    await user.click(within(hierarchy).getByRole("button", { name: "Rename OSG Operations Team" }));
    await user.click(within(hierarchy).getByRole("button", { name: "Cancel" }));
    expect(within(hierarchy).queryByLabelText("New name for OSG Operations Team")).not.toBeInTheDocument();
    expect(await axe(view.container)).toHaveNoViolations();
  });

  it("keeps orphaned or self-parented units visible at the root", () => {
    const command = organisationUnit("DIGOC");
    const orphan = { ...command, id: "orphan", parentId: "missing" };
    const selfParented = { ...command, id: "self", parentId: "self" };
    const tree = buildOrganisationTree([
      organisationUnit("JIOC"),
      orphan,
      selfParented,
    ]);
    expect(tree.map((node) => node.id)).toEqual(["unit-jioc", "orphan", "self"]);
  });
});
