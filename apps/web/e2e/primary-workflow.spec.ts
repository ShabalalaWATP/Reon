import { expect, test } from "@playwright/test";

import {
  BrowserIssueMonitor,
  signIn,
  switchContext,
  switchIdentity,
} from "./support/browserSession";
import { expectConversationAfterReload, sendConversation } from "./support/conversationUi";
import {
  buildAndSubmitPackage,
  disseminatePackage,
  inspectQcPackage,
  managerApprovePackage,
} from "./support/productUi";
import { submitCustomerRequest } from "./support/requestUi";
import {
  assignLeadAnalyst,
  chooseOutcome,
  openWorkItem,
  routeWorkItem,
  submitOutcome,
} from "./support/workflowUi";

test("complete staffed route preserves identity, correspondence and release boundaries", async ({
  page,
}) => {
  const password = process.env.E2E_PASSWORD;
  if (!password) throw new Error("E2E_PASSWORD is required for the browser journey.");
  const monitor = new BrowserIssueMonitor();
  monitor.attach(page);
  const runId = crypto.randomUUID().slice(0, 8);
  const title = `Synthetic browser route ${runId}`;
  const customerMessage = `Customer-visible synthetic update ${runId}.`;
  const customerReply = `Synthetic Customer acknowledgement ${runId}.`;
  const internalMessage = `Internal OSG Manager question ${runId}.`;
  let requestId = "";

  await test.step("Customer signs in and submits a structured request", async () => {
    await signIn(page, "admin2", password);
    requestId = await submitCustomerRequest(page, title);
  });

  await test.step("JIOC routes the request to DIGOC", async () => {
    await switchIdentity(page, "admin4", password);
    await openWorkItem(page, "/triage", requestId, title);
    await routeWorkItem(page, "Route to command", /^DIGOC ·/u, {
      kind: "select",
      label: "Priority",
      value: "High",
    });
  });

  await test.step("DIGOC routes the request to NCGI-A Ops", async () => {
    await switchIdentity(page, "admin5", password);
    await openWorkItem(page, "/coordination", requestId, title);
    await routeWorkItem(page, "Route to Ops group", /^NCGI-A Ops ·/u, {
      label: "Routing note",
      value: "Synthetic route to the primary operations group.",
    });
  });

  await test.step("NCGI-A Ops routes the request to OSG Team", async () => {
    await switchIdentity(page, "admin6", password);
    await openWorkItem(page, "/allocation", requestId, title);
    await routeWorkItem(page, "Route to team", /^OSG Team ·/u, {
      label: "Required capabilities",
      value: "Synthetic browser assurance\nStructured writing",
    });
  });

  await test.step("OSG Manager assigns Ben Doak as Lead Analyst", async () => {
    await switchIdentity(page, "admin8", password);
    await openWorkItem(page, "/delivery/team", requestId, title);
    await assignLeadAnalyst(
      page,
      "Ben Doak",
      "Selected to lead the bounded synthetic browser assurance journey.",
    );
  });

  await test.step("dual-context switching clears protected staff data", async () => {
    await switchIdentity(page, "admin13", password);
    await openWorkItem(page, "/delivery/my-work", requestId, title);
    await expect(page.getByRole("heading", { name: title, level: 2 })).toBeVisible();
    await switchContext(page, "Customer");
    await expect(page.getByText(title, { exact: true })).toHaveCount(0);
    await switchContext(page, "Staff");
    await openWorkItem(page, "/delivery/my-work", requestId, title);
  });

  await test.step("Analyst records Customer and internal correspondence", async () => {
    await sendConversation(
      page,
      "Customer",
      /^Customer$/u,
      `Synthetic Customer update ${runId}`,
      customerMessage,
    );
    await sendConversation(
      page,
      "Internal",
      /^OSG Team Managers$/u,
      `Synthetic Manager question ${runId}`,
      internalMessage,
    );
  });

  await test.step("Customer sees only Customer-visible correspondence after reload", async () => {
    await switchIdentity(page, "admin2", password);
    await page.goto(`/requests/${requestId}`);
    await expect(page.getByText(customerMessage, { exact: true })).toBeVisible();
    await expect(page.getByText(internalMessage, { exact: true })).toHaveCount(0);
    await expectConversationAfterReload(page, customerMessage);
    await sendConversation(
      page,
      null,
      /.+/u,
      `Synthetic Customer response ${runId}`,
      customerReply,
    );
  });

  await test.step("Analyst assembles and submits an immutable product package", async () => {
    await switchIdentity(page, "admin13", password);
    await openWorkItem(page, "/delivery/my-work", requestId, title);
    await expect(page.getByText(customerReply, { exact: true })).toBeVisible();
    await buildAndSubmitPackage(page, runId);
    await openWorkItem(page, "/delivery/my-work", requestId, title);
    await chooseOutcome(page, "Submit product");
    await submitOutcome(page, "Submit product");
  });

  await test.step("OSG Manager sees internal history and approves the exact package", async () => {
    await switchIdentity(page, "admin8", password);
    await openWorkItem(page, "/delivery/team", requestId, title);
    await expectConversationAfterReload(page, internalMessage, "Internal");
    await managerApprovePackage(page);
    await openWorkItem(page, "/delivery/team", requestId, title);
    await chooseOutcome(page, "Approve");
    await submitOutcome(page, "Approve");
  });

  await test.step("QC reviewer checks the Manager-approved package", async () => {
    await switchIdentity(page, "admin15", password);
    await openWorkItem(page, "/quality-release", requestId, title);
    await inspectQcPackage(page);
    await openWorkItem(page, "/quality-release", requestId, title);
    await chooseOutcome(page, "Approve");
    await submitOutcome(page, "Approve");
  });

  await test.step("a distinct release Manager disseminates the approved package", async () => {
    await switchIdentity(page, "admin100", password);
    await openWorkItem(page, "/quality-release", requestId, title);
    await disseminatePackage(page);
    await openWorkItem(page, "/quality-release", requestId, title);
    await chooseOutcome(page, "Disseminate to customer");
    await submitOutcome(page, "Disseminate to customer");
  });

  await test.step("Customer retrieves and accepts the disseminated product", async () => {
    await switchIdentity(page, "admin2", password);
    await page.goto(`/requests/${requestId}`);
    await expect(page.getByRole("heading", { name: "Product available" })).toBeVisible();
    await expect(
      page.getByText("Synthetic browser journey product, reviewed through the complete route."),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "Download" })).toBeVisible();
    await page.getByRole("button", { name: "Accept product" }).click();
    await expect(page.getByText(/^Accepted /u)).toBeVisible();
  });

  monitor.assertClean();
});
