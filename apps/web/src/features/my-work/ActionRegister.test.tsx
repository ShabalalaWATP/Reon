import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import type { PersonalAction } from "../../lib/api/actionNotificationTypes";
import { ActionRegister } from "./ActionRegister";

const action: PersonalAction = {
  id: "action",
  section: "WAITING",
  actionAccess: "PERSONAL",
  actionType: "CUSTOMER_INPUT",
  sourceType: "REQUEST",
  reference: "ISR-200",
  title: "Waiting for response",
  currentOwner: null,
  requiredBy: null,
  ageDays: 0,
  lastChangedAt: "2026-08-07T09:00:00Z",
  deepLink: null,
  sourceVersion: 1,
  isStale: false,
};

describe("ActionRegister", () => {
  it("renders a minimal configured register without leaking omitted fields", () => {
    render(<MemoryRouter><ActionRegister columns={["CURRENT_OWNER"]} items={[action]} label="Waiting action register" /></MemoryRouter>);
    expect(screen.getByRole("region", { name: "Waiting action register" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Current owner" })).toBeInTheDocument();
    expect(screen.getByText("Unassigned")).toBeInTheDocument();
    expect(screen.getByText("Access ended")).toBeInTheDocument();
    expect(screen.queryByText("ISR-200")).not.toBeInTheDocument();
    expect(screen.queryByText("Waiting for response")).not.toBeInTheDocument();
  });

  it("distinguishes shared unit responsibility from personal ownership", () => {
    render(<MemoryRouter><ActionRegister columns={["TITLE", "CURRENT_OWNER"]} items={[{
      ...action,
      actionAccess: "SHARED",
      actionType: "CHOOSE_OPS_GROUP",
      currentOwner: "DIGOC · Awaiting owner",
    }]} label="Incoming request register" /></MemoryRouter>);
    expect(screen.getByText("New request requires attention")).toBeInTheDocument();
    expect(screen.getByText("Available to DIGOC")).toBeInTheDocument();
    expect(screen.getByText("DIGOC · Awaiting owner")).toBeInTheDocument();
  });
});
