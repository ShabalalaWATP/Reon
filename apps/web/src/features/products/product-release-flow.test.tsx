import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import type { ProductPackage } from "../../lib/api/productTypes";
import {
  enabledCapabilities,
  requesterSession,
  requestDetail,
  requestSummary,
} from "../../test/fixtures";
import { json, mockFeatureFetch, renderApp } from "../../test/render";
import { basePackage, mockCrypto, release, roleSession } from "./productFlowTestSupport";

describe("managed product release journey", () => {
  it("requires QC attestation for external links, disseminates and supports withdrawal", async () => {
    let current: ProductPackage = {
      ...basePackage,
      requestStatus: "READY_FOR_RELEASE",
      status: "MANAGER_APPROVED",
      packageChecksum: "c".repeat(64),
    };
    const actions: string[] = [];
    mockCrypto();
    mockFeatureFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(roleSession("QUALITY_RELEASE"));
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/product-packages/pkg-1") && !init.method) return json(current);
      if (url.pathname.endsWith("/disseminate")) {
        actions.push(String(init.body));
        current = {
          ...current,
          status: "DISSEMINATED",
          disseminatedAt: "2026-08-07T10:00:00Z",
          disseminatedBy: "QC Manager",
          version: 2,
        };
        return json(current);
      }
      if (url.pathname.endsWith("/withdraw")) {
        actions.push(String(init.body));
        current = { ...current, status: "WITHDRAWN", version: 3 };
        return json(current);
      }
      throw new Error(`${init.method ?? "GET"} ${url.pathname}`);
    });
    const user = userEvent.setup();
    renderApp("/product-packages/pkg-1");
    const disseminate = await screen.findByRole("button", { name: "Disseminate to Customer" });
    expect(disseminate).toBeDisabled();
    await user.click(screen.getByLabelText(/External access attested/));
    await user.click(disseminate);
    const reason = await screen.findByLabelText("Withdrawal reason");
    await user.type(reason, "Superseded by corrected product");
    await user.click(screen.getByRole("button", { name: "Withdraw access" }));
    await waitFor(() => expect(actions).toHaveLength(2));
    expect(JSON.parse(actions[0])).toMatchObject({
      externalLinkAttested: true,
      packageChecksum: "c".repeat(64),
    });
    expect(JSON.parse(actions[1])).toMatchObject({ reason: "Superseded by corrected product" });
  });

  it("shows released file and link actions in Customer register and detail views", async () => {
    let currentRelease = release;
    let acceptanceBody: Record<string, unknown> | undefined;
    mockFeatureFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (
        url.pathname.endsWith(`/releases/requests/${requestSummary.id}/accept`) &&
        init.method === "POST"
      ) {
        acceptanceBody = JSON.parse(String(init.body));
        currentRelease = { ...currentRelease, acceptedAt: "2026-08-07T11:00:00Z" };
        return json(currentRelease);
      }
      if (url.pathname.endsWith(`/releases/requests/${requestSummary.id}`))
        return json(currentRelease);
      if (url.pathname.endsWith(`/requests/${requestSummary.id}`))
        return json({ ...requestDetail, productAvailable: true, status: "COMPLETED" });
      if (url.pathname.endsWith("/requests"))
        return json({
          items: [{ ...requestSummary, productAvailable: true, status: "COMPLETED" }],
        });
      throw new Error(url.pathname);
    });
    const register = renderApp("/requests");
    await userEvent.setup().click(await screen.findByText("Completed history"));
    expect(await screen.findByText("Product available")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Download" })).toHaveAttribute(
      "href",
      "/api/v1/releases/artefacts/art-file/download",
    );
    expect(screen.getByRole("link", { name: "Open product" })).toHaveAttribute("target", "_blank");
    expect(await axe(register.container)).toHaveNoViolations();
    register.unmount();
    const detail = renderApp(`/requests/${requestSummary.id}`);
    expect(await screen.findByRole("heading", { name: "Product available" })).toBeInTheDocument();
    expect(screen.getByText(/Released by QC Manager/)).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "Accept product" }));
    expect(await screen.findByText(/Accepted 07 Aug 2026/)).toBeInTheDocument();
    expect(acceptanceBody?.idempotencyKey).toEqual(expect.any(String));
    expect(await axe(detail.container)).toHaveNoViolations();
    detail.unmount();
    renderApp("/requests");
    await userEvent.setup().click(await screen.findByText("Completed history"));
    expect(await screen.findByText(/Accepted 07 Aug 2026/)).toBeInTheDocument();
  });

  it("keeps Customer acceptance pending and reports a rejected write", async () => {
    let resolveAcceptance: (response: Response) => void = () => undefined;
    mockFeatureFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (
        url.pathname.endsWith(`/releases/requests/${requestSummary.id}/accept`) &&
        init.method === "POST"
      ) {
        return new Promise<Response>((resolve) => {
          resolveAcceptance = resolve;
        });
      }
      if (url.pathname.endsWith(`/releases/requests/${requestSummary.id}`)) return json(release);
      if (url.pathname.endsWith(`/requests/${requestSummary.id}`))
        return json({ ...requestDetail, productAvailable: true, status: "COMPLETED" });
      throw new Error(url.pathname);
    });
    const user = userEvent.setup();
    renderApp(`/requests/${requestSummary.id}`);

    await user.click(await screen.findByRole("button", { name: "Accept product" }));
    expect(screen.getByRole("button", { name: "Recording acceptance…" })).toBeDisabled();
    resolveAcceptance(json({ detail: "Unavailable" }, 503));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Product acceptance could not be recorded",
    );
  });

  it("does not expose artefacts before a release is disseminated", async () => {
    mockFeatureFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith(`/releases/requests/${requestSummary.id}`))
        return json({ ...release, status: "READY_FOR_RELEASE" });
      if (url.pathname.endsWith(`/requests/${requestSummary.id}`))
        return json({ ...requestDetail, productAvailable: true, status: "COMPLETED" });
      throw new Error(url.pathname);
    });
    renderApp(`/requests/${requestSummary.id}`);

    expect(await screen.findByText("Product ready_for_release")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Open product" })).not.toBeInTheDocument();
  });
});
