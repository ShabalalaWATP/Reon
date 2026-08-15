import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import type { ConfigurationVersion } from "../../lib/api/configurationTypes";
import { adminSession, enabledCapabilities, requesterSession } from "../../test/fixtures";
import {
  configurationPreview,
  configurationVersion,
  workflowDefinition,
} from "../../test/configurationFixtures";
import { json, mockFeatureFetch, mockFetch, renderApp } from "../../test/render";

function configurationHandler(
  current: () => ConfigurationVersion,
  update?: (next: ConfigurationVersion) => void,
) {
  return (url: URL, init: RequestInit) => {
    const method = init.method ?? "GET";
    if (url.pathname.endsWith("/auth/me")) return json(adminSession);
    if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
    if (url.pathname.endsWith("/admin/configuration/versions") && method === "GET")
      return json({ items: [current()] });
    if (url.pathname.endsWith("/workflow-definitions"))
      return json({ items: [workflowDefinition] });
    if (url.pathname.endsWith("/preview")) return json(configurationPreview);
    if (url.pathname.endsWith(`/versions/${current().id}`) && method === "GET")
      return json(current());
    if (url.pathname.endsWith(`/versions/${current().id}`) && method === "PUT") {
      const next = {
        ...current(),
        ...JSON.parse(String(init.body)),
        version: current().version + 1,
      };
      update?.(next);
      return json(next);
    }
    throw new Error(`${method} ${url.pathname}`);
  };
}

