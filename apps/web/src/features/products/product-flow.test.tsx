import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";

import type { Session } from "../../lib/api/types";
import { enabledCapabilities, requesterSession, requestDetail, requestSummary, staffSession, workItem } from "../../test/fixtures";
import { json, mockFeatureFetch, renderApp } from "../../test/render";
import type { ProductArtefact, ProductPackage, ProductRelease } from "../../lib/api/productTypes";

const artefacts: ProductArtefact[] = [
  { id: "art-file", packageId: "pkg-1", position: 1, kind: "MANAGED_FILE", lifecycle: "CLEAN", label: "Decision brief", filename: "brief.pdf", mediaType: "application/pdf", sizeBytes: 2048, sha256: "a".repeat(64), destinationDomain: null, expiresAt: null, scanResult: "CLEAN", scanReason: null, releasedAt: null, version: 1 },
  { id: "art-link", packageId: "pkg-1", position: 2, kind: "EXTERNAL_LINK", lifecycle: "CLEAN", label: "Interactive product", filename: null, mediaType: null, sizeBytes: null, sha256: null, destinationDomain: "products.example.test", expiresAt: "2099-08-10T10:00:00Z", scanResult: null, scanReason: null, releasedAt: null, version: 1 },
];

const basePackage: ProductPackage = {
  id: "pkg-1", requestId: requestSummary.id, requestReference: requestSummary.reference,
  requestTitle: requestSummary.title, requestStatus: "IN_PROGRESS", authorDisplayName: "Lewis Ferguson", packageVersion: 2,
  status: "DRAFT", packageChecksum: null, version: 1, artefacts,
  managerApprovedAt: null, managerApprovedBy: null, disseminatedAt: null,
  disseminatedBy: null, withdrawalReason: null,
};

const release: ProductRelease = {
  packageId: basePackage.id, requestId: requestSummary.id, packageVersion: 2,
  status: "DISSEMINATED", releasedAt: "2026-08-07T10:00:00Z", releasedBy: "QC Manager",
  artefacts: artefacts.map((item) => ({ ...item, lifecycle: "RELEASED", releasedAt: "2026-08-07T10:00:00Z" })),
};

function roleSession(role: Session["user"]["role"]): Session {
  return { ...staffSession, user: { ...staffSession.user, role } };
}

