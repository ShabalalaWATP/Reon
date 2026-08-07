import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import { json, mockFetch, renderApp } from "../../test/render";
import { requestDetail, requestSummary, requesterSession, workItem } from "../../test/fixtures";

describe("requester experience", () => {
  it("shows current requests, action-needed work and completed history", async () => {
    const items = [
      { ...requestSummary, id: "need", status: "INFORMATION_REQUIRED", needsRequesterInput: true, currentOwner: null },
      requestSummary,
      { ...requestSummary, id: "done", reference: "ISR-2026-0002", status: "COMPLETED", title: "Completed request", productAvailable: true },
    ];
    mockFetch((url) => url.pathname.endsWith("/auth/me") ? json(requesterSession) : json({ items }));
    const view = renderApp("/requests");
    expect(await screen.findByRole("heading", { name: "My requests" })).toBeInTheDocument();
    expect(screen.getAllByText("Needs your input")[0].closest("div")).toHaveTextContent("1");
    expect(screen.getByRole("heading", { name: "In progress" })).toBeInTheDocument();
    expect(screen.getByText("Awaiting assignment")).toBeInTheDocument();
    const history = screen.getByText("Completed history").closest("details")!;
    expect(within(history).getByText("Completed request")).toBeInTheDocument();
    expect(within(history).getByRole("link", { name: "Download product" })).toHaveAttribute("href", "/api/v1/requests/done/product");
    expect(within(history).getByText("Feedback requested")).toBeInTheDocument();
    expect(await axe(view.container)).toHaveNoViolations();
  });

  it("shows empty and recoverable error states", async () => {
    let fail = true;
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/requests")) return fail ? json({ detail: "Unavailable" }, 503) : json({ items: [] });
      throw new Error(url.pathname);
    });
    const user = userEvent.setup();
    renderApp("/requests");
    expect(await screen.findByRole("heading", { name: "Requests could not be loaded" })).toBeInTheDocument();
    fail = false;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: "No requests yet" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Create your first request" })).toBeInTheDocument();
  });

  it("validates and submits the complete structured request contract", async () => {
    let submitted: Record<string, unknown> | undefined;
    mockFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/requests") && init.method === "POST") {
        submitted = JSON.parse(String(init.body)) as Record<string, unknown>;
        expect(new Headers(init.headers).get("X-CSRF-Token")).toBe("csrf-token");
        return json(requestDetail);
      }
      if (url.pathname.endsWith(`/${requestDetail.id}`)) return json(requestDetail);
      throw new Error(`Unexpected ${url.pathname}`);
    });
    const user = userEvent.setup();
    renderApp("/requests/new");
    await screen.findByRole("heading", { name: "New service request" });
    await user.click(screen.getByRole("button", { name: "Submit request" }));
    expect(await screen.findByText("Enter a clear request title.")).toBeInTheDocument();
    await fillRequestForm(user);
    await user.click(screen.getByRole("button", { name: "Submit request" }));
    expect(await screen.findByRole("heading", { name: requestDetail.title })).toBeInTheDocument();
    expect(submitted).toMatchObject({
      title: "Quarterly service readiness summary",
      requestingBusinessArea: "Requesting Area A",
      sensitivity: "STANDARD",
      intendedRecipients: ["Service leadership", "Operations lead"],
    });
    expect(submitted).not.toHaveProperty("assignedDeliveryTeam");
    expect(submitted).not.toHaveProperty("assignedSpecialist");
  });

  it("reports request submission failures", async () => {
    mockFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (init.method === "POST") return json({ detail: { message: "Request data was rejected." } }, 422);
      throw new Error(url.pathname);
    });
    const user = userEvent.setup();
    renderApp("/requests/new");
    await screen.findByRole("heading", { name: "New service request" });
    await fillRequestForm(user);
    await user.click(screen.getByRole("button", { name: "Submit request" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Request data was rejected");
  });

  it("shows overview, activity, released delivery and one-time feedback", async () => {
    let detail = {
      ...requestDetail,
      status: "COMPLETED" as const,
      deliverable: { id: "deliverable", title: "Readiness summary", text: "All measures are on track.", releasedAt: "2026-08-06T11:00:00Z" },
    };
    mockFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/feedback") && init.method === "POST") {
        detail = { ...detail, feedback: { id: "feedback", rating: 4, comments: "Clear and useful.", createdAt: "2026-08-06T12:00:00Z" } };
        return json(detail.feedback);
      }
      if (url.pathname.includes("/requests/")) return json(detail);
      throw new Error(url.pathname);
    });
    const user = userEvent.setup();
    const view = renderApp(`/requests/${requestDetail.id}`);
    expect(await screen.findByRole("heading", { name: requestDetail.title })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getByText("Request submitted")).toBeInTheDocument();
    expect(screen.getByText("All measures are on track.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Download product" })).toHaveAttribute(
      "href",
      `/api/v1/requests/${requestDetail.id}/product`,
    );
    await user.selectOptions(screen.getByLabelText(/Rating/), "4");
    await user.type(screen.getByLabelText(/Service comments/), "Clear and useful.");
    await user.click(screen.getByRole("button", { name: "Send feedback" }));
    expect(await screen.findByText("4 out of 5")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Send feedback" })).not.toBeInTheDocument();
    expect(await axe(view.container)).toHaveNoViolations();
  });

  it.each([
    ["IN_PROGRESS", "2026-08-06T11:00:00Z"],
    ["COMPLETED", null],
  ] as const)("does not offer a product download before dissemination for %s", async (status, releasedAt) => {
    const detail = {
      ...requestDetail,
      status,
      deliverable: { id: "product", title: "Withheld product", text: "Withheld text", releasedAt },
    };
    mockFetch((url) => url.pathname.endsWith("/auth/me") ? json(requesterSession) : json(detail));
    renderApp(`/requests/${detail.id}`);
    expect(await screen.findByRole("heading", { name: detail.title })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Download product" })).not.toBeInTheDocument();
    expect(screen.queryByText("Withheld text")).not.toBeInTheDocument();
    expect(screen.getByText("The product will appear here after dissemination.")).toBeInTheDocument();
  });

  it("lets a requester provide information through their named work item", async () => {
    const infoRequest = { ...requestDetail, status: "INFORMATION_REQUIRED" as const, needsRequesterInput: true, workflowError: "sync delayed", events: [] };
    const item = { ...workItem, stage: "INFORMATION_REQUIRED" as const, assigneeId: requesterSession.user.id, assigneeDisplayName: requesterSession.user.displayName, availableActions: ["provide_information", "withdraw"] as const };
    let completedBody: unknown;
    mockFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/work-items")) return json({ items: [item] });
      if (url.pathname.endsWith("/complete")) { completedBody = JSON.parse(String(init.body)); return json(requestDetail); }
      if (url.pathname.includes("/requests/")) return json(infoRequest);
      if (url.pathname.endsWith("/requests")) return json({ items: [] });
      throw new Error(url.pathname);
    });
    const user = userEvent.setup();
    renderApp(`/requests/${requestDetail.id}`);
    expect(await screen.findByRole("heading", { name: "Record outcome" })).toBeInTheDocument();
    expect(screen.getByText("Progress is temporarily delayed. Staff have been notified.")).toBeInTheDocument();
    expect(screen.getByText("No activity has been recorded yet.")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Additional information"), "The meeting has moved to 20 September.");
    await user.click(screen.getByRole("button", { name: "Provide information" }));
    await waitFor(() => expect(completedBody).toEqual({ action: "provide_information", information: "The meeting has moved to 20 September." }));
  });

  it("shows the stored production conversation and returns information to the Analyst", async () => {
    const clarification = {
      id: "thread-1",
      sequence: 1,
      question: "Which fictional region should be prioritised?",
      reason: "The product needs a bounded scope.",
      responseDeadline: "2026-09-10",
      status: "OPEN" as const,
      version: 2,
      assignedSpecialist: { id: "analyst-1", displayName: "Denis Law" },
      messages: [{ id: "message-1", kind: "REQUEST" as const, body: "Which fictional region should be prioritised?", actorDisplayName: "Denis Law", createdAt: "2026-08-06T11:00:00Z" }],
      createdAt: "2026-08-06T11:00:00Z",
      closedAt: null,
    };
    const detail = { ...requestDetail, status: "CUSTOMER_INFORMATION_REQUIRED" as const, needsRequesterInput: true, clarifications: [clarification] };
    const item = { ...workItem, stage: "CUSTOMER_INFORMATION_REQUIRED" as const, assigneeId: requesterSession.user.id, assigneeDisplayName: requesterSession.user.displayName, availableActions: ["provide_clarification", "withdraw"] as const };
    let completedBody: unknown;
    mockFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/work-items")) return json({ items: [item] });
      if (url.pathname.endsWith("/complete")) { completedBody = JSON.parse(String(init.body)); return json(requestDetail); }
      if (url.pathname.includes("/requests/")) return json(detail);
      if (url.pathname.endsWith("/requests")) return json({ items: [] });
      throw new Error(url.pathname);
    });
    const user = userEvent.setup();
    const view = renderApp(`/requests/${requestDetail.id}`);
    expect(await screen.findByRole("heading", { name: "Additional information" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: clarification.question })).toBeInTheDocument();
    expect(screen.getByText(/The product needs a bounded scope/)).toBeInTheDocument();
    await user.type(await screen.findByLabelText("Information for the Analyst"), "Prioritise the fictional northern region.");
    await user.click(screen.getByRole("button", { name: "Send information to Analyst" }));
    await waitFor(() => expect(completedBody).toEqual({ action: "provide_clarification", threadId: "thread-1", expectedVersion: 2, information: "Prioritise the fictional northern region." }));
    expect(await axe(view.container)).toHaveNoViolations();
  });

  it("handles unavailable details and feedback errors", async () => {
    let failFeedback = false;
    const complete = { ...requestDetail, status: "COMPLETED" as const, deliverable: { id: "d", title: "Result", text: "Text", releasedAt: requestDetail.updatedAt } };
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/missing")) return json({ detail: "Not found" }, 404);
      if (url.pathname.endsWith("/feedback")) return failFeedback ? json({ detail: "Feedback already submitted" }, 409) : json({});
      return json(complete);
    });
    renderApp("/requests/missing");
    expect(await screen.findByRole("heading", { name: "Request not available" })).toBeInTheDocument();
    failFeedback = true;
  });
});

async function fillRequestForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/Request title/), "Quarterly service readiness summary");
  await user.selectOptions(screen.getByLabelText(/Service category/), "Advisory support");
  await user.type(screen.getByLabelText(/Description of the need/), "Provide a clear summary of current service readiness.");
  await user.type(screen.getByLabelText(/Desired outcome/), "Leaders can make the next quarterly decision.");
  await user.type(screen.getByLabelText(/Background and known context/), "Quarterly review context.");
  await user.type(screen.getByLabelText(/Required-by date/), "2026-09-10");
  await user.selectOptions(screen.getByLabelText(/Preferred product type/), "Briefing note");
  await user.type(screen.getByLabelText(/Why the date matters/), "The review is scheduled the following day.");
  await user.type(screen.getByLabelText(/Success criteria/), "All agreed measures and next steps are covered.");
  await user.type(screen.getByLabelText(/Intended recipients/), "Service leadership\nOperations lead");
  await user.type(screen.getByLabelText(/Handling instructions/), "Standard handling applies.");
}
