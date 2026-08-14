import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import { staffSession } from "../../test/fixtures";
import { json, mockFetch, TestProviders } from "../../test/render";
import { RelatedRecordPanel } from "./RelatedRecordPanel";
import { comparisonSummary } from "./relatedRecordPresentation";

const candidate = {
  id: "candidate-one",
  reference: "ISR-2026-0011",
  title: "Earlier readiness assessment",
  status: "COMPLETED",
  requiredBy: "2026-08-30",
  productAvailable: true,
  matchStrength: 78,
  matchBand: "STRONG",
  methods: ["FULL_TEXT", "STRUCTURED"],
  reasons: ["Question to answer shares 4 significant terms."],
  evidence: [
    {
      field: "Question to answer",
      reason: "Question to answer shares 4 significant terms.",
      excerpt: "What readiness evidence is available for the planning review?",
    },
  ],
};

function view() {
  return render(
    <TestProviders>
      <RelatedRecordPanel session={staffSession} workItemId="work-one" />
    </TestProviders>,
  );
}

async function expandComparison(user: ReturnType<typeof userEvent.setup>) {
  const toggle = await screen.findByRole("button", {
    name: "Review previous request matches",
  });
  expect(toggle).toHaveAttribute("aria-expanded", "false");
  await user.click(toggle);
  expect(toggle).toHaveAttribute("aria-expanded", "true");
  return toggle;
}

