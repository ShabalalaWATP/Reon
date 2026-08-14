import { expect, type Page } from "@playwright/test";

export async function buildAndSubmitPackage(page: Page, runId: string) {
  await page.getByRole("link", { name: "Start product package" }).click();
  await page.getByRole("button", { name: "Create release package" }).click();
  await expect(page.getByRole("heading", { name: "Build release package" })).toBeVisible();
  const label = `Synthetic browser product ${runId}`;
  const uploadForm = page.locator("form").filter({
    has: page.getByRole("heading", { name: "Upload for scanning" }),
  });
  await uploadForm.getByLabel("Product label").fill(label);
  await uploadForm.locator('input[type="file"]').setInputFiles({
    buffer: Buffer.from("%PDF-1.4\n% Synthetic browser assurance document\n%%EOF\n"),
    mimeType: "application/pdf",
    name: `synthetic-browser-product-${runId}.pdf`,
  });
  await uploadForm.getByRole("button", { name: "Upload artefact" }).click();
  await expect(
    page.getByRole("list", { name: "Package artefacts" }).getByText(label, { exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Covering note to Customer")
    .fill("Synthetic browser journey product, reviewed through the complete route.");
  await page.getByRole("button", { name: "Submit exact version for review" }).click();
  await expect(page.getByText("Awaiting Manager review", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Return to work queue" }).click();
}

export async function managerApprovePackage(page: Page) {
  await page.getByRole("link", { name: "Review product package" }).click();
  await page.getByRole("button", { name: "Approve exact package" }).click();
  await expect(page.getByText("Manager approved", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Return to work queue" }).click();
}

export async function inspectQcPackage(page: Page) {
  await page.getByRole("link", { name: "Review and release package" }).click();
  await expect(page.getByRole("heading", { name: "Package contents" })).toBeVisible();
  await expect(page.getByText(/^Manager approval:/u)).toBeVisible();
  await page.getByRole("link", { name: "Return to work queue" }).click();
}

export async function disseminatePackage(page: Page) {
  await page.getByRole("link", { name: "Review and release package" }).click();
  const externalAttestation = page.getByLabel("External access attested");
  if ((await externalAttestation.count()) > 0) await externalAttestation.check();
  await page.getByRole("button", { name: "Disseminate to Customer" }).click();
  await expect(page.getByText("Disseminated", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Return to work queue" }).click();
}
