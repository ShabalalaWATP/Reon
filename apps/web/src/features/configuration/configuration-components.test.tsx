import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import type { ConfigurationDraftInput } from "../../lib/api/configurationTypes";
import { configurationVersion, workflowDefinition } from "../../test/configurationFixtures";
import { ConfigurationBreadcrumbs } from "./ConfigurationBreadcrumbs";
import { ConfigurationTree } from "./ConfigurationTree";
import { ConfigurationUnitForm } from "./ConfigurationUnitForm";
import { WorkflowTemplateForm } from "./WorkflowTemplateForm";
import { commaSeparatedNumbers, configurationPath, configurationRows, currentCoreRequestFields, draftFrom, filterConfigurationRows, lines, localDateTimeValue, unitState, validParentUnits } from "./configurationModel";

describe("configuration draft editors", () => {
  it("creates a team with bounded staffing and a stable parent edge", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "unit-new" });
    const save = vi.fn();
    const user = userEvent.setup();
    render(<ConfigurationUnitForm disabled={false} onSave={save} selectedId={null} version={configurationVersion} />);
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
    expect(draft.units.at(-1)).toMatchObject({ unitId: "unit-new", kind: "TEAM", minimumManagers: 1, minimumAnalysts: 3 });
    expect(draft.edges.at(-1)).toMatchObject({ parentUnitId: "unit-ops", childUnitId: "unit-new", effectiveUntil: null });
  });

  it("moves and retires units without deleting their effective-dated history", async () => {
    const move = vi.fn();
    const user = userEvent.setup();
    const alternateOps = { ...configurationVersion.units[2], unitId: "unit-ops-alt", code: "ALT_OPS", name: "Alternate Ops" };
    const movableVersion = {
      ...configurationVersion,
      units: [...configurationVersion.units, alternateOps],
      edges: [
        ...configurationVersion.edges.map((edge) => edge.childUnitId === "unit-team" ? { ...edge, effectiveFrom: "2026-08-01T09:00:00Z" } : edge),
        { parentUnitId: "unit-command", childUnitId: "unit-ops-alt", effectiveFrom: configurationVersion.effectiveFrom, effectiveUntil: null },
      ],
    };
    const first = render(<ConfigurationUnitForm disabled={false} onSave={move} selectedId="unit-team" version={movableVersion} />);
    await user.selectOptions(screen.getByLabelText("Change"), "MOVE");
    expect(screen.queryByRole("option", { name: /Northern Command/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /Northern Ops Group/ })).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Parent unit"), "unit-ops-alt");
    await user.click(screen.getByRole("button", { name: "Save proposed change" }));
    const moved = move.mock.calls[0][0] as ConfigurationDraftInput;
    expect(moved.edges.filter((edge) => edge.childUnitId === "unit-team")).toEqual([
      expect.objectContaining({ parentUnitId: "unit-ops", effectiveUntil: configurationVersion.effectiveFrom }),
      expect.objectContaining({ parentUnitId: "unit-ops-alt", effectiveUntil: null }),
    ]);
    first.unmount();
    const retire = vi.fn();
    render(<ConfigurationUnitForm disabled={false} onSave={retire} selectedId="unit-team" version={configurationVersion} />);
    await user.selectOptions(screen.getByLabelText("Change"), "RETIRE");
    await user.type(screen.getByLabelText("Effective retirement"), "2026-10-01T12:00");
    await user.click(screen.getByRole("button", { name: "Save proposed change" }));
    const retired = retire.mock.calls[0][0] as ConfigurationDraftInput;
    expect(retired.units.find((unit) => unit.unitId === "unit-team")).toMatchObject({ routingEnabled: true, effectiveUntil: new Date("2026-10-01T12:00").toISOString() });
    expect(retired.edges.find((edge) => edge.childUnitId === "unit-team")?.effectiveUntil).toBeTruthy();
  });

  it("edits only the unit revision effective for the proposal", async () => {
    const save = vi.fn();
    const user = userEvent.setup();
    const current = configurationVersion.units[3];
    const historical = { ...current, name: "Historic Pine Team", effectiveFrom: "2025-01-01T00:00:00Z", effectiveUntil: "2026-01-01T00:00:00Z" };
    const active = { ...current, name: "Current Pine Team", effectiveFrom: "2026-01-01T00:00:00Z" };
    const version = { ...configurationVersion, units: [...configurationVersion.units.slice(0, 3), historical, active] };
    render(<ConfigurationUnitForm disabled={false} onSave={save} selectedId="unit-team" version={version} />);
    expect(screen.getByLabelText("New display name")).toHaveValue("Current Pine Team");
    await user.clear(screen.getByLabelText("New display name"));
    await user.type(screen.getByLabelText("New display name"), "Future Pine Team");
    await user.click(screen.getByRole("button", { name: "Save proposed change" }));
    const units = (save.mock.calls[0][0] as ConfigurationDraftInput).units.filter((unit) => unit.unitId === "unit-team");
    expect(units).toContainEqual(historical);
    expect(units).toContainEqual({ ...active, effectiveUntil: configurationVersion.effectiveFrom });
    expect(units).toContainEqual({ ...active, name: "Future Pine Team", effectiveFrom: configurationVersion.effectiveFrom });
  });

  it("moves only the effective edge and preserves a future scheduled parent", async () => {
    const save = vi.fn();
    const user = userEvent.setup();
    const alternateOps = { ...configurationVersion.units[2], unitId: "unit-ops-alt", code: "ALT_OPS", name: "Alternate Ops" };
    const futureOps = { ...configurationVersion.units[2], unitId: "unit-ops-future", code: "FUTURE_OPS", name: "Future Ops" };
    const proposalAt = configurationVersion.effectiveFrom;
    const futureAt = "2026-12-01T00:00:00Z";
    const historicEdge = { parentUnitId: "unit-ops", childUnitId: "unit-team", effectiveFrom: "2025-01-01T00:00:00Z", effectiveUntil: "2026-01-01T00:00:00Z" };
    const currentEdge = { parentUnitId: "unit-ops", childUnitId: "unit-team", effectiveFrom: "2026-01-01T00:00:00Z", effectiveUntil: futureAt };
    const futureEdge = { parentUnitId: "unit-ops-future", childUnitId: "unit-team", effectiveFrom: futureAt, effectiveUntil: null };
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
    render(<ConfigurationUnitForm disabled={false} onSave={save} selectedId="unit-team" version={version} />);
    await user.selectOptions(screen.getByLabelText("Change"), "MOVE");
    await user.selectOptions(screen.getByLabelText("Parent unit"), "unit-ops-alt");
    await user.click(screen.getByRole("button", { name: "Save proposed change" }));
    const edges = (save.mock.calls[0][0] as ConfigurationDraftInput).edges.filter((edge) => edge.childUnitId === "unit-team");
    expect(edges).toEqual([
      historicEdge,
      { ...currentEdge, effectiveUntil: proposalAt },
      futureEdge,
      { parentUnitId: "unit-ops-alt", childUnitId: "unit-team", effectiveFrom: proposalAt, effectiveUntil: futureAt },
    ]);
  });

  it("retires the schedule effective at the requested time and removes later routing", async () => {
    const save = vi.fn();
    const user = userEvent.setup();
    const team = configurationVersion.units[3];
    const currentUntil = "2026-10-01T00:00:00Z";
    const retirementAt = "2026-12-01T00:00:00.000Z";
    const futureUnit = { ...team, name: "Scheduled Pine Team", effectiveFrom: currentUntil, effectiveUntil: null };
    const currentEdge = { ...configurationVersion.edges[2], effectiveUntil: currentUntil };
    const futureEdge = { ...configurationVersion.edges[2], parentUnitId: "unit-ops", effectiveFrom: currentUntil };
    const version = {
      ...configurationVersion,
      units: [...configurationVersion.units.slice(0, 3), { ...team, effectiveUntil: currentUntil }, futureUnit],
      edges: [...configurationVersion.edges.slice(0, 2), currentEdge, futureEdge],
    };
    render(<ConfigurationUnitForm disabled={false} onSave={save} selectedId="unit-team" version={version} />);
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
    const alternateOps = { ...configurationVersion.units[2], unitId: "unit-ops-alt", code: "ALT_OPS", name: "Alternate Ops" };
    const version = {
      ...configurationVersion,
      units: [...configurationVersion.units, alternateOps],
      edges: [
        ...configurationVersion.edges.filter((edge) => edge.childUnitId !== "unit-team"),
        { parentUnitId: "unit-ops", childUnitId: "unit-team", effectiveFrom: configurationVersion.effectiveFrom.replace("Z", "+00:00"), effectiveUntil: null },
      ],
    };
    render(<ConfigurationUnitForm disabled={false} onSave={save} selectedId="unit-team" version={version} />);
    await user.selectOptions(screen.getByLabelText("Change"), "MOVE");
    await user.selectOptions(screen.getByLabelText("Parent unit"), "unit-ops-alt");
    await user.click(screen.getByRole("button", { name: "Save proposed change" }));
    expect((save.mock.calls[0][0] as ConfigurationDraftInput).edges.filter((edge) => edge.childUnitId === "unit-team")).toEqual([
      { parentUnitId: "unit-ops-alt", childUnitId: "unit-team", effectiveFrom: configurationVersion.effectiveFrom, effectiveUntil: null },
    ]);
  });

  it("replaces the exact candidate-group purposes for team and routing units", async () => {
    const user = userEvent.setup();
    const teamSave = vi.fn();
    const first = render(<ConfigurationUnitForm disabled={false} onSave={teamSave} selectedId="unit-team" version={configurationVersion} />);
    await user.selectOptions(screen.getByLabelText("Change"), "MAPPING");
    await user.clear(screen.getByLabelText("Manager candidate group"));
    await user.type(screen.getByLabelText("Manager candidate group"), "cedar-managers");
    await user.clear(screen.getByLabelText("Analyst candidate group"));
    await user.type(screen.getByLabelText("Analyst candidate group"), "cedar-analysts");
    await user.click(screen.getByRole("button", { name: "Save proposed change" }));
    expect((teamSave.mock.calls[0][0] as ConfigurationDraftInput).candidateGroups.filter((item) => item.unitId === "unit-team")).toEqual([
      { unitId: "unit-team", purpose: "MANAGER", candidateGroup: "cedar-managers" },
      { unitId: "unit-team", purpose: "ANALYST", candidateGroup: "cedar-analysts" },
    ]);
    first.unmount();
    const routeSave = vi.fn();
    render(<ConfigurationUnitForm disabled={false} onSave={routeSave} selectedId="unit-command" version={configurationVersion} />);
    await user.selectOptions(screen.getByLabelText("Change"), "MAPPING");
    await user.clear(screen.getByLabelText("Routing candidate group"));
    await user.type(screen.getByLabelText("Routing candidate group"), "cedar-routing");
    await user.click(screen.getByRole("button", { name: "Save proposed change" }));
    expect((routeSave.mock.calls[0][0] as ConfigurationDraftInput).candidateGroups).toContainEqual({ unitId: "unit-command", purpose: "ROUTING", candidateGroup: "cedar-routing" });
  });

  it("saves only bounded workflow metadata and preserves fixed outcomes", async () => {
    const save = vi.fn();
    const user = userEvent.setup();
    const view = render(<WorkflowTemplateForm definitions={[workflowDefinition]} disabled={false} onSave={save} version={configurationVersion} />);
    await user.clear(screen.getByLabelText("Service categories"));
    await user.type(screen.getByLabelText("Service categories"), "Advisory support\nOperational review");
    await user.clear(screen.getByLabelText("Reminder days, comma separated"));
    await user.type(screen.getByLabelText("Reminder days, comma separated"), "7, 1, invalid, 7");
    await user.clear(screen.getByLabelText("Approved external-link domains"));
    await user.type(screen.getByLabelText("Approved external-link domains"), "PRODUCTS.EXAMPLE.TEST.\nproducts.example.test");
    await user.click(screen.getByLabelText("PPTX"));
    await user.clear(screen.getByDisplayValue("Quality review"));
    await user.type(screen.getByDisplayValue(""), "Quality and release review");
    await user.click(screen.getByRole("button", { name: "Save proposed workflow settings" }));
    const template = (save.mock.calls[0][0] as ConfigurationDraftInput).workflowTemplate;
    expect(template.serviceCategories).toEqual(["Advisory support", "Operational review"]);
    expect(template.reminderDays).toEqual([1, 7]);
    expect(template.approvedLinkDomains).toEqual(["products.example.test"]);
    expect(template.artefactTypes).toEqual(["LEGACY_TEXT", "PDF", "DOCX"]);
    expect(template.allowedOutcomes).toEqual(configurationVersion.workflowTemplate.allowedOutcomes);
    view.rerender(<WorkflowTemplateForm definitions={[]} disabled={false} onSave={save} version={configurationVersion} />);
    expect(screen.getByRole("button", { name: "Save proposed workflow settings" })).toBeDisabled();
    expect(screen.getByText("No compatible deployed workflow is available.")).toBeInTheDocument();
  });
});