describe("configuration administration journey", () => {
  it("shows the effective-dated tree, bounded workflow and keyboard navigation", async () => {
    mockFeatureFetch(configurationHandler(() => configurationVersion));
    const user = userEvent.setup();
    const view = renderApp("/admin/configuration/cfg-2");
    expect(
      await screen.findByRole("heading", { name: "Organisation and workflow configuration" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Proposed changes", { selector: ".configuration-state" }),
    ).toBeInTheDocument();
    const rows = screen.getAllByRole("treeitem");
    expect(rows).toHaveLength(4);
    rows[0].focus();
    await user.keyboard("{End}");
    expect(rows[3]).toHaveFocus();
    await user.keyboard("{Home}");
    expect(rows[0]).toHaveFocus();
    await user.keyboard("{ArrowDown}");
    expect(rows[1]).toHaveFocus();
    await user.keyboard("{ArrowUp}");
    expect(rows[0]).toHaveFocus();
    await user.type(screen.getByLabelText("Search organisation"), "Northern Command");
    expect(screen.queryByRole("treeitem", { name: /Pine Team/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Show in tree" }));
    expect(screen.getByLabelText("Search organisation")).toHaveValue("");
    expect(screen.getByRole("heading", { name: "Pine Team" })).toBeInTheDocument();
    expect(
      screen.getByRole("navigation", { name: "Selected organisation path" }),
    ).toHaveTextContent(
      "Mist · MistNorthern Command · NORTHNorthern Ops Group · NORTH_OPSPine Team · PINE_TEAM",
    );
    expect(screen.getByText("Snapshot reference").parentElement).toHaveTextContent("b".repeat(64));
    expect(screen.getAllByText(/Outcomes fixed: approve, changes_required/)).toHaveLength(2);
    expect(await axe(view.container)).toHaveNoViolations();
  });

  it("saves a renamed unit as a complete optimistic draft replacement", async () => {
    let current = configurationVersion;
    let saved: Record<string, unknown> | undefined;
    mockFeatureFetch((url, init) => {
      if (url.pathname.endsWith(`/versions/${current.id}`) && init.method === "PUT") {
        saved = JSON.parse(String(init.body));
        current = { ...current, ...saved, version: current.version + 1 };
        return json(current);
      }
      return configurationHandler(() => current)(url, init);
    });
    const user = userEvent.setup();
    renderApp("/admin/configuration/cfg-2");
    await user.click(await screen.findByRole("treeitem", { name: /Pine Team/ }));
    await user.clear(screen.getByLabelText("New display name"));
    await user.type(screen.getByLabelText("New display name"), "Pine Delivery Team");
    await user.click(screen.getByRole("button", { name: "Save proposed change" }));
    await waitFor(() => expect(saved).toBeDefined());
    expect(saved).toMatchObject({
      expectedVersion: 1,
      units: expect.arrayContaining([
        expect.objectContaining({ unitId: "unit-team", name: "Pine Delivery Team" }),
      ]),
    });
    expect(saved?.candidateGroups).toEqual(configurationVersion.candidateGroups);
  });

  it("validates, submits, independently approves and activates one exact proposal", async () => {
    let current: ConfigurationVersion = configurationVersion;
    const actions: Array<{ action: string; body: Record<string, unknown> }> = [];
    mockFeatureFetch((url, init) => {
      const method = init.method ?? "GET";
      if (url.pathname.endsWith("/auth/me")) return json(adminSession);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/admin/configuration/versions") && method === "GET")
        return json({ items: [current] });
      if (url.pathname.endsWith("/workflow-definitions"))
        return json({ items: [workflowDefinition] });
      if (url.pathname.endsWith("/preview")) return json(configurationPreview);
      if (url.pathname.endsWith(`/versions/${current.id}`) && method === "GET")
        return json(current);
      for (const action of ["validate", "submit", "approve", "activate"] as const) {
        if (url.pathname.endsWith(`/${action}`)) {
          const body = JSON.parse(String(init.body));
          actions.push({ action, body });
          if (action === "validate")
            current = {
              ...current,
              status: "VALIDATED",
              validatedAt: "2026-08-07T10:00:00Z",
              version: 2,
              findings: [
                {
                  severity: "WARNING",
                  code: "TEAM_UNSTAFFED",
                  message: "Work will await staffing.",
                  path: "units.3",
                  unitId: "unit-team",
                },
              ],
            };
          if (action === "submit")
            current = {
              ...current,
              status: "AWAITING_APPROVAL",
              submittedAt: "2026-08-07T10:01:00Z",
              reason: body.reason as string,
              version: 3,
            };
          if (action === "approve")
            current = {
              ...current,
              approval: {
                actorUserId: adminSession.user.id,
                decision: "APPROVED",
                reviewedVersion: 3,
                snapshotDigest: "a".repeat(64),
                reason: body.reason as string,
                createdAt: "2026-08-07T10:02:00Z",
              },
              version: 4,
            };
          if (action === "activate")
            current = {
              ...current,
              status: "ACTIVE",
              activatedAt: "2026-08-07T10:03:00Z",
              reason: body.reason as string,
              version: 5,
            };
          return json(current);
        }
      }
      throw new Error(`${method} ${url.pathname}`);
    });
    const user = userEvent.setup();
    renderApp("/admin/configuration/cfg-2");
    await user.click(
      await screen.findByRole("button", { name: "Validate complete configuration" }),
    );
    expect(await screen.findByText("TEAM UNSTAFFED")).toBeInTheDocument();
    await screen.findByRole("button", { name: "Submit for independent approval" });
    await user.type(
      screen.getByRole("textbox", { name: /Decision reason/ }),
      "New branch is ready for controlled review.",
    );
    await user.click(screen.getByRole("button", { name: "Submit for independent approval" }));
    await screen.findByRole("button", { name: "Approve proposed changes" });
    await user.type(
      screen.getByRole("textbox", { name: /Decision reason/ }),
      "Independent review confirms the proposed changes.",
    );
    await user.click(screen.getByRole("button", { name: "Approve proposed changes" }));
    await screen.findByRole("button", { name: "Activate approved changes" });
    await user.type(
      screen.getByRole("textbox", { name: /Decision reason/ }),
      "Activate for new requests from the effective date.",
    );
    await user.click(screen.getByRole("button", { name: "Activate approved changes" }));
    expect(
      await screen.findByText("Current", { selector: ".configuration-state" }),
    ).toBeInTheDocument();
    expect(actions.map((item) => item.action)).toEqual([
      "validate",
      "submit",
      "approve",
      "activate",
    ]);
    expect(actions[0].body).toEqual({ expectedVersion: 1 });
    expect(actions[3].body).toMatchObject({
      expectedVersion: 4,
      reason: expect.stringContaining("Activate"),
    });
  });

  it("creates and immediately selects future proposed changes", async () => {
    let current: ConfigurationVersion = {
      ...configurationVersion,
      id: "cfg-1",
      sequence: 1,
      status: "ACTIVE",
    };
    let createdBody: Record<string, unknown> | undefined;
    mockFeatureFetch((url, init) => {
      const method = init.method ?? "GET";
      if (url.pathname.endsWith("/auth/me")) return json(adminSession);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/workflow-definitions"))
        return json({ items: [workflowDefinition] });
      if (url.pathname.endsWith("/preview")) return json({ ...configurationPreview, changes: [] });
      if (url.pathname.endsWith("/admin/configuration/versions") && method === "POST") {
        createdBody = JSON.parse(String(init.body));
        current = {
          ...configurationVersion,
          id: "cfg-3",
          sequence: 3,
          label: String(createdBody!.label),
        };
        return json(current, 201);
      }
      if (url.pathname.endsWith("/admin/configuration/versions")) return json({ items: [current] });
      if (url.pathname.endsWith(`/versions/${current.id}`)) return json(current);
      throw new Error(`${method} ${url.pathname}`);
    });
    const user = userEvent.setup();
    renderApp("/admin/configuration/cfg-1");
    await user.click(await screen.findByText("Propose changes from Northern branch changes"));
    await user.type(screen.getByLabelText("Change title"), "Autumn branch configuration");
    await user.type(screen.getByLabelText("Effective from"), "2026-10-01T09:30");
    await user.click(screen.getByRole("button", { name: "Create proposed changes" }));
    expect(
      await screen.findByText("Proposed changes", { selector: ".configuration-state" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Configuration history")).toHaveValue("cfg-3");
    expect(createdBody).toMatchObject({
      basedOnVersionId: "cfg-1",
      label: "Autumn branch configuration",
      effectiveFrom: new Date("2026-10-01T09:30").toISOString(),
    });
  });

  it("conceals configuration from non-administrators", async () => {
    let registryCalls = 0;
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/requests")) return json({ items: [] });
      if (url.pathname.includes("/admin/configuration")) registryCalls += 1;
      throw new Error(url.pathname);
    });
    renderApp("/admin/configuration");
    expect(await screen.findByRole("heading", { name: "No requests yet" })).toBeInTheDocument();
    expect(registryCalls).toBe(0);
  });
});
