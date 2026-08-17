import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";

import { ExternalLinkForm } from "./ExternalLinkForm";
import { ManagedFileForm } from "./ManagedFileForm";
import { PackageArtefactList } from "./PackageArtefactList";
import { formatBytes, newProductKey } from "./productPresentation";
import type { ProductArtefact } from "../../lib/api/productTypes";
import type { ManagedUploadProgress } from "./managedUploadModel";

describe("product artefact entry", () => {
  it("accepts approved documents and images and reports failures", async () => {
    vi.stubGlobal("crypto", {
      randomUUID: () => "key",
      subtle: { digest: vi.fn().mockResolvedValue(new Uint8Array([0, 15, 255]).buffer) },
    });
    const upload = vi
      .fn()
      .mockRejectedValueOnce(new Error("Scanner is unavailable."))
      .mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<ManagedFileForm disabled={false} onUpload={upload} />);
    const button = screen.getByRole("button", { name: "Upload to MIST" });
    await user.click(button);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Choose PDF, DOCX, PPTX, PNG or JPEG files.",
    );
    const input = document.querySelector<HTMLInputElement>('input[type="file"]')!;
    await user.upload(input, new File(["bad"], "macro.docm"));
    await user.click(button);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Choose PDF, DOCX, PPTX, PNG or JPEG files.",
    );
    const file = new File(["ok"], "BRIEF.PDF", { type: "application/pdf" });
    Object.defineProperty(file, "arrayBuffer", { value: async () => new Uint8Array([1]).buffer });
    await user.upload(input, file);
    await user.click(button);
    expect(screen.getByRole("alert")).toHaveTextContent("Enter a product label.");
    await user.type(screen.getByLabelText("Product label"), "  Release brief  ");
    await user.click(button);
    expect(await screen.findByRole("alert")).toHaveTextContent("Scanner is unavailable.");
    await user.click(button);
    expect(upload).toHaveBeenLastCalledWith([
      expect.objectContaining({
        label: "Release brief",
        mediaType: "application/pdf",
        sha256: "000fff",
      }),
    ]);
    expect(screen.getByLabelText("Product label")).toHaveValue("");
    fireEvent.change(input, { target: { files: [] } });
  });

  it("falls back to a safe upload error and honours disabled state", async () => {
    vi.stubGlobal("crypto", {
      subtle: { digest: vi.fn().mockResolvedValue(new Uint8Array(32).buffer) },
    });
    const upload = vi.fn().mockRejectedValue("offline");
    const user = userEvent.setup();
    const { rerender } = render(<ManagedFileForm disabled onUpload={upload} />);
    expect(screen.getByRole("button", { name: "Upload to MIST" })).toBeDisabled();
    rerender(<ManagedFileForm disabled={false} onUpload={upload} />);
    const file = new File(["ok"], "brief.docx");
    Object.defineProperty(file, "arrayBuffer", { value: async () => new Uint8Array([1]).buffer });
    await user.type(screen.getByLabelText("Product label"), "Brief");
    await user.upload(document.querySelector<HTMLInputElement>('input[type="file"]')!, file);
    await user.click(screen.getByRole("button", { name: "Upload to MIST" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The file could not be uploaded.");
  });

  it("prepares multiple image artefacts with bounded filename labels", async () => {
    vi.stubGlobal("crypto", {
      subtle: { digest: vi.fn().mockResolvedValue(new Uint8Array(32).buffer) },
    });
    const upload = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<ManagedFileForm disabled={false} maximumFiles={2} onUpload={upload} />);
    const input = document.querySelector<HTMLInputElement>('input[type="file"]')!;
    const png = new File(["png"], "map.png", { type: "image/png" });
    const jpeg = new File(["jpeg"], "chart.JPEG", { type: "image/jpeg" });
    for (const file of [png, jpeg]) {
      Object.defineProperty(file, "arrayBuffer", { value: async () => new Uint8Array([1]).buffer });
    }
    await user.upload(input, [png, jpeg]);
    await user.click(screen.getByRole("button", { name: "Upload to MIST" }));
    expect(upload).toHaveBeenCalledWith([
      expect.objectContaining({ label: "map", mediaType: "image/png" }),
      expect.objectContaining({ label: "chart", mediaType: "image/jpeg" }),
    ]);
  });

  it("announces per-file progress and retries the unfinished files", async () => {
    const retry = vi.fn().mockResolvedValue(undefined);
    const first = progress("first.pdf", "complete");
    const second = { ...progress("second.pdf", "error"), error: "Connection lost." };
    const view = render(
      <ManagedFileForm
        disabled={false}
        onRetry={retry}
        onUpload={vi.fn()}
        progress={[first, second]}
      />,
    );

    expect(screen.getByRole("list", { name: "Upload progress" })).toHaveAttribute(
      "aria-live",
      "polite",
    );
    expect(screen.getByText("Complete")).toBeInTheDocument();
    expect(screen.getByText("Upload stopped: Connection lost.")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Needs retry");
    await userEvent.setup().click(screen.getByRole("button", { name: "Retry unfinished uploads" }));
    expect(retry).toHaveBeenCalledOnce();
    expect(await axe(view.container)).toHaveNoViolations();
  });

  it("validates external HTTPS destinations without fetching or previewing them", async () => {
    const add = vi
      .fn()
      .mockRejectedValueOnce(new Error("Domain not approved."))
      .mockRejectedValueOnce("offline")
      .mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<ExternalLinkForm disabled={false} onAdd={add} />);
    const submit = screen.getByRole("button", { name: "Add product link" });
    await user.click(submit);
    expect(screen.getByRole("alert")).toHaveTextContent("Enter a product label.");
    await user.type(screen.getByLabelText("Product label"), "Dashboard");
    const credentialUrl = `https://${["user", "pass"].join(":")}@example.test/a`;
    for (const [url, message] of [
      ["not-a-url", "Enter a valid absolute HTTPS URL."],
      ["http://example.test/a", "Use an absolute HTTPS URL"],
      [credentialUrl, "Use an absolute HTTPS URL"],
      ["https://example.test/a#private", "Use an absolute HTTPS URL"],
      ["https://localhost/a", "Local destinations are not permitted."],
    ]) {
      await user.clear(screen.getByLabelText("HTTPS product URL"));
      await user.type(screen.getByLabelText("HTTPS product URL"), url);
      await user.click(submit);
      expect(screen.getByRole("alert")).toHaveTextContent(message);
    }
    await user.clear(screen.getByLabelText("HTTPS product URL"));
    await user.type(screen.getByLabelText("HTTPS product URL"), "https://products.example.test/a");
    await user.type(screen.getByLabelText("Expiry (optional)"), "2099-01-02T03:04");
    await user.click(submit);
    expect(await screen.findByRole("alert")).toHaveTextContent("Domain not approved.");
    await user.click(submit);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The product link could not be added.",
    );
    await user.click(submit);
    expect(add).toHaveBeenLastCalledWith({
      label: "Dashboard",
      url: "https://products.example.test/a",
      expiresAt: "2099-01-02T03:04:00.000Z",
    });
  });

  it("shows empty, unavailable and compact artefact metadata states", () => {
    const base: ProductArtefact = {
      id: "a",
      packageId: "p",
      position: 1,
      kind: "MANAGED_FILE",
      lifecycle: "FAILED",
      label: "Brief",
      filename: "brief.pdf",
      mediaType: "application/pdf",
      sizeBytes: 512,
      sha256: "a".repeat(64),
      version: 1,
      destinationDomain: null,
      expiresAt: null,
      scanResult: "FAILED",
      scanReason: "Mismatch",
      releasedAt: null,
    };
    const { rerender } = render(<PackageArtefactList artefacts={[]} />);
    expect(screen.getByText("No artefacts have been added to this version.")).toBeInTheDocument();
    rerender(<PackageArtefactList artefacts={[base]} customerAccess />);
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(formatBytes(null)).toBe("External link");
    expect(formatBytes(1_500)).toBe("1.5 KB");
    expect(formatBytes(2_000_000)).toBe("1.9 MB");
    expect(newProductKey()).toMatch(/^[0-9a-f-]{36}$/);
  });
});

function progress(filename: string, stage: ManagedUploadProgress["stage"]): ManagedUploadProgress {
  return {
    completeIdempotencyKey: `complete-${filename}`,
    createIdempotencyKey: `create-${filename}`,
    draft: {
      file: new File([filename], filename, { type: "application/pdf" }),
      label: filename,
      mediaType: "application/pdf",
      sha256: "a".repeat(64),
    },
    stage,
  };
}
