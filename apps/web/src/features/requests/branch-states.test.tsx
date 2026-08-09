import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { requestDetail, requestSummary, requesterSession, workItem } from "../../test/fixtures";
import { json, mockFetch, renderApp } from "../../test/render";
import { FeedbackForm } from "./FeedbackForm";
import { RequestForm } from "./RequestForm";
import { RequestOverview } from "./RequestOverview";

describe("request branch states", () => {
  it("shows a completed-only register with no current work", async () => {
    mockFetch((url) => url.pathname.endsWith("/auth/me")
      ? json(requesterSession)
      : json({ items: [{ ...requestSummary, status: "COMPLETED" }] }));
    renderApp("/requests");
    expect(await screen.findByText("No requests in this group.")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Needs your input" })).not.toBeInTheDocument();
  });

  it("shows current work without creating completed history", async () => {
    mockFetch((url) => url.pathname.endsWith("/auth/me")
      ? json(requesterSession)
      : json({ items: [requestSummary] }));
    renderApp("/requests");
    expect(await screen.findByRole("heading", { name: "In progress" })).toBeInTheDocument();
    expect(screen.queryByText("Completed history")).not.toBeInTheDocument();
  });

  it("renders unallocated overview fallbacks", () => {
    render(<RequestOverview request={{ ...requestDetail, currentOwner: null, assignedDeliveryTeam: null, assignedSpecialist: null }} />);
    expect(screen.getByText("Awaiting assignment")).toBeInTheDocument();
    expect(screen.getByText("Not allocated")).toBeInTheDocument();
    expect(screen.getByText("Not assigned")).toBeInTheDocument();
  });

  it("renders feedback validation and pending state", async () => {
    const submit = vi.fn();
    const { rerender } = render(<FeedbackForm disabled={false} onSubmit={submit} />);
    fireEvent.change(screen.getByLabelText(/Rating/), { target: { value: "0" } });
    fireEvent.change(screen.getByLabelText(/Service comments/), { target: { value: "x".repeat(2001) } });
    fireEvent.submit(screen.getByRole("button", { name: "Send feedback" }).closest("form")!);
    expect(await screen.findByText("Choose a rating from 1 to 5.")).toBeInTheDocument();
    expect(screen.getByText(/Too big/)).toBeInTheDocument();
    rerender(<FeedbackForm disabled onSubmit={submit} />);
    expect(screen.getByRole("button", { name: "Sending…" })).toBeDisabled();
  });

  it("renders a disabled request submission control", () => {
    render(<RequestForm disabled onSubmit={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Submitting…" })).toBeDisabled();
  });

  it("shows event and feedback text fallbacks", async () => {
    const detail = {
      ...requestDetail,
      status: "COMPLETED" as const,
      events: [{ ...requestDetail.events[0], actorDisplayName: null }],
      deliverable: { id: "d", title: "Result", text: "Released text", releasedAt: null },
      feedback: { id: "f", rating: 5, comments: "Service response recorded.", createdAt: requestDetail.updatedAt },
    };
    mockFetch((url) => url.pathname.endsWith("/auth/me") ? json(requesterSession) : json(detail));
    renderApp(`/requests/${detail.id}`);
    expect(await screen.findByText(/ISTARI service/)).toBeInTheDocument();
    expect(screen.getByText("Service response recorded.")).toBeInTheDocument();
    expect(screen.getByText("The product will appear here after dissemination.")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Download product" })).not.toBeInTheDocument();
  });

  it.each([
    ["error", "The requested response could not be loaded."],
    ["empty", "No response task is currently available."],
  ])("shows the requester work-item %s state", async (state, message) => {
    const detail = { ...requestDetail, status: "INFORMATION_REQUIRED" as const };
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/work-items")) return state === "error" ? json({ detail: "Unavailable" }, 503) : json({ items: [] });
      return json(detail);
    });
    renderApp(`/requests/${detail.id}`);
    expect(await screen.findByText(message)).toBeInTheDocument();
  });

  it("claims requester work and reports a rejected claim", async () => {
    const detail = { ...requestDetail, status: "INFORMATION_REQUIRED" as const };
    const item = { ...workItem, stage: "INFORMATION_REQUIRED" as const, availableActions: ["provide_information"] as const };
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/work-items")) return json({ items: [item] });
      if (url.pathname.endsWith("/claim")) return json({ detail: { message: "Already claimed." } }, 409);
      return json(detail);
    });
    const user = userEvent.setup();
    renderApp(`/requests/${detail.id}`);
    await user.click(await screen.findByRole("button", { name: "Claim work item" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Already claimed.");
  });
});
