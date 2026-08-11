import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import { enabledCapabilities, requesterSession } from "../../test/fixtures";
import { json, mockFeatureFetch, renderApp } from "../../test/render";

const calendarSession = { ...requesterSession, user: { ...requesterSession.user, id: "crioc-member", username: "admin75", displayName: "Willie Ormond", role: "INTAKE_TRIAGE" as const, scope: "CRIOC" } };
const calendarAccess = { teamId: "crioc", teamCode: "CRIOC", teamName: "CRIOC", unitKind: "ROOT" as const, workspacePosition: "MEMBER" as const, grantId: null, permissions: [], views: ["OVERVIEW", "QUEUE", "CALENDAR", "PEOPLE", "STATISTICS", "HANDOVER", "ACTIVITY"] };

describe("calendar event dialog", () => {
  it("opens one form from the toolbar or a calendar day, pre-fills the day and closes after creation", async () => {
    const writes: Array<Record<string, unknown>> = [];
    mockFeatureFetch(async (url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(calendarSession);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/team-workspaces")) return json({ items: [calendarAccess] });
      if (url.pathname.endsWith("/calendar") && (!init.method || init.method === "GET")) return json({ items: [] });
      if (url.pathname.endsWith("/calendar/events") && init.method === "POST") { writes.push(JSON.parse(String(init.body)) as Record<string, unknown>); return json({ eventId: "event-new", version: 1 }); }
      throw new Error(`Unexpected ${url.pathname}`);
    }, true, true, false);
    const user = userEvent.setup();
    const view = renderApp("/teams/crioc/calendar");
    const addButton = await screen.findByRole("button", { name: "Add event" });
    expect(screen.queryByRole("dialog", { name: "Add calendar event" })).not.toBeInTheDocument();

    await user.click(addButton);
    expect(await screen.findByRole("dialog", { name: "Add calendar event" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Add calendar activity" })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /Private appointment/ })).not.toBeChecked();
    expect(screen.getByText(/visible to other members of CRIOC/)).toBeInTheDocument();
    expect(await axe(view.container)).toHaveNoViolations();
    await user.click(screen.getByRole("button", { name: "Close Add calendar event" }));
    expect(addButton).toHaveFocus();

    const today = new Date();
    const dateLabel = new Intl.DateTimeFormat("en-GB", { dateStyle: "long" }).format(today);
    await user.click(screen.getByRole("button", { name: `Add event on ${dateLabel}` }));
    const localDate = new Date(today.getTime() - today.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
    expect(screen.getByLabelText(/^Starts/)).toHaveValue(`${localDate}T09:00`);
    await user.type(screen.getByLabelText(/^Title/), "Synthetic course");
    await user.type(screen.getByLabelText(/^Notes/), "A synthetic calendar event created from the selected day.");
    await user.click(screen.getByRole("button", { name: "Create event" }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0].visibility).toBe("TEAM_DETAIL");
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Add calendar event" })).not.toBeInTheDocument());

    await user.click(addButton);
    await user.click(screen.getByRole("checkbox", { name: /Private appointment/ }));
    expect(screen.getByText(/title and notes will be hidden/)).toBeInTheDocument();
    await user.type(screen.getByLabelText(/^Title/), "Private appointment");
    await user.type(screen.getByLabelText(/^Notes/), "Synthetic personal detail hidden from the team calendar.");
    await user.click(screen.getByRole("button", { name: "Create event" }));
    await waitFor(() => expect(writes).toHaveLength(2));
    expect(writes[1].visibility).toBe("PRIVATE");
  });
});
