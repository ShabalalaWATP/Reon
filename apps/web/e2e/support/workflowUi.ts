import { expect, type Page } from "@playwright/test";

import { selectOptionMatching } from "./browserSession";

export type QueueRoute =
  | "/triage"
  | "/coordination"
  | "/allocation"
  | "/delivery/team"
  | "/delivery/my-work"
  | "/quality-release";

export async function openWorkItem(
  page: Page,
  route: QueueRoute,
  requestId: string,
  title: string,
) {
  const path = `${route}?requestId=${encodeURIComponent(requestId)}`;
  await expect(async () => {
    await page.goto(path);
    await expect(queueRow(page, title)).toBeVisible({ timeout: 2_000 });
  }).toPass({ intervals: [500, 1_000, 2_000], timeout: 90_000 });
  await queueRow(page, title).click();
  const claim = page.getByRole("button", { name: "Claim work item" });
  if (await claim.isVisible()) {
    await claim.click();
    await expect(claim).toBeHidden();
  }
  await expect(page.getByRole("heading", { name: title, level: 2 })).toBeVisible();
}

export async function routeWorkItem(
  page: Page,
  action: string,
  destination: RegExp,
  extra: { kind?: "select"; label: string; value: string },
) {
  await chooseOutcome(page, action);
  await selectOptionMatching(page, "Destination unit", destination);
  if (extra.kind === "select") {
    await page.getByLabel(extra.label).selectOption({ label: extra.value });
  } else {
    await page.getByLabel(extra.label).fill(extra.value);
  }
  await submitOutcome(page, action);
}

export async function assignLeadAnalyst(page: Page, analyst: string, reason: string) {
  await chooseOutcome(page, "Assign Analysts");
  await page.getByLabel("Lead Analyst").selectOption({ label: analyst });
  await page.getByLabel("Assignment reason").fill(reason);
  await submitOutcome(page, "Assign Analysts");
}

export async function submitOutcome(page: Page, action: string) {
  await page.getByRole("button", { name: action, exact: true }).click();
  await expect(page.getByRole("button", { name: action, exact: true })).toBeHidden();
}

export async function chooseOutcome(page: Page, action: string) {
  await page.getByLabel("Outcome").selectOption({ label: action });
  await expect(page.getByRole("button", { name: action, exact: true })).toBeEnabled();
}

function queueRow(page: Page, title: string) {
  return page.getByRole("button").filter({ has: page.getByText(title, { exact: true }) });
}
