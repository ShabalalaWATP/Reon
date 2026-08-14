import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ProductArtefact } from "../../lib/api/productTypes";
import { PackageArtefactList } from "./PackageArtefactList";

const reviewArtefacts: ProductArtefact[] = [
  {
    id: "art-file",
    packageId: "pkg",
    position: 1,
    kind: "MANAGED_FILE",
    lifecycle: "CLEAN",
    label: "Decision brief",
    filename: "brief.pdf",
    mediaType: "application/pdf",
    sizeBytes: 10,
    sha256: "a".repeat(64),
    destinationDomain: null,
    reviewDestinationUrl: null,
    reviewUrl: "/api/v1/product-packages/artefacts/art-file/review",
    expiresAt: null,
    scanResult: "CLEAN",
    scanReason: null,
    releasedAt: null,
    version: 1,
  },
  {
    id: "art-link",
    packageId: "pkg",
    position: 2,
    kind: "EXTERNAL_LINK",
    lifecycle: "CLEAN",
    label: "Interactive product",
    filename: null,
    mediaType: null,
    sizeBytes: null,
    sha256: null,
    destinationDomain: "products.example.test",
    reviewDestinationUrl: "https://products.example.test/review?token=synthetic",
    reviewUrl: null,
    expiresAt: null,
    scanResult: null,
    scanReason: null,
    releasedAt: null,
    version: 1,
  },
];

describe("pre-release product artefacts", () => {
  it("shows exact staff-only file and destination inspection targets", () => {
    render(<PackageArtefactList artefacts={reviewArtefacts} />);
    expect(screen.getByRole("link", { name: "Inspect file" })).toHaveAttribute(
      "href",
      "/api/v1/product-packages/artefacts/art-file/review",
    );
    expect(screen.getByRole("link", { name: "Inspect file" })).toHaveAttribute("target", "_blank");
    expect(screen.getByRole("link", { name: "Inspect destination" })).toHaveAttribute(
      "rel",
      "noopener noreferrer",
    );
    expect(
      screen.getByText("https://products.example.test/review?token=synthetic"),
    ).toBeInTheDocument();
  });

  it("never exposes staff inspection targets in the Customer rendering", () => {
    render(<PackageArtefactList artefacts={reviewArtefacts} customerAccess />);
    expect(screen.queryByRole("link", { name: "Inspect file" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Inspect destination" })).not.toBeInTheDocument();
    expect(
      screen.queryByText("https://products.example.test/review?token=synthetic"),
    ).not.toBeInTheDocument();
  });
});