describe("related-request comparison", () => {
  it("summarises every comparison state without overstating weak matches", () => {
    const strong = { matchBand: "STRONG" as const };
    const possible = { matchBand: "POSSIBLE" as const };

    expect(comparisonSummary("", true, false)).toBe("Checking authorised request history…");
    expect(comparisonSummary("", false, true)).toBe("Comparison unavailable");
    expect(comparisonSummary("", false, false)).toBe("No comparison available");
    expect(comparisonSummary("search", false, false, [strong])).toBe("1 result for “search”");
    expect(comparisonSummary("search", false, false, [strong, possible])).toBe(
      "2 results for “search”",
    );
    expect(comparisonSummary("", false, false, [])).toBe("No credible matches found");
    expect(comparisonSummary("", false, false, [possible, possible])).toBe(
      "No strong matches · 2 lower-confidence suggestions",
    );
    expect(comparisonSummary("", false, false, [strong, strong])).toBe("2 strong matches");
    expect(comparisonSummary("", false, false, [strong, possible])).toBe(
      "1 strong match · 1 other suggestion",
    );
    expect(comparisonSummary("", false, false, [strong, possible, possible])).toBe(
      "1 strong match · 2 other suggestions",
    );
  });

  it("loads automatic matches and records an attributable human decision", async () => {
    let workspace = { sourceVersion: 4, items: [] as unknown[] };
    let posted: unknown;
    mockFetch((url, init) => {
      if (url.pathname.endsWith("/request-links") && init.method === "POST") {
        posted = JSON.parse(String(init.body));
        workspace = {
          sourceVersion: 5,
          items: [
            {
              id: "link-one",
              target: candidate,
              linkType: "EXISTING_OUTPUT",
              reason: "The released product may meet the same customer need.",
              actorDisplayName: "Scott McTominay",
              createdAt: "2026-08-07T10:00:00Z",
            },
          ],
        };
        return json(workspace);
      }
      if (url.pathname.endsWith("/request-links")) return json(workspace);
      if (url.pathname.endsWith("/related-records")) {
        expect(url.searchParams.has("query")).toBe(false);
        return json({ mode: "TEXT_ONLY", items: [candidate] });
      }
      throw new Error(`Unexpected ${url.pathname}`);
    });
    const user = userEvent.setup();
    const rendered = view();
    expect(await screen.findByText("1 strong match")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Earlier readiness assessment/ }),
    ).not.toBeInTheDocument();
    const toggle = await expandComparison(user);
    expect(await screen.findByText("No comparison decisions recorded.")).toBeInTheDocument();
    const resultsRegion = screen.getByRole("region", {
      name: "Previous request match results",
    });
    expect(resultsRegion).toHaveAttribute("tabindex", "0");
    await user.click(await screen.findByRole("button", { name: /Earlier readiness assessment/ }));
    expect(
      screen.getByText("What readiness evidence is available for the planning review?"),
    ).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText(/Decision/), "EXISTING_OUTPUT");
    await user.type(
      screen.getByLabelText(/Reason/),
      "The released product may meet the same customer need.",
    );
    await user.click(screen.getByRole("button", { name: "Record decision" }));
    expect(
      await screen.findByText(/Scott McTominay · 07 Aug 2026, (10|11):00/),
    ).toBeInTheDocument();
    expect(posted).toEqual({
      expectedVersion: 4,
      targetRequestId: candidate.id,
      linkType: "EXISTING_OUTPUT",
      reason: "The released product may meet the same customer need.",
    });
    expect(screen.queryByRole("button", { name: "Record decision" })).not.toBeInTheDocument();
    await user.click(toggle);
    expect(
      screen.queryByRole("button", { name: /Earlier readiness assessment/ }),
    ).not.toBeInTheDocument();
    expect(await axe(rendered.container)).toHaveNoViolations();
  });

  it("handles unavailable results, disabled output links and mutation conflicts", async () => {
    let failSearch = false;
    let candidateWithNoProduct = {
      ...candidate,
      matchBand: "POSSIBLE" as const,
      matchStrength: 47,
      productAvailable: false,
    };
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
        return json({
          mode: "TEXT_ONLY",
          items: query === "nothing" ? [] : [candidateWithNoProduct],
        });
      }
      throw new Error(`Unexpected ${url.pathname}`);
    });
    const user = userEvent.setup();
    view();
    expect(
      await screen.findByText("No strong matches · 1 lower-confidence suggestion"),
    ).toBeInTheDocument();
    await expandComparison(user);
    await screen.findByText("No comparison decisions recorded.");
    const input = screen.getByLabelText(/Search request history/);
    await user.type(input, "nothing");
    await user.click(screen.getByRole("button", { name: "Search records" }));
    expect(
      await screen.findByText("No authorised request matches those terms."),
    ).toBeInTheDocument();
    await user.clear(input);
    await user.type(input, "earlier");
    await user.click(screen.getByRole("button", { name: "Search records" }));
    await user.click(await screen.findByRole("button", { name: /Earlier readiness assessment/ }));
    expect(screen.getByRole("option", { name: "Existing released product" })).toBeDisabled();
    await user.selectOptions(screen.getByLabelText(/Decision/), "NOT_RELEVANT");
    await user.type(
      screen.getByLabelText(/Reason/),
      "This related request needs a recorded human review.",
    );
    await user.click(screen.getByRole("button", { name: "Record decision" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Refresh this request");
    failSearch = true;
    candidateWithNoProduct = { ...candidateWithNoProduct, title: "Changed" };
    await user.clear(input);
    await user.type(input, "failure");
    await user.click(screen.getByRole("button", { name: "Search records" }));
    expect(
      await screen.findByText("Request comparison could not be completed."),
    ).toBeInTheDocument();
  });

  it("retries a failed link register", async () => {
    let calls = 0;
    mockFetch((url) => {
      if (url.pathname.endsWith("/related-records")) {
        return json({ mode: "TEXT_ONLY", items: [] });
      }
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
    await expandComparison(user);
    expect(
      await screen.findByRole("heading", { name: "Recorded links could not be loaded" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(calls).toBe(2));
    expect(await screen.findByText("No comparison decisions recorded.")).toBeInTheDocument();
  });

  it("returns from advanced search to automatic hybrid evidence", async () => {
    const sparseCandidate = {
      ...candidate,
      evidence: [{ field: "Request details", reason: "Coverage periods overlap.", excerpt: "" }],
      reasons: [],
    };
    mockFetch((url) => {
      if (url.pathname.endsWith("/request-links")) {
        return json({ sourceVersion: 1, items: [] });
      }
      if (url.pathname.endsWith("/related-records")) {
        const query = url.searchParams.get("query");
        return json(
          query ? { mode: "TEXT_ONLY", items: [] } : { mode: "HYBRID", items: [sparseCandidate] },
        );
      }
      throw new Error(`Unexpected ${url.pathname}`);
    });
    const user = userEvent.setup();
    view();
    await expandComparison(user);
    expect(await screen.findByText(/semantic, full-text and field matching/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Earlier readiness assessment/ }));
    expect(screen.getByText("Open to review the comparison evidence.")).toBeInTheDocument();
    const evidenceItem = screen.getByText("Coverage periods overlap.").closest("li");
    expect(evidenceItem?.querySelector("p")).toBeNull();

    await user.type(screen.getByLabelText(/Search request history/), "nothing");
    await user.click(screen.getByRole("button", { name: "Search records" }));
    expect(
      await screen.findByText("No authorised request matches those terms."),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Automatic matches" }));
    expect(await screen.findByText(/semantic, full-text and field matching/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Automatic matches" })).not.toBeInTheDocument();
  });
});
