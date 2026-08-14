import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { ProductArtefact } from "../../lib/api/productTypes";
import { enabledCapabilities, requesterSession, requestSummary } from "../../test/fixtures";
import { json, mockFeatureFetch, renderApp } from "../../test/render";
import { artefacts, basePackage, mockCrypto, roleSession } from "./productFlowTestSupport";

describe("managed product authoring journey", () => {
  it("creates a package against the assigned request version", async () => {
    let body: Record<string, unknown> | undefined;
    mockCrypto();
    mockFeatureFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(roleSession("DELIVERY_SPECIALIST"));
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/product-packages") && init.method === "POST") {
        body = JSON.parse(String(init.body));
        return json(basePackage, 201);
      }
      if (url.pathname.endsWith("/product-packages/pkg-1")) return json(basePackage);
      throw new Error(`${init.method ?? "GET"} ${url.pathname}`);
    });
    const user = userEvent.setup();
    renderApp(`/product-packages/new?requestId=${requestSummary.id}&version=7`);
    await user.click(await screen.findByRole("button", { name: "Create release package" }));
    expect(await screen.findByRole("heading", { name: requestSummary.title })).toBeInTheDocument();
    expect(body).toMatchObject({ requestId: requestSummary.id, expectedVersion: 7 });
  });

  it("validates package creation and recovers an authorised package read", async () => {
    let fail = true;
    mockFeatureFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(roleSession("DELIVERY_SPECIALIST"));
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/product-packages/pkg-1"))
        return fail ? json({ detail: "Unavailable" }, 503) : json(basePackage);
      throw new Error(url.pathname);
    });
    const user = userEvent.setup();
    const create = renderApp("/product-packages/new");
    await user.click(await screen.findByRole("button", { name: "Create release package" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Enter the request identifier and current version",
    );
    create.unmount();
    renderApp("/product-packages/pkg-1");
    expect(
      await screen.findByRole("heading", { name: "Product package could not be loaded" }),
    ).toBeInTheDocument();
    fail = false;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: requestSummary.title })).toBeInTheDocument();
  });

  it("uploads managed bytes through the opaque intent and records an HTTPS link", async () => {
    const calls: Array<{ body: unknown; headers: Headers; method: string; path: string }> = [];
    let current = { ...basePackage, artefacts: [] as ProductArtefact[] };
    mockCrypto();
    mockFeatureFetch(async (url, init) => {
      const method = init.method ?? "GET";
      calls.push({
        body: init.body,
        headers: new Headers(init.headers),
        method,
        path: `${url.pathname}${url.search}`,
      });
      if (url.pathname.endsWith("/auth/me")) return json(roleSession("DELIVERY_SPECIALIST"));
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/product-packages/pkg-1") && method === "GET")
        return json(current);
      if (url.pathname.endsWith("/managed-artefacts"))
        return json({
          package: { ...current, version: 2 },
          artefact: artefacts[0],
          uploadIntent: {
            id: "intent-1",
            objectKey: "opaque",
            uploadToken: "t".repeat(40),
            expiresAt: "2099-01-01T00:00:00Z",
          },
        });
      if (url.pathname.endsWith("/content"))
        return json({
          intentId: "intent-1",
          sizeBytes: 3,
          sha256: "0".repeat(64),
          uploadedAt: "2026-08-07T10:00:00Z",
          packageVersion: 3,
        });
      if (url.pathname.endsWith("/complete")) {
        current = { ...current, artefacts: [artefacts[0]], version: 4 };
        return json(current);
      }
      if (url.pathname.endsWith("/external-links")) {
        current = { ...current, artefacts, version: 5 };
        return json(current);
      }
      throw new Error(`${method} ${url.pathname}`);
    });
    const user = userEvent.setup();
    renderApp("/product-packages/pkg-1");
    await screen.findByRole("heading", { name: "Build release package" });
    const file = new File(["pdf"], "brief.pdf", { type: "application/pdf" });
    Object.defineProperty(file, "arrayBuffer", {
      value: async () => new TextEncoder().encode("pdf").buffer,
    });
    await user.type(screen.getAllByLabelText("Product label")[0], "Decision brief");
    await user.upload(document.querySelector<HTMLInputElement>('input[type="file"]')!, file);
    await user.click(screen.getByRole("button", { name: "Upload artefact" }));
    await waitFor(() =>
      expect(screen.getAllByText("brief.pdf", { exact: false })).not.toHaveLength(0),
    );
    const upload = calls.find((call) => call.method === "PUT")!;
    expect(upload.path).toContain("/uploads/intent-1/content?expectedVersion=2");
    expect(upload.headers.get("X-Upload-Token")).toBe("t".repeat(40));
    expect(upload.headers.get("X-CSRF-Token")).toBe("csrf-token");
    const completion = calls.find((call) => call.path.endsWith("/complete"))!;
    expect(JSON.parse(String(completion.body))).toMatchObject({ expectedVersion: 3 });
    await user.type(screen.getAllByLabelText("Product label")[1], "Interactive product");
    await user.type(
      screen.getByLabelText("HTTPS product URL"),
      "https://products.example.test/view",
    );
    await user.type(screen.getByLabelText("Expiry (optional)"), "2099-08-10T10:00");
    await user.click(screen.getByRole("button", { name: "Add approved link" }));
    await waitFor(() =>
      expect(screen.getByText("products.example.test", { exact: false })).toBeInTheDocument(),
    );
    const linkBody = JSON.parse(
      String(calls.find((call) => call.path.endsWith("/external-links"))!.body),
    );
    expect(linkBody).toMatchObject({
      url: "https://products.example.test/view",
      expiresAt: new Date("2099-08-10T10:00").toISOString(),
    });
  });

  it("keeps approved links available when managed-file assurance is absent", async () => {
    const externalOnly = { ...enabledCapabilities, managedFileUploads: false };
    mockFeatureFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(roleSession("DELIVERY_SPECIALIST"));
      if (url.pathname.endsWith("/me/capabilities")) return json(externalOnly);
      if (url.pathname.endsWith("/product-packages/pkg-1"))
        return json({ ...basePackage, artefacts: [] });
      throw new Error(url.pathname);
    });
    renderApp("/product-packages/pkg-1");
    expect(await screen.findByText(/no approved semantic\/CDR scanner/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Upload artefact" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add approved link" })).toBeInTheDocument();
  });

  it("keeps legacy downloads visible when managed products are disabled", async () => {
    mockFeatureFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/me/capabilities"))
        return json({ ...enabledCapabilities, products: false });
      if (url.pathname.endsWith("/requests"))
        return json({
          items: [{ ...requestSummary, productAvailable: true, status: "COMPLETED" }],
        });
      throw new Error(url.pathname);
    });
    renderApp("/requests");
    await userEvent.setup().click(await screen.findByText("Completed history"));
    expect(await screen.findByRole("link", { name: "Download product" })).toHaveAttribute(
      "href",
      `/api/v1/requests/${requestSummary.id}/product`,
    );
  });

  it.each([
    [
      "DELIVERY_SPECIALIST",
      "DRAFT",
      "REVIEW_READY",
      "Submit exact version for review",
      "/submit",
      "Awaiting Manager review",
    ],
    [
      "DELIVERY_TEAM_LEAD",
      "REVIEW_READY",
      "MANAGER_APPROVED",
      "Approve exact package",
      "/manager-approve",
      "Manager approved",
    ],
  ] as const)(
    "records the %s exact-version decision",
    async (role, initialStatus, resultStatus, label, suffix, resultLabel) => {
      let actionBody: Record<string, unknown> | undefined;
      const checksum = "b".repeat(64);
      mockCrypto();
      mockFeatureFetch((url, init) => {
        if (url.pathname.endsWith("/auth/me")) return json(roleSession(role));
        if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
        if (url.pathname.endsWith(suffix) && init.method === "POST") {
          actionBody = JSON.parse(String(init.body));
          return json({ ...basePackage, status: resultStatus, version: 2 });
        }
        if (url.pathname.endsWith("/product-packages/pkg-1"))
          return json({ ...basePackage, packageChecksum: checksum, status: initialStatus });
        throw new Error(`${init.method ?? "GET"} ${url.pathname}`);
      });
      const user = userEvent.setup();
      renderApp("/product-packages/pkg-1");
      if (role === "DELIVERY_SPECIALIST") {
        await user.type(
          await screen.findByLabelText(/Covering note to Customer/),
          "Synthetic covering note for the Customer.",
        );
      }
      await user.click(await screen.findByRole("button", { name: label }));
      await waitFor(() => expect(actionBody).toBeDefined());
      expect(await screen.findByText(resultLabel, { exact: true })).toBeInTheDocument();
      expect(actionBody).toMatchObject({
        expectedVersion: 1,
        ...(role === "DELIVERY_TEAM_LEAD"
          ? { packageChecksum: checksum }
          : { coveringNote: "Synthetic covering note for the Customer." }),
      });
    },
  );
});
