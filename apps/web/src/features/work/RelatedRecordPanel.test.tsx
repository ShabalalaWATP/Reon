import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import { staffSession } from "../../test/fixtures";
import { json, mockFetch, TestProviders } from "../../test/render";
import { RelatedRecordPanel } from "./RelatedRecordPanel";

const candidate = {
  id: "candidate-one",
  reference: "ISR-2026-0011",
  title: "Earlier readiness assessment",
  status: "COMPLETED",
  requiredBy: "2026-08-30",
  productAvailable: true,
};

function view() {
  return render(
    <TestProviders>
      <RelatedRecordPanel
        csrfToken={staffSession.csrfToken}
        userId={staffSession.user.id}
        workItemId="work-one"
      />
    </TestProviders>,
  );
}

describe("manual related-record checks", () => {
  it("searches authorised records and records an attributable link", async () => {
    let workspace = { sourceVersion: 4, items: [] as unknown[] };
    let posted: unknown;
    mockFetch((url, init) => {
      if (url.pathname.endsWith("/request-links") && init.method === "POST") {
        posted = JSON.parse(String(init.body));
        workspace = {
          sourceVersion: 5,
          items: [{
            id: "link-one",
            target: candidate,
            linkType: "EXISTING_OUTPUT",
            reason: "The released product may meet the same customer need.",
            actorDisplayName: "Scott McTominay",
            createdAt: "2026-08-07T10:00:00Z",
          }],
        };
        return json(workspace);
      }
      if (url.pathname.endsWith("/request-links")) return json(workspace);
      if (url.pathname.endsWith("/related-records")) {
        expect(url.searchParams.get("query")).toBe("readiness");
        return json({ items: [candidate] });
      }
      throw new Error(`Unexpected ${url.pathname}`);
    });
    const user = userEvent.setup();
    const rendered = view();
    await user.click(screen.getByRole("button", { name: "Check related records" }));
    expect(await screen.findByText("No related-record checks recorded.")).toBeInTheDocument();
    await user.type(screen.getByLabelText(/Reference or title/), "readiness");
    await user.click(screen.getByRole("button", { name: "Search" }));
    await user.click(await screen.findByRole("button", { name: /Earlier readiness assessment/ }));
    await user.selectOptions(screen.getByLabelText(/Link type/), "EXISTING_OUTPUT");
    await user.type(screen.getByLabelText(/Reason/), "The released product may meet the same customer need.");
    await user.click(screen.getByRole("button", { name: "Record link" }));
    expect(
      await screen.findByText(/Scott McTominay · 07 Aug 2026, (10|11):00/),
    ).toBeInTheDocument();
    expect(posted).toEqual({
      expectedVersion: 4,
      targetRequestId: candidate.id,
      linkType: "EXISTING_OUTPUT",
      reason: "The released product may meet the same customer need.",
    });
    expect(screen.queryByRole("button", { name: "Record link" })).not.toBeInTheDocument();
    expect(await axe(rendered.container)).toHaveNoViolations();
  });

  it("handles unavailable results, disabled output links and mutation conflicts", async () => {
    let failSearch = false;
    let candidateWithNoProduct = { ...candidate, productAvailable: false };
    mockFetch((url, init) => {
      if (url.pathname.endsWith("/request-links") && init.method === "POST") {
        return json({ detail: "Refresh this request before recording the link." }, 409);
      }
      if (url.pathname.endsWith("/request-links")) {
        return json({ sourceVersion: 2, items: [] });
      }
      if (url.pathname.endsWith("/related-records")) {
        if (failSearch) return json({ detail: "Unavailable" }, 503);
        const query = url.searchParams.get("query");
        return json({ items: query === "nothing" ? [] : [candidateWithNoProduct] });
      }
      throw new Error(`Unexpected ${url.pathname}`);
    });
    const user = userEvent.setup();
    view();
    await user.click(screen.getByRole("button", { name: "Check related records" }));
    await screen.findByText("No related-record checks recorded.");
    const input = screen.getByLabelText(/Reference or title/);
    await user.type(input, "nothing");
    await user.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByText("No authorised records match this search.")).toBeInTheDocument();
    await user.clear(input);
    await user.type(input, "earlier");
    await user.click(screen.getByRole("button", { name: "Search" }));
    await user.click(await screen.findByRole("button", { name: /Earlier readiness assessment/ }));
    expect(screen.getByRole("option", { name: "Existing released product" })).toBeDisabled();
    await user.type(screen.getByLabelText(/Reason/), "This related request needs a recorded human review.");
    await user.click(screen.getByRole("button", { name: "Record link" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Refresh this request");
    failSearch = true;
    candidateWithNoProduct = { ...candidateWithNoProduct, title: "Changed" };
    await user.clear(input);
    await user.type(input, "failure");
    await user.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByText("Search could not be completed.")).toBeInTheDocument();
  });

  it("retries a failed link register", async () => {
    let calls = 0;
    mockFetch((url) => {
      if (url.pathname.endsWith("/request-links")) {
        calls += 1;
        return calls === 1
          ? json({ detail: "Unavailable" }, 503)
          : json({ sourceVersion: 1, items: [] });
      }
      throw new Error(`Unexpected ${url.pathname}`);
    });
    const user = userEvent.setup();
    view();
    await user.click(screen.getByRole("button", { name: "Check related records" }));
    expect(await screen.findByRole("heading", { name: "Recorded links could not be loaded" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(calls).toBe(2));
    expect(await screen.findByText("No related-record checks recorded.")).toBeInTheDocument();
  });
});