describe("managed product package journey", () => {
  it("creates a package against the assigned request version", async () => {
    let body: Record<string, unknown> | undefined;
    mockCrypto();
    mockFeatureFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(roleSession("DELIVERY_SPECIALIST"));
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/product-packages") && init.method === "POST") { body = JSON.parse(String(init.body)); return json(basePackage, 201); }
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
      if (url.pathname.endsWith("/product-packages/pkg-1")) return fail ? json({ detail: "Unavailable" }, 503) : json(basePackage);
      throw new Error(url.pathname);
    });
    const user = userEvent.setup();
    const create = renderApp("/product-packages/new");
    await user.click(await screen.findByRole("button", { name: "Create release package" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Enter the request identifier and current version");
    create.unmount();
    renderApp("/product-packages/pkg-1");
    expect(await screen.findByRole("heading", { name: "Product package could not be loaded" })).toBeInTheDocument();
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
      calls.push({ body: init.body, headers: new Headers(init.headers), method, path: `${url.pathname}${url.search}` });
      if (url.pathname.endsWith("/auth/me")) return json(roleSession("DELIVERY_SPECIALIST"));
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/product-packages/pkg-1") && method === "GET") return json(current);
      if (url.pathname.endsWith("/managed-artefacts")) return json({ package: { ...current, version: 2 }, artefact: artefacts[0], uploadIntent: { id: "intent-1", objectKey: "opaque", uploadToken: "t".repeat(40), expiresAt: "2099-01-01T00:00:00Z" } });
      if (url.pathname.endsWith("/content")) return json({ intentId: "intent-1", sizeBytes: 3, sha256: "0".repeat(64), uploadedAt: "2026-08-07T10:00:00Z", packageVersion: 3 });
      if (url.pathname.endsWith("/complete")) { current = { ...current, artefacts: [artefacts[0]], version: 4 }; return json(current); }
      if (url.pathname.endsWith("/external-links")) { current = { ...current, artefacts, version: 5 }; return json(current); }
      throw new Error(`${method} ${url.pathname}`);
    });
    const user = userEvent.setup();
    renderApp("/product-packages/pkg-1");
    await screen.findByRole("heading", { name: "Build release package" });
    const file = new File(["pdf"], "brief.pdf", { type: "application/pdf" });
    Object.defineProperty(file, "arrayBuffer", { value: async () => new TextEncoder().encode("pdf").buffer });
    await user.type(screen.getAllByLabelText("Product label")[0], "Decision brief");
    await user.upload(document.querySelector<HTMLInputElement>('input[type="file"]')!, file);
    await user.click(screen.getByRole("button", { name: "Upload artefact" }));
    await waitFor(() => expect(screen.getByText("brief.pdf", { exact: false })).toBeInTheDocument());
    const upload = calls.find((call) => call.method === "PUT")!;
    expect(upload.path).toContain("/uploads/intent-1/content?expectedVersion=2");
    expect(upload.headers.get("X-Upload-Token")).toBe("t".repeat(40));
    expect(upload.headers.get("X-CSRF-Token")).toBe("csrf-token");
    const completion = calls.find((call) => call.path.endsWith("/complete"))!;
    expect(JSON.parse(String(completion.body))).toMatchObject({ expectedVersion: 3 });
    await user.type(screen.getAllByLabelText("Product label")[1], "Interactive product");
    await user.type(screen.getByLabelText("HTTPS product URL"), "https://products.example.test/view");
    await user.type(screen.getByLabelText("Expiry (optional)"), "2099-08-10T10:00");
    await user.click(screen.getByRole("button", { name: "Add approved link" }));
    await waitFor(() => expect(screen.getByText("products.example.test", { exact: false })).toBeInTheDocument());
    const linkBody = JSON.parse(String(calls.find((call) => call.path.endsWith("/external-links"))!.body));
    expect(linkBody).toMatchObject({ url: "https://products.example.test/view", expiresAt: new Date("2099-08-10T10:00").toISOString() });
  });

  it("keeps approved links available when managed-file assurance is absent", async () => {
    const externalOnly = { ...enabledCapabilities, managedFileUploads: false };
    mockFeatureFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(roleSession("DELIVERY_SPECIALIST"));
      if (url.pathname.endsWith("/me/capabilities")) return json(externalOnly);
      if (url.pathname.endsWith("/product-packages/pkg-1")) return json({ ...basePackage, artefacts: [] });
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
      if (url.pathname.endsWith("/me/capabilities")) return json({ ...enabledCapabilities, products: false });
      if (url.pathname.endsWith("/requests")) return json({ items: [{ ...requestSummary, productAvailable: true, status: "COMPLETED" }] });
      throw new Error(url.pathname);
    });
    renderApp("/requests");
    expect(await screen.findByRole("link", { name: "Download product" })).toHaveAttribute(
      "href",
      `/api/v1/requests/${requestSummary.id}/product`,
    );
  });

  it.each([
    ["DELIVERY_SPECIALIST", "DRAFT", "Submit exact version for review", "/submit"],
    ["DELIVERY_TEAM_LEAD", "REVIEW_READY", "Approve exact package", "/manager-approve"],
  ] as const)("records the %s exact-version decision", async (role, status, label, suffix) => {
    let actionBody: Record<string, unknown> | undefined;
    const checksum = "b".repeat(64);
    mockCrypto();
    mockFeatureFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(roleSession(role));
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith(suffix) && init.method === "POST") { actionBody = JSON.parse(String(init.body)); return json({ ...basePackage, status }); }
      if (url.pathname.endsWith("/product-packages/pkg-1")) return json({ ...basePackage, packageChecksum: checksum, status });
      throw new Error(`${init.method ?? "GET"} ${url.pathname}`);
    });
    const user = userEvent.setup();
    renderApp("/product-packages/pkg-1");
    await user.click(await screen.findByRole("button", { name: label }));
    await waitFor(() => expect(actionBody).toBeDefined());
    expect(actionBody).toMatchObject({ expectedVersion: 1, ...(role === "DELIVERY_TEAM_LEAD" ? { packageChecksum: checksum } : {}) });
  });

  it("requires QC attestation for external links, disseminates and supports withdrawal", async () => {
    let current: ProductPackage = { ...basePackage, requestStatus: "READY_FOR_RELEASE", status: "MANAGER_APPROVED", packageChecksum: "c".repeat(64) };
    const actions: string[] = [];
    mockCrypto();
    mockFeatureFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(roleSession("QUALITY_RELEASE"));
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/product-packages/pkg-1") && !init.method) return json(current);
      if (url.pathname.endsWith("/disseminate")) { actions.push(String(init.body)); current = { ...current, status: "DISSEMINATED", disseminatedAt: "2026-08-07T10:00:00Z", disseminatedBy: "QC Manager", version: 2 }; return json(current); }
      if (url.pathname.endsWith("/withdraw")) { actions.push(String(init.body)); current = { ...current, status: "WITHDRAWN", version: 3 }; return json(current); }
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
    expect(JSON.parse(actions[0])).toMatchObject({ externalLinkAttested: true, packageChecksum: "c".repeat(64) });
    expect(JSON.parse(actions[1])).toMatchObject({ reason: "Superseded by corrected product" });
  });

  it("shows released file and link actions in Customer register and detail views", async () => {
    mockFeatureFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith(`/releases/requests/${requestSummary.id}`)) return json(release);
      if (url.pathname.endsWith(`/requests/${requestSummary.id}`)) return json({ ...requestDetail, productAvailable: true, status: "COMPLETED" });
      if (url.pathname.endsWith("/requests")) return json({ items: [{ ...requestSummary, productAvailable: true, status: "COMPLETED" }] });
      throw new Error(url.pathname);
    });
    const register = renderApp("/requests");
    expect(await screen.findByText("Product available")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Download" })).toHaveAttribute("href", "/api/v1/releases/artefacts/art-file/download");
    expect(screen.getByRole("link", { name: "Open product" })).toHaveAttribute("target", "_blank");
    expect(await axe(register.container)).toHaveNoViolations();
    register.unmount();
    const detail = renderApp(`/requests/${requestSummary.id}`);
    expect(await screen.findByRole("heading", { name: "Product available" })).toBeInTheDocument();
    expect(screen.getByText(/Released by QC Manager/)).toBeInTheDocument();
    expect(await axe(detail.container)).toHaveNoViolations();
  });

  it("links an Analyst work item to a prefilled package draft", async () => {
    const session = roleSession("DELIVERY_SPECIALIST");
    mockFeatureFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(session);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/work-items")) return json({ items: [{ ...workItem, stage: "IN_PROGRESS", requestVersion: 7, assigneeId: session.user.id, availableActions: ["submit"] }] });
      if (url.pathname.endsWith(`/requests/${requestSummary.id}`)) return json({ ...requestDetail, status: "IN_PROGRESS" });
      if (url.pathname.endsWith(`/product-packages/by-request/${requestSummary.id}`)) return json({ detail: "Not found" }, 404);
      throw new Error(url.pathname);
    });
    renderApp("/delivery/my-work");
    expect(await screen.findByRole("link", { name: "Start product package" })).toHaveAttribute("href", `/product-packages/new?requestId=${requestSummary.id}&version=7`);
  });

  it("offers a revised package when rework points at an immutable version", async () => {
    const session = roleSession("DELIVERY_SPECIALIST");
    mockFeatureFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(session);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/work-items")) return json({ items: [{ ...workItem, stage: "REWORK_REQUIRED", requestVersion: 8, assigneeId: session.user.id, availableActions: ["submit"] }] });
      if (url.pathname.endsWith(`/requests/${requestSummary.id}`)) return json({ ...requestDetail, status: "REWORK_REQUIRED" });
      if (url.pathname.endsWith(`/product-packages/by-request/${requestSummary.id}`)) return json({ ...basePackage, status: "REVIEW_READY" });
      throw new Error(url.pathname);
    });
    renderApp("/delivery/my-work");
    expect(await screen.findByRole("link", { name: "Start revised package" })).toHaveAttribute("href", `/product-packages/new?requestId=${requestSummary.id}&version=8`);
  });

  it("withholds dissemination until the workflow reaches release readiness", async () => {
    mockFeatureFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(roleSession("QUALITY_RELEASE"));
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/product-packages/pkg-1")) return json({ ...basePackage, requestStatus: "QUALITY_REVIEW", status: "MANAGER_APPROVED", packageChecksum: "c".repeat(64) });
      throw new Error(url.pathname);
    });
    renderApp("/product-packages/pkg-1");
    expect(await screen.findByText(/Complete the workflow review/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Disseminate to Customer" })).not.toBeInTheDocument();
  });

  it.each([
    ["DELIVERY_TEAM_LEAD", "LEAD_REVIEW", "/delivery/team", "Review product package"],
    ["QUALITY_RELEASE", "QUALITY_REVIEW", "/quality-release", "Review and release package"],
  ] as const)("links a %s work item to the current immutable package", async (role, stage, path, label) => {
    const session = roleSession(role);
    mockFeatureFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(session);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/work-items")) return json({ items: [{ ...workItem, stage, assigneeId: session.user.id, availableActions: role === "QUALITY_RELEASE" ? ["release"] : ["approve"] }] });
      if (url.pathname.endsWith(`/requests/${requestSummary.id}`)) return json({ ...requestDetail, status: stage });
      if (url.pathname.endsWith(`/product-packages/by-request/${requestSummary.id}`)) return json(basePackage);
      throw new Error(url.pathname);
    });
    renderApp(path);
    expect(await screen.findByRole("link", { name: label })).toHaveAttribute("href", "/product-packages/pkg-1");
  });
});

function mockCrypto() {
  vi.stubGlobal("crypto", {
    randomUUID: () => "99999999-9999-4999-8999-999999999999",
    subtle: { digest: vi.fn().mockResolvedValue(new Uint8Array(32).buffer) },
  });
}
