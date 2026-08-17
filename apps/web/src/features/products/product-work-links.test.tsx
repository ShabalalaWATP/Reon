import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { enabledCapabilities, requestDetail, requestSummary, workItem } from "../../test/fixtures";
import { json, mockFeatureFetch, renderApp } from "../../test/render";
import { basePackage, roleSession } from "./productFlowTestSupport";

describe("managed product work links", () => {
  it("links an Analyst work item to a prefilled package draft", async () => {
    const session = roleSession("DELIVERY_SPECIALIST");
    mockFeatureFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(session);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/work-items"))
        return json({
          items: [
            {
              ...workItem,
              stage: "IN_PROGRESS",
              requestVersion: 7,
              assigneeId: session.user.id,
              availableActions: ["submit"],
            },
          ],
        });
      if (url.pathname.endsWith(`/requests/${requestSummary.id}`))
        return json({ ...requestDetail, status: "IN_PROGRESS" });
      if (url.pathname.endsWith(`/product-packages/by-request/${requestSummary.id}`))
        return json(null);
      throw new Error(url.pathname);
    });
    renderApp("/delivery/my-work");
    expect(await screen.findByRole("link", { name: "Start product package" })).toHaveAttribute(
      "href",
      `/product-packages/new?requestId=${requestSummary.id}&version=7`,
    );
  });

  it("tells a Manager when no managed package has been started", async () => {
    const session = roleSession("DELIVERY_TEAM_LEAD");
    mockFeatureFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(session);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/work-items"))
        return json({
          items: [
            {
              ...workItem,
              stage: "LEAD_REVIEW",
              assigneeId: session.user.id,
              availableActions: ["approve"],
            },
          ],
        });
      if (url.pathname.endsWith(`/requests/${requestSummary.id}`))
        return json({ ...requestDetail, status: "LEAD_REVIEW" });
      if (url.pathname.endsWith(`/product-packages/by-request/${requestSummary.id}`))
        return json(null);
      throw new Error(url.pathname);
    });
    renderApp("/delivery/team");

    expect(
      await screen.findByText("No managed product package has been started."),
    ).toBeInTheDocument();
  });

  it("offers a revised package when rework points at an immutable version", async () => {
    const session = roleSession("DELIVERY_SPECIALIST");
    mockFeatureFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(session);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/work-items"))
        return json({
          items: [
            {
              ...workItem,
              stage: "REWORK_REQUIRED",
              requestVersion: 8,
              assigneeId: session.user.id,
              availableActions: ["submit"],
            },
          ],
        });
      if (url.pathname.endsWith(`/requests/${requestSummary.id}`))
        return json({ ...requestDetail, status: "REWORK_REQUIRED" });
      if (url.pathname.endsWith(`/product-packages/by-request/${requestSummary.id}`))
        return json({ ...basePackage, status: "REVIEW_READY" });
      throw new Error(url.pathname);
    });
    renderApp("/delivery/my-work");
    expect(await screen.findByRole("link", { name: "Start revised package" })).toHaveAttribute(
      "href",
      `/product-packages/new?requestId=${requestSummary.id}&version=8`,
    );
  });

  it("withholds dissemination until the workflow reaches release readiness", async () => {
    mockFeatureFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(roleSession("QUALITY_RELEASE"));
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/product-packages/pkg-1"))
        return json({
          ...basePackage,
          requestStatus: "QUALITY_REVIEW",
          status: "MANAGER_APPROVED",
          packageChecksum: "c".repeat(64),
        });
      throw new Error(url.pathname);
    });
    renderApp("/product-packages/pkg-1");
    expect(await screen.findByText(/Complete the workflow review/)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Disseminate to Customer" }),
    ).not.toBeInTheDocument();
  });

  it.each([
    ["DELIVERY_TEAM_LEAD", "LEAD_REVIEW", "/delivery/team", "Review product package"],
    ["QUALITY_RELEASE", "QUALITY_REVIEW", "/quality-release", "Review product package"],
    ["QUALITY_RELEASE", "READY_FOR_RELEASE", "/quality-release", "Disseminate product package"],
  ] as const)(
    "links a %s work item to the current immutable package",
    async (role, stage, path, label) => {
      const session = roleSession(role);
      mockFeatureFetch((url) => {
        if (url.pathname.endsWith("/auth/me")) return json(session);
        if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
        if (url.pathname.endsWith("/work-items"))
          return json({
            items: [
              {
                ...workItem,
                stage,
                assigneeId: session.user.id,
                availableActions:
                  role === "QUALITY_RELEASE"
                    ? stage === "QUALITY_REVIEW"
                      ? ["approve"]
                      : ["release"]
                    : ["approve"],
              },
            ],
          });
        if (url.pathname.endsWith(`/requests/${requestSummary.id}`))
          return json({ ...requestDetail, status: stage });
        if (url.pathname.endsWith(`/product-packages/by-request/${requestSummary.id}`))
          return json(basePackage);
        throw new Error(url.pathname);
      });
      renderApp(path);
      expect(await screen.findByRole("link", { name: label })).toHaveAttribute(
        "href",
        "/product-packages/pkg-1",
      );
    },
  );
});
