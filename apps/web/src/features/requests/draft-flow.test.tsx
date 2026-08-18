import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { RequestDraft } from "../../lib/api/types";
import { requestDetail, requestSummary, requesterSession } from "../../test/fixtures";
import { json, mockFetch, renderApp } from "../../test/render";

const fullDraft: RequestDraft = {
  id: "draft-1",
  requesterId: requesterSession.user.id,
  title: requestDetail.title,
  description: requestDetail.description,
  questionToAnswer: requestDetail.questionToAnswer,
  desiredOutcome: requestDetail.desiredOutcome,
  backgroundContext: requestDetail.backgroundContext,
  subjectAreaOrLocation: requestDetail.subjectAreaOrLocation,
  coverageStart: requestDetail.coverageStart,
  coverageEnd: requestDetail.coverageEnd,
  customerUrgency: requestDetail.customerUrgency,
  supportedActivityOrDecision: requestDetail.supportedActivityOrDecision,
  requiredBy: requestDetail.requiredBy,
  requiredByReason: requestDetail.requiredByReason,
  preferredDeliverableType: requestDetail.preferredDeliverableType,
  successCriteria: requestDetail.successCriteria,
  constraintsOrCaveats: requestDetail.constraintsOrCaveats,
  supportingInformation: requestDetail.supportingInformation,
  sensitivity: requestDetail.sensitivity,
  handlingInstructions: requestDetail.handlingInstructions,
  version: 1,
  createdAt: requestDetail.createdAt,
  updatedAt: requestDetail.updatedAt,
};

describe("private Customer drafts", () => {
  it("shows private drafts in the Customer register", async () => {
    mockFetch(
      (url) => {
        if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
        if (url.pathname.endsWith("/request-drafts")) {
          return json({ items: [{ ...fullDraft, title: null }] });
        }
        if (url.pathname.endsWith("/requests")) return json({ items: [requestSummary] });
        throw new Error(url.pathname);
      },
      { emptyDraftRegister: false },
    );
    renderApp("/requests");
    expect(await screen.findByRole("heading", { name: "Drafts" })).toBeInTheDocument();
    expect(screen.getByText("Untitled request")).toBeInTheDocument();
    expect(screen.getByText("Only visible to you")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Untitled request/ })).toHaveAttribute(
      "href",
      "/requests/drafts/draft-1",
    );
  });

  it("saves an incomplete new draft and deletes it", async () => {
    const blankDraft = { ...fullDraft, title: "", version: 1 };
    let deleted = false;
    mockFetch(
      (url, init) => {
        if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
        if (url.pathname.endsWith("/request-drafts") && init.method === "POST") {
          return json(blankDraft, 201);
        }
        if (url.pathname.endsWith("/request-drafts/draft-1") && init.method === "DELETE") {
          deleted = true;
          return new Response(null, { status: 204 });
        }
        if (url.pathname.endsWith("/request-drafts/draft-1")) return json(blankDraft);
        if (url.pathname.endsWith("/request-drafts")) return json({ items: [] });
        if (url.pathname.endsWith("/requests")) return json({ items: [] });
        throw new Error(`${init.method ?? "GET"} ${url.pathname}`);
      },
      { emptyDraftRegister: false },
    );
    const user = userEvent.setup();
    renderApp("/requests/new");
    await screen.findByRole("heading", { name: "New service request" });
    await user.click(screen.getByRole("button", { name: "Save draft" }));
    expect(await screen.findByText("Draft saved privately.")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Edit request draft" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Delete draft" }));
    expect(await screen.findByRole("heading", { name: "My requests" })).toBeInTheDocument();
    expect(deleted).toBe(true);
  });

  it("updates and submits a complete draft with the returned version", async () => {
    let savedBody: Record<string, unknown> | undefined;
    let submittedBody: Record<string, unknown> | undefined;
    const savedDraft = { ...fullDraft, version: 2, title: "Updated draft title" };
    mockFetch(
      (url, init) => {
        if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
        if (url.pathname.endsWith("/request-drafts/draft-1/submit")) {
          submittedBody = JSON.parse(String(init.body)) as Record<string, unknown>;
          return json({ ...requestDetail, title: "Updated draft title" });
        }
        if (url.pathname.endsWith("/request-drafts/draft-1") && init.method === "PATCH") {
          savedBody = JSON.parse(String(init.body)) as Record<string, unknown>;
          return json(savedDraft);
        }
        if (url.pathname.endsWith("/request-drafts/draft-1")) return json(fullDraft);
        if (url.pathname.endsWith(`/${requestDetail.id}`)) {
          return json({ ...requestDetail, title: "Updated draft title" });
        }
        throw new Error(`${init.method ?? "GET"} ${url.pathname}`);
      },
      { emptyDraftRegister: false },
    );
    const user = userEvent.setup();
    renderApp("/requests/drafts/draft-1");
    await screen.findByRole("heading", { name: "Edit request draft" });
    const title = screen.getByLabelText(/Request title/);
    await user.clear(title);
    await user.type(title, "Updated draft title");
    await user.click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() =>
      expect(savedBody).toMatchObject({ expectedVersion: 1, title: "Updated draft title" }),
    );
    await user.click(screen.getByRole("button", { name: "Submit request" }));
    expect(await screen.findByRole("heading", { name: "Updated draft title" })).toBeInTheDocument();
    expect(submittedBody).toMatchObject({ expectedVersion: 2, title: "Updated draft title" });
    expect(submittedBody?.submissionKey).toEqual(expect.any(String));
  });

  it("reports an unavailable draft without exposing another Customer", async () => {
    mockFetch(
      (url) =>
        url.pathname.endsWith("/auth/me")
          ? json(requesterSession)
          : json({ detail: "Not found" }, 404),
      { emptyDraftRegister: false },
    );
    renderApp("/requests/drafts/missing");
    expect(
      await screen.findByRole("heading", { name: "Draft could not be loaded" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Return to requests" })).toBeInTheDocument();
  });
});
