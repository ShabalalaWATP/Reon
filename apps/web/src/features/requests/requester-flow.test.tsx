import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import { json, mockFeatureFetch, renderApp } from "../../test/render";
import {
  enabledCapabilities,
  requestDetail,
  requestSummary,
  requesterSession,
} from "../../test/fixtures";

import { fillRequestForm, releasedPackage } from "./requesterFlowTestSupport";

describe("requester experience", () => {
  it("shows current requests, action-needed work and completed history", async () => {
    const items = [
      {
        ...requestSummary,
        id: "need",
        status: "INFORMATION_REQUIRED",
        needsRequesterInput: true,
        currentOwner: null,
      },
      requestSummary,
      {
        ...requestSummary,
        id: "done",
        reference: "ISR-2026-0002",
        status: "COMPLETED",
        title: "Completed request",
        productAvailable: true,
      },
    ];
    mockFeatureFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/releases/requests/done")) return json(releasedPackage("done"));
      return json({ items });
    });
    const view = renderApp("/requests");
    expect(await screen.findByRole("heading", { name: "My requests" })).toBeInTheDocument();
    expect(screen.getAllByText("Needs your input")[0].closest("div")).toHaveTextContent("1");
    expect(screen.getByRole("heading", { name: "Current requests" })).toBeInTheDocument();
    expect(screen.getAllByRole("columnheader", { name: "Reference" })).not.toHaveLength(0);
    expect(screen.getAllByRole("columnheader", { name: "Request" })).not.toHaveLength(0);
    expect(screen.getAllByRole("columnheader", { name: "Status" })).not.toHaveLength(0);
    expect(screen.getByText("Awaiting assignment")).toBeInTheDocument();
    const history = screen.getByText("Completed history").closest("details")!;
    expect(within(history).queryByText("Completed request")).not.toBeInTheDocument();
    await userEvent.setup().click(within(history).getByText("Completed history"));
    expect(await within(history).findByText("Completed request")).toBeInTheDocument();
    expect(await within(history).findByRole("link", { name: "Download" })).toHaveAttribute(
      "href",
      "/api/v1/releases/artefacts/released-file/download",
    );
    expect(within(history).getByText("Feedback requested")).toBeInTheDocument();
    expect(await axe(view.container)).toHaveNoViolations();
  });

  it("shows empty and recoverable error states", async () => {
    let fail = true;
    mockFeatureFetch(
      (url) => {
        if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
        if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
        if (url.pathname.endsWith("/request-drafts"))
          return fail ? json({ detail: "Unavailable" }, 503) : json({ items: [] });
        if (url.pathname.endsWith("/requests")) return json({ items: [] });
        throw new Error(url.pathname);
      },
      { emptyDraftRegister: false },
    );
    const user = userEvent.setup();
    renderApp("/requests");
    expect(
      await screen.findByRole("heading", { name: "Requests could not be loaded" }),
    ).toBeInTheDocument();
    fail = false;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: "No requests yet" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Create your first request" })).toBeInTheDocument();
  });

  it("validates and submits the complete structured request contract", async () => {
    let submitted: Record<string, unknown> | undefined;
    mockFeatureFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
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
    expect(screen.getByRole("button", { name: "Submit request" })).toBeDisabled();
    fillRequestForm();
    await user.click(screen.getByRole("button", { name: "Submit request" }));
    expect(await screen.findByRole("heading", { name: requestDetail.title })).toBeInTheDocument();
    expect(submitted).toMatchObject({
      title: "Quarterly service readiness summary",
      sensitivity: "STANDARD",
      customerUrgency: "ROUTINE",
    });
    expect(submitted).not.toHaveProperty("assignedDeliveryTeam");
    expect(submitted).not.toHaveProperty("assignedSpecialist");
    expect(submitted).not.toHaveProperty("serviceCategory");
  });

  it("reports request submission failures", async () => {
    mockFeatureFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (init.method === "POST")
        return json({ detail: { message: "Request data was rejected." } }, 422);
      throw new Error(url.pathname);
    });
    const user = userEvent.setup();
    renderApp("/requests/new");
    await screen.findByRole("heading", { name: "New service request" });
    fillRequestForm();
    await user.click(screen.getByRole("button", { name: "Submit request" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Request data was rejected");
  });

  it("shows overview, activity, released delivery and one-time feedback", async () => {
    let detail = {
      ...requestDetail,
      status: "COMPLETED" as const,
      productAvailable: true,
      deliverable: {
        id: "deliverable",
        title: "Readiness summary",
        text: "All measures are on track.",
        releasedAt: "2026-08-06T11:00:00Z",
      },
    };
    mockFeatureFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/feedback") && init.method === "POST") {
        detail = {
          ...detail,
          feedback: {
            id: "feedback",
            rating: 4,
            comments: "Clear and useful.",
            createdAt: "2026-08-06T12:00:00Z",
          },
        };
        return json(detail.feedback);
      }
      if (url.pathname.endsWith(`/releases/requests/${requestDetail.id}`))
        return json(releasedPackage(requestDetail.id));
      if (url.pathname.includes("/requests/")) return json(detail);
      throw new Error(url.pathname);
    });
    const user = userEvent.setup();
    const view = renderApp(`/requests/${requestDetail.id}`);
    expect(await screen.findByRole("heading", { name: requestDetail.title })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Request details" })).toBeInTheDocument();
    expect(screen.getByText("Request submitted")).toBeInTheDocument();
    expect(await screen.findByText("Readiness summary")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Download" })).toHaveAttribute(
      "href",
      "/api/v1/releases/artefacts/released-file/download",
    );
    await user.selectOptions(screen.getByLabelText(/Rating/), "4");
    await user.type(screen.getByLabelText(/Service comments/), "Clear and useful.");
    await user.click(screen.getByRole("button", { name: "Send feedback" }));
    expect(await screen.findByText("4 out of 5")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Send feedback" })).not.toBeInTheDocument();
    expect(await axe(view.container)).toHaveNoViolations();
  });

  it("requires a reason and closes a request through the cancellation control", async () => {
    let cancellation: Record<string, unknown> | undefined;
    const cancelled = {
      ...requestDetail,
      status: "CANCELLED" as const,
      version: requestDetail.version + 1,
      currentOwner: "Customer",
    };
    mockFeatureFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/cancel") && init.method === "POST") {
        cancellation = JSON.parse(String(init.body)) as Record<string, unknown>;
        return json(cancelled);
      }
      if (url.pathname.endsWith(`/requests/${requestDetail.id}`)) return json(requestDetail);
      throw new Error(`Unexpected ${url.pathname}`);
    });

    const user = userEvent.setup();
    renderApp(`/requests/${requestDetail.id}`);
    await user.click(await screen.findByRole("button", { name: "Cancel request" }));
    const confirm = screen.getByRole("button", { name: "Confirm cancellation" });
    expect(confirm).toBeDisabled();
    await user.type(
      screen.getByLabelText(/Cancellation reason/),
      "The requirement has been withdrawn.",
    );
    await user.click(confirm);

    await waitFor(() =>
      expect(cancellation).toEqual({
        expectedVersion: requestDetail.version,
        reason: "The requirement has been withdrawn.",
      }),
    );
    expect(await screen.findByText("Cancelled")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancel request" })).not.toBeInTheDocument();
  });

  it("keeps a request open when cancellation is rejected", async () => {
    mockFeatureFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/cancel") && init.method === "POST")
        return json({ detail: "Cancellation conflict" }, 409);
      if (url.pathname.endsWith(`/requests/${requestDetail.id}`)) return json(requestDetail);
      throw new Error(`Unexpected ${url.pathname}`);
    });
    const user = userEvent.setup();
    renderApp(`/requests/${requestDetail.id}`);
    await user.click(await screen.findByRole("button", { name: "Cancel request" }));
    await user.type(
      screen.getByLabelText(/Cancellation reason/),
      "The requirement may no longer be needed.",
    );
    await user.click(screen.getByRole("button", { name: "Confirm cancellation" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Cancellation conflict");
    await user.click(screen.getByRole("button", { name: "Keep request open" }));
    expect(screen.getByRole("button", { name: "Cancel request" })).toBeInTheDocument();
  });

  it("keeps a released legacy product downloadable when no managed package exists", async () => {
    const legacy = {
      ...requestDetail,
      status: "COMPLETED" as const,
      productAvailable: true,
      deliverable: {
        id: "legacy",
        title: "Legacy result",
        text: "Released text",
        releasedAt: "2026-08-06T11:00:00Z",
      },
    };
    mockFeatureFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith(`/releases/requests/${legacy.id}`)) return json(null);
      if (url.pathname.endsWith(`/requests/${legacy.id}`)) return json(legacy);
      throw new Error(url.pathname);
    });
    renderApp(`/requests/${legacy.id}`);
    expect(await screen.findByRole("link", { name: "Download product" })).toHaveAttribute(
      "href",
      `/api/v1/requests/${legacy.id}/product`,
    );
  });

  it.each([
    ["IN_PROGRESS", "2026-08-06T11:00:00Z"],
    ["COMPLETED", null],
  ] as const)(
    "does not offer a product download before dissemination for %s",
    async (status, releasedAt) => {
      const detail = {
        ...requestDetail,
        status,
        deliverable: {
          id: "product",
          title: "Withheld product",
          text: "Withheld text",
          releasedAt,
        },
      };
      mockFeatureFetch((url) =>
        url.pathname.endsWith("/auth/me")
          ? json(requesterSession)
          : url.pathname.endsWith("/me/capabilities")
            ? json(enabledCapabilities)
            : json(detail),
      );
      renderApp(`/requests/${detail.id}`);
      expect(await screen.findByRole("heading", { name: detail.title })).toBeInTheDocument();
      expect(screen.queryByRole("link", { name: "Download product" })).not.toBeInTheDocument();
      expect(screen.queryByText("Withheld text")).not.toBeInTheDocument();
      expect(
        screen.getByText("The product will appear here after dissemination."),
      ).toBeInTheDocument();
    },
  );
});
