import { describe, expect, it, vi } from "vitest";

import { json, mockFetch } from "../../test/render";
import { ApiError } from "./client";
import { productApi, productArtefactUrl } from "./productClient";

const csrf = "csrf";
const versioned = { expectedVersion: 2, idempotencyKey: "99999999-9999-4999-8999-999999999999" };

describe("product API client", () => {
  it("uses the bounded package and release route contracts", async () => {
    const requests: Array<{ body: unknown; method: string; path: string }> = [];
    mockFetch((url, init) => {
      requests.push({ body: init.body ? JSON.parse(String(init.body)) : null, method: init.method ?? "GET", path: `${url.pathname}${url.search}` });
      return json({ id: "response" });
    }, false, false, false, false, false);
    await productApi.createPackage({ requestId: "request/one", ...versioned }, csrf);
    await productApi.package("package/one");
    await productApi.packageForRequest("request/one");
    await productApi.addManagedArtefact("package/one", { ...versioned, filename: "brief.pdf", label: "Brief", mediaType: "application/pdf", sizeBytes: 10, sha256: "a".repeat(64) }, csrf);
    await productApi.completeUpload("package/one", "intent/one", versioned, csrf);
    await productApi.addExternalLink("package/one", { ...versioned, label: "Product", url: "https://example.test/a" }, csrf);
    await productApi.submit("package/one", versioned, csrf);
    await productApi.managerApprove("package/one", { ...versioned, packageChecksum: "b".repeat(64) }, csrf);
    await productApi.disseminate("package/one", { ...versioned, packageChecksum: "b".repeat(64), externalLinkAttested: true }, csrf);
    await productApi.withdraw("package/one", { ...versioned, reason: "Incorrect release" }, csrf);
    await productApi.releaseForRequest("request/one");
    expect(requests.map((item) => `${item.method} ${item.path}`)).toEqual([
      "POST /api/v1/product-packages",
      "GET /api/v1/product-packages/package%2Fone",
      "GET /api/v1/product-packages/by-request/request%2Fone",
      "POST /api/v1/product-packages/package%2Fone/managed-artefacts",
      "POST /api/v1/product-packages/package%2Fone/uploads/intent%2Fone/complete",
      "POST /api/v1/product-packages/package%2Fone/external-links",
      "POST /api/v1/product-packages/package%2Fone/submit",
      "POST /api/v1/product-packages/package%2Fone/manager-approve",
      "POST /api/v1/releases/package%2Fone/disseminate",
      "POST /api/v1/releases/package%2Fone/withdraw",
      "GET /api/v1/releases/requests/request%2Fone",
    ]);
    expect(requests[0].body).toMatchObject({ requestId: "request/one", expectedVersion: 2 });
    expect(productArtefactUrl("id/one", "MANAGED_FILE")).toBe("/api/v1/releases/artefacts/id%2Fone/download");
    expect(productArtefactUrl("id/one", "EXTERNAL_LINK")).toBe("/api/v1/releases/artefacts/id%2Fone/open");
  });

  it("uploads raw bytes with the optimistic version, token and CSRF proof", async () => {
    let seen: { headers: Headers; path: string } | undefined;
    mockFetch((url, init) => {
      seen = { headers: new Headers(init.headers), path: `${url.pathname}${url.search}` };
      return json({ intentId: "intent", packageVersion: 2 });
    }, false, false, false, false, false);
    const receipt = await productApi.uploadContent("package", "intent", new File(["bytes"], "brief.pdf", { type: "application/pdf" }), 2, "opaque-token", csrf);
    expect(receipt.packageVersion).toBe(2);
    expect(seen?.path).toBe("/api/v1/product-packages/package/uploads/intent/content?expectedVersion=2");
    expect(seen?.headers.get("X-Upload-Token")).toBe("opaque-token");
    expect(seen?.headers.get("Content-Type")).toBe("application/pdf");
  });

  it("reports JSON and non-JSON upload failures without exposing token data", async () => {
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(json({ detail: "Upload intent expired." }, 409))
      .mockResolvedValueOnce(json({ detail: { message: "Checksum mismatch." } }, 422))
      .mockResolvedValueOnce(new Response("upstream", { status: 503 })));
    const file = new File(["bytes"], "brief", { type: "" });
    await expect(productApi.uploadContent("p", "i", file, 1, "secret", csrf)).rejects.toEqual(expect.objectContaining({ message: "Upload intent expired.", status: 409 }));
    await expect(productApi.uploadContent("p", "i", file, 1, "secret", csrf)).rejects.toEqual(expect.objectContaining({ message: "Checksum mismatch.", status: 422 }));
    await expect(productApi.uploadContent("p", "i", file, 1, "secret", csrf)).rejects.toEqual(expect.objectContaining({ message: "Upload failed with status 503.", status: 503 }));
    expect(ApiError).toBeDefined();
  });
});
