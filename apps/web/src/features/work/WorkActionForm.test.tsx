import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";

import { organisationChildren, requestDetail, workItem } from "../../test/fixtures";
import type { WorkAction } from "../../lib/api/types";
import type { SpecialistOptions } from "./EligibleSpecialistField";
import type { RoutingOptions } from "./RoutingDestinationField";
import { WorkActionForm } from "./WorkActionForm";
import { WorkActionPanel } from "./WorkActionPanel";

const readySpecialists: SpecialistOptions = {
  items: [
    { id: "specialist-1", displayName: "Aisha Rahman" },
    { id: "specialist-2", displayName: "Euan Fraser" },
  ],
  onRetry: vi.fn(),
  status: "ready",
};
const readyRouting: RoutingOptions = {
  items: organisationChildren("JIOC"),
  onRetry: vi.fn(),
  status: "ready",
};

describe("work action controls", () => {
  it.each([
    ["request_information", "Reason"],
    ["send_to_allocation", "Routing note"],
    ["progress", "Confirmed category"],
    ["allocate", "Destination unit"],
    ["assign", "Team Analyst"],
    ["submit", "Product title"],
    ["provide_information", "Additional information"],
    ["request_clarification", "Question for the Customer"],
    ["provide_clarification", "Information for the Analyst"],
    ["release", "Dissemination recipients"],
  ] as const)("renders fields for %s", (action, label) => {
    render(
      <WorkActionForm
        actions={[action]}
        disabled={false}
        onSubmit={vi.fn()}
        routingOptions={readyRouting}
        specialistOptions={readySpecialists}
      />,
    );
    expect(screen.getByLabelText(label)).toBeInTheDocument();
  });

  it("renders fieldless approval and submits it", async () => {
    const submit = vi.fn<(action: WorkAction) => void>();
    const user = userEvent.setup();
    render(<WorkActionForm actions={["approve"]} disabled={false} onSubmit={submit} />);
    expect(screen.queryAllByRole("textbox")).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "Approve" }));
    expect(submit).toHaveBeenCalledWith({ action: "approve" });
  });

  it("submits structured Analyst clarification and Customer response payloads", async () => {
    const submit = vi.fn<(action: WorkAction) => void>();
    const user = userEvent.setup();
    const { rerender } = render(
      <WorkActionForm actions={["request_clarification"]} disabled={false} onSubmit={submit} />,
    );
    await user.type(screen.getByLabelText("Question for the Customer"), "Which region should be prioritised?");
    await user.type(screen.getByLabelText("Why this information is needed"), "The product needs a bounded scope.");
    await user.type(screen.getByLabelText("Response deadline"), "2026-09-10");
    await user.click(screen.getByRole("button", { name: "Ask Customer for information" }));
    expect(submit).toHaveBeenLastCalledWith({
      action: "request_clarification",
      question: "Which region should be prioritised?",
      reason: "The product needs a bounded scope.",
      responseDeadline: "2026-09-10",
    });

    const clarification = {
      id: "thread-1",
      sequence: 1,
      question: "Which region should be prioritised?",
      reason: "The product needs a bounded scope.",
      responseDeadline: "2026-09-10",
      status: "OPEN" as const,
      version: 3,
      assignedSpecialist: requestDetail.assignedSpecialist!,
      messages: [],
      createdAt: requestDetail.createdAt,
      closedAt: null,
    };
    rerender(
      <WorkActionForm actions={["provide_clarification"]} clarification={clarification} disabled={false} onSubmit={submit} />,
    );
    await user.type(screen.getByLabelText("Information for the Analyst"), "Prioritise the northern region.");
    await user.click(screen.getByRole("button", { name: "Send information to Analyst" }));
    expect(submit).toHaveBeenLastCalledWith({
      action: "provide_clarification",
      expectedVersion: 3,
      information: "Prioritise the northern region.",
      threadId: "thread-1",
    });
  });

  it("shows reason and allocation field errors", async () => {
    const user = userEvent.setup();
    const { rerender } = render(<WorkActionForm actions={["request_information"]} disabled={false} onSubmit={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Request more information" }));
    expect(await screen.findByText("Explain this decision.")).toBeInTheDocument();
    rerender(<WorkActionForm actions={["allocate"]} disabled={false} onSubmit={vi.fn()} routingOptions={readyRouting} />);
    await user.click(screen.getByRole("button", { name: "Route to team" }));
    expect(await screen.findByText("Choose a destination unit.")).toBeInTheDocument();
  });

  it("submits the selected specialist identifier and validates an empty selection", async () => {
    const submit = vi.fn<(action: WorkAction) => void>();
    const user = userEvent.setup();
    const view = render(
      <WorkActionForm
        actions={["assign"]}
        disabled={false}
        onSubmit={submit}
        specialistOptions={readySpecialists}
      />,
    );

    const specialistSelect = screen.getByLabelText("Team Analyst");
    expect(specialistSelect).toHaveAttribute("aria-invalid", "false");
    expect(specialistSelect).not.toHaveAttribute("aria-describedby");
    expect(await axe(view.container)).toHaveNoViolations();
    await user.click(screen.getByRole("button", { name: "Assign Analyst" }));
    const error = await screen.findByText("Choose an Analyst.");
    expect(error.id).not.toBe("");
    expect(specialistSelect).toHaveAttribute("aria-invalid", "true");
    expect(specialistSelect).toHaveAttribute("aria-describedby", error.id);
    expect(await axe(view.container)).toHaveNoViolations();

    await user.click(screen.getByRole("button", { name: "Assign Analyst" }));
    expect(screen.getByText("Choose an Analyst.")).toHaveAttribute("id", error.id);
    await user.selectOptions(specialistSelect, "specialist-2");
    await user.click(screen.getByRole("button", { name: "Assign Analyst" }));

    expect(submit).toHaveBeenCalledWith({
      action: "assign",
      specialistId: "specialist-2",
    });
  });

  it("handles specialist loading, error, empty and ready states", async () => {
    const retry = vi.fn();
    const user = userEvent.setup();
    const actions = ["assign"] as const;
    const { rerender } = render(
      <WorkActionForm
        actions={[...actions]}
        disabled={false}
        onSubmit={vi.fn()}
        specialistOptions={{ items: [], onRetry: retry, status: "loading" }}
      />,
    );

    expect(screen.getByLabelText("Team Analyst")).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("Loading eligible Analysts…");
    expect(screen.getByRole("button", { name: "Assign Analyst" })).toBeDisabled();

    rerender(
      <WorkActionForm
        actions={[...actions]}
        disabled={false}
        onSubmit={vi.fn()}
        specialistOptions={{ items: [], onRetry: retry, status: "error" }}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Eligible Analysts could not be loaded.",
    );
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledOnce();

    rerender(
      <WorkActionForm
        actions={[...actions]}
        disabled={false}
        onSubmit={vi.fn()}
        specialistOptions={{ items: [], onRetry: retry, status: "ready" }}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "No eligible Analysts are available for this team.",
    );
    expect(screen.getByLabelText("Team Analyst")).toBeDisabled();

    rerender(
      <WorkActionForm
        actions={[...actions]}
        disabled={false}
        onSubmit={vi.fn()}
        specialistOptions={readySpecialists}
      />,
    );
    expect(screen.getByRole("option", { name: "Aisha Rahman" })).toHaveValue(
      "specialist-1",
    );
    expect(screen.getByLabelText("Team Analyst")).toBeEnabled();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("renders no-action and disabled states", () => {
    const { rerender } = render(<WorkActionForm actions={[]} disabled={false} onSubmit={vi.fn()} />);
    expect(screen.getByText("No actions are available for this item.")).toBeInTheDocument();
    rerender(<WorkActionForm actions={["approve"]} disabled onSubmit={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Recording outcome…" })).toBeDisabled();
  });

  it("renders every ownership state", () => {
    const props = { currentUserId: "me", disabled: false, onClaim: vi.fn(), onComplete: vi.fn() };
    const { rerender } = render(<WorkActionPanel {...props} item={workItem} />);
    expect(screen.getByRole("heading", { name: "Take ownership" })).toBeInTheDocument();
    rerender(<WorkActionPanel {...props} item={{ ...workItem, assigneeId: "other", assigneeDisplayName: null }} />);
    expect(screen.getByRole("heading", { name: "Assigned to another team member" })).toBeInTheDocument();
    rerender(<WorkActionPanel {...props} item={{ ...workItem, assigneeId: "me", availableActions: [] }} />);
    expect(screen.getByRole("heading", { name: "Record outcome" })).toBeInTheDocument();
    rerender(<WorkActionPanel {...props} disabled item={workItem} />);
    expect(screen.getByRole("button", { name: "Claiming…" })).toBeDisabled();
  });
});
