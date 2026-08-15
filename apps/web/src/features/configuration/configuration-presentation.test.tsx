import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { configurationVersion } from "../../test/configurationFixtures";
import { ConfigurationBreadcrumbs } from "./ConfigurationBreadcrumbs";
import { ConfigurationTree } from "./ConfigurationTree";
import { ConfigurationUnitForm } from "./ConfigurationUnitForm";
import {
  commaSeparatedNumbers,
  configurationPath,
  configurationRows,
  draftFrom,
  filterConfigurationRows,
  lines,
  localDateTimeValue,
  unitState,
  validParentUnits,
} from "./configurationModel";

describe("configuration presentation model", () => {
  it("orders roots and orphans safely even when supplied edges contain a cycle", () => {
    const [root, command] = configurationVersion.units;
    expect(
      configurationRows(configurationVersion.units, configurationVersion.edges).map(
        (unit) => unit.unitId,
      ),
    ).toEqual(["unit-root", "unit-command", "unit-ops", "unit-team"]);
    expect(
      configurationRows(
        [root, command],
        [
          {
            parentUnitId: root.unitId,
            childUnitId: command.unitId,
            effectiveFrom: configurationVersion.effectiveFrom,
            effectiveUntil: null,
          },
          {
            parentUnitId: command.unitId,
            childUnitId: root.unitId,
            effectiveFrom: configurationVersion.effectiveFrom,
            effectiveUntil: null,
          },
        ],
      ),
    ).toHaveLength(2);
    expect(
      configurationRows(
        [root, command],
        [
          {
            parentUnitId: root.unitId,
            childUnitId: command.unitId,
            effectiveFrom: configurationVersion.effectiveFrom,
            effectiveUntil: configurationVersion.effectiveFrom,
          },
        ],
      ).map((unit) => unit.depth),
    ).toEqual([0, 0]);
  });

  it("clones drafts and describes routing, staffing and retirement states", () => {
    const draft = draftFrom(configurationVersion);
    draft.units[0].name = "Changed";
    draft.workflowTemplate.taskLabels.release = "Changed";
    expect(configurationVersion.units[0].name).toBe("Mist");
    expect(configurationVersion.workflowTemplate.taskLabels.release).toBe("Release");
    expect(
      unitState({ ...configurationVersion.units[0], effectiveUntil: "2026-10-01T00:00:00Z" }),
    ).toBe("Retiring");
    expect(unitState({ ...configurationVersion.units[0], routingEnabled: false })).toBe(
      "Routing paused",
    );
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

    expect(draftFrom(historical).workflowTemplate.coreFields).toEqual([
      "title",
      "service_category",
      "description",
      "question_to_answer",
      "desired_outcome",
      "background_context",
      "subject_area_or_location",
      "coverage_start",
      "coverage_end",
      "customer_urgency",
      "supported_activity_or_decision",
      "required_by",
      "required_by_reason",
      "preferred_deliverable_type",
      "success_criteria",
      "constraints_or_caveats",
      "supporting_information",
      "sensitivity",
      "handling_instructions",
    ]);
  });

  it("filters the hierarchy with ancestor context and builds cycle-safe breadcrumbs", () => {
    const rows = configurationRows(
      configurationVersion.units,
      configurationVersion.edges,
      configurationVersion.effectiveFrom,
    );
    expect(filterConfigurationRows(rows, "")).toBe(rows);
    expect(filterConfigurationRows(rows, "pine").map((row) => row.unitId)).toEqual([
      "unit-root",
      "unit-command",
      "unit-ops",
      "unit-team",
    ]);
    expect(filterConfigurationRows(rows, "missing")).toEqual([]);
    expect(
      configurationPath(
        configurationVersion.units,
        configurationVersion.edges,
        "unit-team",
        configurationVersion.effectiveFrom,
      ).map((unit) => unit.name),
    ).toEqual(["Mist", "Northern Command", "Northern Ops Group", "Pine Team"]);
    const cyclicEdges = [
      ...configurationVersion.edges,
      {
        parentUnitId: "unit-team",
        childUnitId: "unit-root",
        effectiveFrom: configurationVersion.effectiveFrom,
        effectiveUntil: null,
      },
    ];
    expect(
      configurationPath(
        configurationVersion.units,
        cyclicEdges,
        "unit-team",
        configurationVersion.effectiveFrom,
      ),
    ).toHaveLength(4);
    expect(
      configurationPath(
        configurationVersion.units,
        configurationVersion.edges,
        null,
        configurationVersion.effectiveFrom,
      ),
    ).toEqual([]);
    expect(
      configurationPath(
        configurationVersion.units,
        configurationVersion.edges,
        "missing",
        configurationVersion.effectiveFrom,
      ),
    ).toEqual([]);
  });

  it("shows only effective and structurally valid parents", () => {
    const retiredCommand = {
      ...configurationVersion.units[1],
      unitId: "retired-command",
      effectiveUntil: configurationVersion.effectiveFrom,
    };
    const pausedOps = {
      ...configurationVersion.units[2],
      unitId: "paused-ops",
      routingEnabled: false,
    };
    const units = [...configurationVersion.units, retiredCommand, pausedOps];
    expect(
      validParentUnits(
        units,
        configurationVersion.edges,
        "COMMAND",
        configurationVersion.effectiveFrom,
      ).map((unit) => unit.kind),
    ).toEqual(["ROOT"]);
    expect(
      validParentUnits(
        units,
        configurationVersion.edges,
        "OPS_GROUP",
        configurationVersion.effectiveFrom,
      ).map((unit) => unit.kind),
    ).toEqual(["COMMAND"]);
    expect(
      validParentUnits(
        units,
        configurationVersion.edges,
        "TEAM",
        configurationVersion.effectiveFrom,
        "unit-team",
      ),
    ).toEqual([]);
    expect(
      validParentUnits(
        units,
        configurationVersion.edges,
        "ROOT",
        configurationVersion.effectiveFrom,
      ),
    ).toEqual([]);
  });

  it("searches the rendered tree and exposes selected-unit breadcrumbs", async () => {
    const user = userEvent.setup();
    const select = vi.fn();
    function SearchableTree() {
      const [search, setSearch] = useState("");
      return (
        <ConfigurationTree
          edges={configurationVersion.edges}
          effectiveAt={configurationVersion.effectiveFrom}
          onSearchChange={setSearch}
          onSelect={select}
          search={search}
          selectedId={null}
          units={configurationVersion.units}
        />
      );
    }
    const view = render(
      <>
        <SearchableTree />
        <ConfigurationBreadcrumbs
          edges={configurationVersion.edges}
          effectiveAt={configurationVersion.effectiveFrom}
          onSelect={select}
          selectedId="unit-team"
          units={configurationVersion.units}
        />
      </>,
    );
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
    expect(
      view.container.querySelector("nav[aria-label='Selected organisation path']"),
    ).toBeInTheDocument();
  });

  it("renders the empty hierarchy state", () => {
    render(
      <ConfigurationTree
        edges={[]}
        effectiveAt={configurationVersion.effectiveFrom}
        onSearchChange={vi.fn()}
        onSelect={vi.fn()}
        search=""
        selectedId={null}
        units={[]}
      />,
    );
    expect(screen.getByText("No organisation units have been configured.")).toBeInTheDocument();
  });

  it("explains when a move has no alternative valid parent", async () => {
    const user = userEvent.setup();
    render(
      <ConfigurationUnitForm
        disabled={false}
        onSave={vi.fn()}
        selectedId="unit-team"
        version={configurationVersion}
      />,
    );
    await user.selectOptions(screen.getByLabelText("Change"), "MOVE");
    expect(screen.getByText("No structurally valid parent is available.")).toBeInTheDocument();
    expect(screen.getByLabelText("Parent unit")).toHaveValue("");
  });

  it("renders the breadcrumb orientation state before a unit is selected", () => {
    render(
      <ConfigurationBreadcrumbs
        edges={configurationVersion.edges}
        effectiveAt={configurationVersion.effectiveFrom}
        onSelect={vi.fn()}
        selectedId={null}
        units={configurationVersion.units}
      />,
    );
    expect(screen.getByText("Select a unit to see its organisational path.")).toBeInTheDocument();
  });
});
