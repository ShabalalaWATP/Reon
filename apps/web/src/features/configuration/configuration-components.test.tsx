import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ConfigurationDraftInput } from "../../lib/api/configurationTypes";
import { configurationVersion, workflowDefinition } from "../../test/configurationFixtures";
import { ConfigurationTree } from "./ConfigurationTree";
import { ConfigurationUnitForm } from "./ConfigurationUnitForm";
import { WorkflowTemplateForm } from "./WorkflowTemplateForm";
import { commaSeparatedNumbers, configurationRows, draftFrom, lines, unitState } from "./configurationModel";

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
    await user.click(screen.getByRole("button", { name: "Save draft change" }));
    const draft = save.mock.calls[0][0] as ConfigurationDraftInput;
    expect(draft.units.at(-1)).toMatchObject({ unitId: "unit-new", kind: "TEAM", minimumManagers: 1, minimumAnalysts: 3 });
    expect(draft.edges.at(-1)).toMatchObject({ parentUnitId: "unit-ops", childUnitId: "unit-new", effectiveUntil: null });
  });

  it("moves and retires units without deleting their effective-dated history", async () => {
    const move = vi.fn();
    const user = userEvent.setup();
    const first = render(<ConfigurationUnitForm disabled={false} onSave={move} selectedId="unit-team" version={configurationVersion} />);
    await user.selectOptions(screen.getByLabelText("Change"), "MOVE");
    await user.selectOptions(screen.getByLabelText("Parent unit"), "unit-command");
    await user.click(screen.getByRole("button", { name: "Save draft change" }));
    const moved = move.mock.calls[0][0] as ConfigurationDraftInput;
    expect(moved.edges.filter((edge) => edge.childUnitId === "unit-team")).toEqual([
      expect.objectContaining({ parentUnitId: "unit-ops", effectiveUntil: configurationVersion.effectiveFrom }),
      expect.objectContaining({ parentUnitId: "unit-command", effectiveUntil: null }),
    ]);
    first.unmount();
    const retire = vi.fn();
    render(<ConfigurationUnitForm disabled={false} onSave={retire} selectedId="unit-team" version={configurationVersion} />);
    await user.selectOptions(screen.getByLabelText("Change"), "RETIRE");
    await user.type(screen.getByLabelText("Effective retirement"), "2026-10-01T12:00");
    await user.click(screen.getByRole("button", { name: "Save draft change" }));
    const retired = retire.mock.calls[0][0] as ConfigurationDraftInput;
    expect(retired.units.find((unit) => unit.unitId === "unit-team")).toMatchObject({ routingEnabled: false, effectiveUntil: new Date("2026-10-01T12:00").toISOString() });
    expect(retired.edges.find((edge) => edge.childUnitId === "unit-team")?.effectiveUntil).toBeTruthy();
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
    await user.click(screen.getByRole("button", { name: "Save draft change" }));
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
    await user.click(screen.getByRole("button", { name: "Save draft change" }));
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
    await user.click(screen.getByRole("button", { name: "Save template draft" }));
    const template = (save.mock.calls[0][0] as ConfigurationDraftInput).workflowTemplate;
    expect(template.serviceCategories).toEqual(["Advisory support", "Operational review"]);
    expect(template.reminderDays).toEqual([1, 7]);
    expect(template.approvedLinkDomains).toEqual(["products.example.test"]);
    expect(template.artefactTypes).toEqual(["LEGACY_TEXT", "PDF", "DOCX"]);
    expect(template.allowedOutcomes).toEqual(configurationVersion.workflowTemplate.allowedOutcomes);
    view.rerender(<WorkflowTemplateForm definitions={[]} disabled={false} onSave={save} version={configurationVersion} />);
    expect(screen.getByRole("button", { name: "Save template draft" })).toBeDisabled();
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
  });

  it("renders the empty hierarchy state", () => {
    render(<ConfigurationTree edges={[]} onSelect={vi.fn()} selectedId={null} units={[]} />);
    expect(screen.getByText("This draft has no organisation units.")).toBeInTheDocument();
  });
});