describe("configuration presentation model", () => {
  it("orders roots and orphans safely even when supplied edges contain a cycle", () => {
    const [root, command] = configurationVersion.units;
    expect(configurationRows(configurationVersion.units, configurationVersion.edges).map((unit) => unit.unitId)).toEqual(["unit-root", "unit-command", "unit-ops", "unit-team"]);
    expect(configurationRows([root, command], [
      { parentUnitId: root.unitId, childUnitId: command.unitId, effectiveFrom: configurationVersion.effectiveFrom, effectiveUntil: null },
      { parentUnitId: command.unitId, childUnitId: root.unitId, effectiveFrom: configurationVersion.effectiveFrom, effectiveUntil: null },
    ])).toHaveLength(2);
    expect(configurationRows([root, command], [{ parentUnitId: root.unitId, childUnitId: command.unitId, effectiveFrom: configurationVersion.effectiveFrom, effectiveUntil: configurationVersion.effectiveFrom }]).map((unit) => unit.depth)).toEqual([0, 0]);
  });

  it("clones drafts and describes routing, staffing and retirement states", () => {
    const draft = draftFrom(configurationVersion);
    draft.units[0].name = "Changed";
    draft.workflowTemplate.taskLabels.release = "Changed";
    expect(configurationVersion.units[0].name).toBe("ISTARI");
    expect(configurationVersion.workflowTemplate.taskLabels.release).toBe("Release");
    expect(unitState({ ...configurationVersion.units[0], effectiveUntil: "2026-10-01T00:00:00Z" })).toBe("Retiring");
    expect(unitState({ ...configurationVersion.units[0], routingEnabled: false })).toBe("Routing paused");
    expect(unitState(configurationVersion.units[3])).toContain("1 Manager");
    expect(unitState(configurationVersion.units[0])).toBe("Routing enabled");
    expect(lines(" one \n\n two ")).toEqual(["one", "two"]);
    expect(commaSeparatedNumbers("1, bad, 3.5, 4")).toEqual([1, 4]);
    const localDate = new Date("2026-08-07T12:34:56Z");
    vi.spyOn(localDate, "getTimezoneOffset").mockReturnValue(-60);
    expect(localDateTimeValue(localDate)).toBe("2026-08-07T13:34");
  });

  it("upgrades historical fixed intake fields when preparing a successor", () => {
    const historical = {
      ...configurationVersion,
      workflowTemplate: {
        ...configurationVersion.workflowTemplate,
        coreFields: ["title", "requesting_business_area", "intended_recipients"],
      },
    };

    expect(draftFrom(historical).workflowTemplate.coreFields).toEqual(
      currentCoreRequestFields,
    );
  });

  it("filters the hierarchy with ancestor context and builds cycle-safe breadcrumbs", () => {
    const rows = configurationRows(configurationVersion.units, configurationVersion.edges, configurationVersion.effectiveFrom);
    expect(filterConfigurationRows(rows, "")).toBe(rows);
    expect(filterConfigurationRows(rows, "pine").map((row) => row.unitId)).toEqual(["unit-root", "unit-command", "unit-ops", "unit-team"]);
    expect(filterConfigurationRows(rows, "missing")).toEqual([]);
    expect(configurationPath(configurationVersion.units, configurationVersion.edges, "unit-team", configurationVersion.effectiveFrom).map((unit) => unit.name)).toEqual(["ISTARI", "Northern Command", "Northern Ops Group", "Pine Team"]);
    const cyclicEdges = [...configurationVersion.edges, { parentUnitId: "unit-team", childUnitId: "unit-root", effectiveFrom: configurationVersion.effectiveFrom, effectiveUntil: null }];
    expect(configurationPath(configurationVersion.units, cyclicEdges, "unit-team", configurationVersion.effectiveFrom)).toHaveLength(4);
    expect(configurationPath(configurationVersion.units, configurationVersion.edges, null, configurationVersion.effectiveFrom)).toEqual([]);
    expect(configurationPath(configurationVersion.units, configurationVersion.edges, "missing", configurationVersion.effectiveFrom)).toEqual([]);
  });

  it("shows only effective and structurally valid parents", () => {
    const retiredCommand = { ...configurationVersion.units[1], unitId: "retired-command", effectiveUntil: configurationVersion.effectiveFrom };
    const pausedOps = { ...configurationVersion.units[2], unitId: "paused-ops", routingEnabled: false };
    const units = [...configurationVersion.units, retiredCommand, pausedOps];
    expect(validParentUnits(units, configurationVersion.edges, "COMMAND", configurationVersion.effectiveFrom).map((unit) => unit.kind)).toEqual(["ROOT"]);
    expect(validParentUnits(units, configurationVersion.edges, "OPS_GROUP", configurationVersion.effectiveFrom).map((unit) => unit.kind)).toEqual(["COMMAND"]);
    expect(validParentUnits(units, configurationVersion.edges, "TEAM", configurationVersion.effectiveFrom, "unit-team")).toEqual([]);
    expect(validParentUnits(units, configurationVersion.edges, "ROOT", configurationVersion.effectiveFrom)).toEqual([]);
  });

  it("searches the rendered tree and exposes selected-unit breadcrumbs", async () => {
    const user = userEvent.setup();
    const select = vi.fn();
    function SearchableTree() {
      const [search, setSearch] = useState("");
      return <ConfigurationTree edges={configurationVersion.edges} effectiveAt={configurationVersion.effectiveFrom} onSearchChange={setSearch} onSelect={select} search={search} selectedId={null} units={configurationVersion.units} />;
    }
    const view = render(<><SearchableTree /><ConfigurationBreadcrumbs edges={configurationVersion.edges} effectiveAt={configurationVersion.effectiveFrom} onSelect={select} selectedId="unit-team" units={configurationVersion.units} /></>);
    await user.type(screen.getByLabelText("Search organisation"), "OPS GROUP");
    expect(screen.getAllByRole("treeitem")).toHaveLength(3);
    expect(screen.getByText("1 matching units, with organisational context")).toBeInTheDocument();
    const filteredRows = screen.getAllByRole("treeitem");
    filteredRows[0].focus();
    await user.keyboard("{End}");
    expect(filteredRows.at(-1)).toHaveFocus();
    await user.clear(screen.getByLabelText("Search organisation"));
    await user.type(screen.getByLabelText("Search organisation"), "not present");
    expect(screen.getByText(/No organisation units match/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear organisation search" }));
    expect(screen.getAllByRole("treeitem")).toHaveLength(4);
    await user.click(screen.getByRole("button", { name: /^Northern Command ·/ }));
    expect(select).toHaveBeenCalledWith("unit-command");
    expect(view.container.querySelector("nav[aria-label='Selected organisation path']")).toBeInTheDocument();
  });

  it("renders the empty hierarchy state", () => {
    render(<ConfigurationTree edges={[]} effectiveAt={configurationVersion.effectiveFrom} onSearchChange={vi.fn()} onSelect={vi.fn()} search="" selectedId={null} units={[]} />);
    expect(screen.getByText("No organisation units have been configured.")).toBeInTheDocument();
  });

  it("explains when a move has no alternative valid parent", async () => {
    const user = userEvent.setup();
    render(<ConfigurationUnitForm disabled={false} onSave={vi.fn()} selectedId="unit-team" version={configurationVersion} />);
    await user.selectOptions(screen.getByLabelText("Change"), "MOVE");
    expect(screen.getByText("No structurally valid parent is available.")).toBeInTheDocument();
    expect(screen.getByLabelText("Parent unit")).toHaveValue("");
  });

  it("renders the breadcrumb orientation state before a unit is selected", () => {
    render(<ConfigurationBreadcrumbs edges={configurationVersion.edges} effectiveAt={configurationVersion.effectiveFrom} onSelect={vi.fn()} selectedId={null} units={configurationVersion.units} />);
    expect(screen.getByText("Select a unit to see its organisational path.")).toBeInTheDocument();
  });
});
