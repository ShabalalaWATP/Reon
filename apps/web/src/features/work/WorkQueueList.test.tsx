import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { workItem } from "../../test/fixtures";
import { WorkQueueList } from "./WorkQueueList";

describe("QC Team queue sections", () => {
  it("separates review work from dissemination work", () => {
    render(
      <WorkQueueList
        currentUserId="quality-user"
        hasMore={false}
        items={[
          { ...workItem, id: "quality", stage: "QUALITY_REVIEW", title: "Review package" },
          { ...workItem, id: "release", stage: "READY_FOR_RELEASE", title: "Disseminate package" },
        ]}
        loadingMore={false}
        onLoadMore={vi.fn()}
        onSelect={vi.fn()}
        splitQualityStages
      />,
    );

    expect(
      within(screen.getByRole("region", { name: "Needs QC review" })).getByText("Review package"),
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole("region", { name: "Ready for dissemination" })).getByText(
        "Disseminate package",
      ),
    ).toBeInTheDocument();
  });

  it("keeps both accountable sections visible when one is empty", () => {
    render(
      <WorkQueueList
        currentUserId="quality-user"
        hasMore={false}
        items={[{ ...workItem, stage: "QUALITY_REVIEW" }]}
        loadingMore={false}
        onLoadMore={vi.fn()}
        onSelect={vi.fn()}
        splitQualityStages
      />,
    );

    expect(
      within(screen.getByRole("region", { name: "Ready for dissemination" })).getByText(
        "No items in this section.",
      ),
    ).toBeInTheDocument();
  });
});
