import { expect, type Page } from "@playwright/test";

import { selectOptionMatching } from "./browserSession";

/**
 * Staff work detail keeps correspondence in a collapsed section so the human
 * decision stays at the top; a closed details element hides its content from
 * role queries, so open it before working inside. Customer pages mount the
 * panel open and have no summary to click.
 */
export async function revealCorrespondence(page: Page) {
  const closedSummary = page.locator("details.queue-detail__correspondence:not([open]) > summary");
  const sendButton = page.getByRole("button", { name: "Send message" });
  // After a reload the panel arrives asynchronously: wait until either the
  // collapsed summary (staff pages) or the open panel's control (Customer
  // pages) is visible, then open the section if it is still closed.
  await expect(closedSummary.or(sendButton).first()).toBeVisible();
  if ((await closedSummary.count()) > 0) await closedSummary.first().click();
}

export async function sendConversation(
  page: Page,
  view: "Customer" | "Internal" | null,
  target: RegExp,
  subject: string,
  body: string,
) {
  await revealCorrespondence(page);
  const sendButton = page.getByRole("button", { name: "Send message" });
  await expect(sendButton).toBeEnabled();
  if (view) {
    const tab = page.getByRole("button", { name: view, exact: true });
    await tab.click();
    await expect(tab).toHaveAttribute("aria-pressed", "true");
  }
  await selectOptionMatching(page, "Send to", target);
  const selectedTarget = page.getByLabel("Send to").locator("option:checked");
  await expect(selectedTarget).toHaveText(target);
  const subjectField = page.getByLabel(/^Subject/u);
  const messageField = page.getByLabel("Message");
  await subjectField.fill(subject);
  await messageField.fill(body);
  await expect(subjectField).toHaveValue(subject);
  await expect(messageField).toHaveValue(body);
  const responsePromise = page.waitForResponse((response) => {
    const path = new URL(response.url()).pathname;
    return response.request().method() === "POST" && path.endsWith("/conversations/messages");
  });
  await sendButton.click();
  const response = await responsePromise;
  expect(response.ok(), `Conversation send returned ${response.status()}.`).toBe(true);
  await expect(
    page.getByRole("list", { name: "Recorded conversations" }).getByText(body, { exact: true }),
  ).toBeVisible();
  await expect(sendButton).toBeEnabled();
}

export async function expectConversationAfterReload(
  page: Page,
  body: string,
  view: "Customer" | "Internal" | null = null,
) {
  await page.reload();
  await revealCorrespondence(page);
  if (view) {
    await page.getByRole("button", { name: view, exact: true }).click();
  }
  await expect(
    page.getByRole("list", { name: "Recorded conversations" }).getByText(body, { exact: true }),
  ).toBeVisible();
}
