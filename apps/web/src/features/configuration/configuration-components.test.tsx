import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ConfigurationDraftInput } from "../../lib/api/configurationTypes";
import { configurationVersion } from "../../test/configurationFixtures";
import { ConfigurationUnitForm } from "./ConfigurationUnitForm";

describe("configuration unit draft changes", () => {
  it("creates a team with bounded staffing and a stable parent edge", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "unit-new" });
    const save = vi.fn();
    const user = userEvent.setup();
    render(
      <ConfigurationUnitForm
        disabled={false}
        onSave={save}
        selectedId={null}
        version={configurationVersion}
      />,
    );
    await user.type(screen.getByLabelText("Stable code"), "CEDAR_TEAM");
    await user.type(screen.getByLabelText("Display name"), "Cedar Team");
    await user.selectOptions(screen.getByLabelText("Unit kind"), "TEAM");
    await user.selectOptions(screen.getByLabelText("Parent unit"), "unit-ops");
    await user.clear(screen.getByLabelText("Minimum Managers"));
    await user.type(screen.getByLabelText("Minimum Managers"), "1");
    await user.clear(screen.getByLabelText("Minimum Analysts"));
    await user.type(screen.getByLabelText("Minimum Analysts"), "3");
    await user.click(screen.getByRole("button", { name: "Save proposed change" }));
    const draft = save.mock.calls[0][0] as ConfigurationDraftInput;
    expect(draft.units.at(-1)).toMatchObject({
      unitId: "unit-new",
      kind: "TEAM",
      minimumManagers: 1,
      minimumAnalysts: 3,
    });
    expect(draft.edges.at(-1)).toMatchObject({
      parentUnitId: "unit-ops",
      childUnitId: "unit-new",
      effectiveUntil: null,
    });
  });

  it("moves and retires units without deleting their effective-dated history", async () => {
    const move = vi.fn();
    const user = userEvent.setup();
    const alternateOps = {
      ...configurationVersion.units[2],
      unitId: "unit-ops-alt",
      code: "ALT_OPS",
      name: "Alternate Ops",
    };
    const movableVersion = {
      ...configurationVersion,
      units: [...configurationVersion.units, alternateOps],
      edges: [
        ...configurationVersion.edges.map((edge) =>
          edge.childUnitId === "unit-team"
            ? { ...edge, effectiveFrom: "2026-08-01T09:00:00Z" }
            : edge,
        ),
        {
          parentUnitId: "unit-command",
          childUnitId: "unit-ops-alt",
          effectiveFrom: configurationVersion.effectiveFrom,
          effectiveUntil: null,
        },
      ],
    };
    const first = render(
      <ConfigurationUnitForm
        disabled={false}
        onSave={move}
        selectedId="unit-team"
        version={movableVersion}
      />,
    );
    await user.selectOptions(screen.getByLabelText("Change"), "MOVE");
    expect(screen.queryByRole("option", { name: /Northern Command/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /Northern Ops Group/ })).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Parent unit"), "unit-ops-alt");
    await user.click(screen.getByRole("button", { name: "Save proposed change" }));
    const moved = move.mock.calls[0][0] as ConfigurationDraftInput;
    expect(moved.edges.filter((edge) => edge.childUnitId === "unit-team")).toEqual([
      expect.objectContaining({
        parentUnitId: "unit-ops",
        effectiveUntil: configurationVersion.effectiveFrom,
      }),
      expect.objectContaining({ parentUnitId: "unit-ops-alt", effectiveUntil: null }),
    ]);
    first.unmount();
    const retire = vi.fn();
    render(
      <ConfigurationUnitForm
        disabled={false}
        onSave={retire}
        selectedId="unit-team"
        version={configurationVersion}
      />,
    );
    await user.selectOptions(screen.getByLabelText("Change"), "RETIRE");
    await user.type(screen.getByLabelText("Effective retirement"), "2026-10-01T12:00");
    await user.click(screen.getByRole("button", { name: "Save proposed change" }));
    const retired = retire.mock.calls[0][0] as ConfigurationDraftInput;
    expect(retired.units.find((unit) => unit.unitId === "unit-team")).toMatchObject({
      routingEnabled: true,
      effectiveUntil: new Date("2026-10-01T12:00").toISOString(),
    });
    expect(
      retired.edges.find((edge) => edge.childUnitId === "unit-team")?.effectiveUntil,
    ).toBeTruthy();
  });

  it("edits only the unit revision effective for the proposal", async () => {
    const save = vi.fn();
    const user = userEvent.setup();
    const current = configurationVersion.units[3];
    const historical = {
      ...current,
      name: "Historic Pine Team",
      effectiveFrom: "2025-01-01T00:00:00Z",
      effectiveUntil: "2026-01-01T00:00:00Z",
    };
    const active = { ...current, name: "Current Pine Team", effectiveFrom: "2026-01-01T00:00:00Z" };
    const version = {
      ...configurationVersion,
      units: [...configurationVersion.units.slice(0, 3), historical, active],
    };
    render(
      <ConfigurationUnitForm
        disabled={false}
        onSave={save}
        selectedId="unit-team"
        version={version}
      />,
    );
    expect(screen.getByLabelText("New display name")).toHaveValue("Current Pine Team");
    await user.clear(screen.getByLabelText("New display name"));
    await user.type(screen.getByLabelText("New display name"), "Future Pine Team");
    await user.click(screen.getByRole("button", { name: "Save proposed change" }));
    const units = (save.mock.calls[0][0] as ConfigurationDraftInput).units.filter(
      (unit) => unit.unitId === "unit-team",
    );
    expect(units).toContainEqual(historical);
    expect(units).toContainEqual({ ...active, effectiveUntil: configurationVersion.effectiveFrom });
    expect(units).toContainEqual({
      ...active,
      name: "Future Pine Team",
      effectiveFrom: configurationVersion.effectiveFrom,
    });
  });

  it("moves only the effective edge and preserves a future scheduled parent", async () => {
    const save = vi.fn();
    const user = userEvent.setup();
    const alternateOps = {
      ...configurationVersion.units[2],
      unitId: "unit-ops-alt",
      code: "ALT_OPS",
      name: "Alternate Ops",
    };
    const futureOps = {
      ...configurationVersion.units[2],
      unitId: "unit-ops-future",
      code: "FUTURE_OPS",
      name: "Future Ops",
    };
    const proposalAt = configurationVersion.effectiveFrom;
    const futureAt = "2026-12-01T00:00:00Z";
    const historicEdge = {
      parentUnitId: "unit-ops",
      childUnitId: "unit-team",
      effectiveFrom: "2025-01-01T00:00:00Z",
      effectiveUntil: "2026-01-01T00:00:00Z",
    };
    const currentEdge = {
      parentUnitId: "unit-ops",
      childUnitId: "unit-team",
      effectiveFrom: "2026-01-01T00:00:00Z",
      effectiveUntil: futureAt,
    };
    const futureEdge = {
      parentUnitId: "unit-ops-future",
      childUnitId: "unit-team",
      effectiveFrom: futureAt,
      effectiveUntil: null,
    };
    const version = {
      ...configurationVersion,
      units: [...configurationVersion.units, alternateOps, futureOps],
      edges: [
        ...configurationVersion.edges.filter((edge) => edge.childUnitId !== "unit-team"),
        historicEdge,
        currentEdge,
        futureEdge,
      ],
    };
    render(
      <ConfigurationUnitForm
        disabled={false}
        onSave={save}
        selectedId="unit-team"
        version={version}
      />,
    );
    await user.selectOptions(screen.getByLabelText("Change"), "MOVE");
    await user.selectOptions(screen.getByLabelText("Parent unit"), "unit-ops-alt");
    await user.click(screen.getByRole("button", { name: "Save proposed change" }));
    const edges = (save.mock.calls[0][0] as ConfigurationDraftInput).edges.filter(
      (edge) => edge.childUnitId === "unit-team",
    );
    expect(edges).toEqual([
      historicEdge,
      { ...currentEdge, effectiveUntil: proposalAt },
      futureEdge,
      {
        parentUnitId: "unit-ops-alt",
        childUnitId: "unit-team",
        effectiveFrom: proposalAt,
        effectiveUntil: futureAt,
      },
    ]);
  });

  it("retires the schedule effective at the requested time and removes later routing", async () => {
    const save = vi.fn();
    const user = userEvent.setup();
    const team = configurationVersion.units[3];
    const currentUntil = "2026-10-01T00:00:00Z";
    const retirementAt = "2026-12-01T00:00:00.000Z";
    const futureUnit = {
      ...team,
      name: "Scheduled Pine Team",
      effectiveFrom: currentUntil,
      effectiveUntil: null,
    };
    const currentEdge = { ...configurationVersion.edges[2], effectiveUntil: currentUntil };
    const futureEdge = {
      ...configurationVersion.edges[2],
      parentUnitId: "unit-ops",
      effectiveFrom: currentUntil,
    };
    const version = {
      ...configurationVersion,
      units: [
        ...configurationVersion.units.slice(0, 3),
        { ...team, effectiveUntil: currentUntil },
        futureUnit,
      ],
      edges: [...configurationVersion.edges.slice(0, 2), currentEdge, futureEdge],
    };
    render(
      <ConfigurationUnitForm
        disabled={false}
        onSave={save}
        selectedId="unit-team"
        version={version}
      />,
    );
    await user.selectOptions(screen.getByLabelText("Change"), "RETIRE");
    await user.type(screen.getByLabelText("Effective retirement"), "2026-12-01T00:00");
    await user.click(screen.getByRole("button", { name: "Save proposed change" }));
    const proposal = save.mock.calls[0][0] as ConfigurationDraftInput;
    expect(proposal.units.filter((unit) => unit.unitId === "unit-team")).toEqual([
      { ...team, effectiveUntil: currentUntil },
      { ...futureUnit, effectiveUntil: retirementAt },
    ]);
    expect(proposal.edges.filter((edge) => edge.childUnitId === "unit-team")).toEqual([
      currentEdge,
      { ...futureEdge, effectiveUntil: retirementAt },
    ]);
  });

  it("replaces a provisional move recorded with an equivalent timestamp offset", async () => {
    const save = vi.fn();
    const user = userEvent.setup();
    const alternateOps = {
      ...configurationVersion.units[2],
      unitId: "unit-ops-alt",
      code: "ALT_OPS",
      name: "Alternate Ops",
    };
    const version = {
      ...configurationVersion,
      units: [...configurationVersion.units, alternateOps],
      edges: [
        ...configurationVersion.edges.filter((edge) => edge.childUnitId !== "unit-team"),
        {
          parentUnitId: "unit-ops",
          childUnitId: "unit-team",
          effectiveFrom: configurationVersion.effectiveFrom.replace("Z", "+00:00"),
          effectiveUntil: null,
        },
      ],
    };
    render(
      <ConfigurationUnitForm
        disabled={false}
        onSave={save}
        selectedId="unit-team"
        version={version}
      />,
    );
    await user.selectOptions(screen.getByLabelText("Change"), "MOVE");
    await user.selectOptions(screen.getByLabelText("Parent unit"), "unit-ops-alt");
    await user.click(screen.getByRole("button", { name: "Save proposed change" }));
    expect(
      (save.mock.calls[0][0] as ConfigurationDraftInput).edges.filter(
        (edge) => edge.childUnitId === "unit-team",
      ),
    ).toEqual([
      {
        parentUnitId: "unit-ops-alt",
        childUnitId: "unit-team",
        effectiveFrom: configurationVersion.effectiveFrom,
        effectiveUntil: null,
      },
    ]);
  });
});
