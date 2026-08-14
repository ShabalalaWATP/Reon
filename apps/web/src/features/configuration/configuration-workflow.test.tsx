import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ConfigurationDraftInput } from "../../lib/api/configurationTypes";
import { configurationVersion, workflowDefinition } from "../../test/configurationFixtures";
import { ConfigurationUnitForm } from "./ConfigurationUnitForm";
import { WorkflowTemplateForm } from "./WorkflowTemplateForm";

describe("configuration mappings and workflow", () => {
  it("replaces the exact candidate-group purposes for team and routing units", async () => {
    const user = userEvent.setup();
    const teamSave = vi.fn();
    const first = render(
      <ConfigurationUnitForm
        disabled={false}
        onSave={teamSave}
        selectedId="unit-team"
        version={configurationVersion}
      />,
    );
    await user.selectOptions(screen.getByLabelText("Change"), "MAPPING");
    await user.clear(screen.getByLabelText("Manager candidate group"));
    await user.type(screen.getByLabelText("Manager candidate group"), "cedar-managers");
    await user.clear(screen.getByLabelText("Analyst candidate group"));
    await user.type(screen.getByLabelText("Analyst candidate group"), "cedar-analysts");
    await user.click(screen.getByRole("button", { name: "Save proposed change" }));
    expect(
      (teamSave.mock.calls[0][0] as ConfigurationDraftInput).candidateGroups.filter(
        (item) => item.unitId === "unit-team",
      ),
    ).toEqual([
      { unitId: "unit-team", purpose: "MANAGER", candidateGroup: "cedar-managers" },
      { unitId: "unit-team", purpose: "ANALYST", candidateGroup: "cedar-analysts" },
    ]);
    first.unmount();
    const routeSave = vi.fn();
    render(
      <ConfigurationUnitForm
        disabled={false}
        onSave={routeSave}
        selectedId="unit-command"
        version={configurationVersion}
      />,
    );
    await user.selectOptions(screen.getByLabelText("Change"), "MAPPING");
    await user.clear(screen.getByLabelText("Routing candidate group"));
    await user.type(screen.getByLabelText("Routing candidate group"), "cedar-routing");
    await user.click(screen.getByRole("button", { name: "Save proposed change" }));
    expect((routeSave.mock.calls[0][0] as ConfigurationDraftInput).candidateGroups).toContainEqual({
      unitId: "unit-command",
      purpose: "ROUTING",
      candidateGroup: "cedar-routing",
    });
  });

  it("saves only bounded workflow metadata and preserves fixed outcomes", async () => {
    const save = vi.fn();
    const user = userEvent.setup();
    const view = render(
      <WorkflowTemplateForm
        definitions={[workflowDefinition]}
        disabled={false}
        onSave={save}
        version={configurationVersion}
      />,
    );
    await user.clear(screen.getByLabelText("Service categories"));
    await user.type(
      screen.getByLabelText("Service categories"),
      "Advisory support\nOperational review",
    );
    await user.clear(screen.getByLabelText("Reminder days, comma separated"));
    await user.type(screen.getByLabelText("Reminder days, comma separated"), "7, 1, invalid, 7");
    await user.clear(screen.getByLabelText("Approved external-link domains"));
    await user.type(
      screen.getByLabelText("Approved external-link domains"),
      "PRODUCTS.EXAMPLE.TEST.\nproducts.example.test",
    );
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
    view.rerender(
      <WorkflowTemplateForm
        definitions={[]}
        disabled={false}
        onSave={save}
        version={configurationVersion}
      />,
    );
    expect(screen.getByRole("button", { name: "Save proposed workflow settings" })).toBeDisabled();
    expect(screen.getByText("No compatible deployed workflow is available.")).toBeInTheDocument();
  });
});
