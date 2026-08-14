import { expect, type Page } from "@playwright/test";

export async function submitCustomerRequest(page: Page, title: string) {
  const date = futureDate(14);
  await page.goto("/requests/new");
  const values: Record<string, string> = {
    "Request title": title,
    "Description of the need": "Produce a synthetic browser-journey assurance product.",
    "Specific question to answer": "Does the complete synthetic route work correctly?",
    "Desired outcome": "A reviewed and released synthetic service product.",
    "Background and known context": "Synthetic CI evidence only.",
    "Subject area or location": "Synthetic browser assurance area",
    "Relevant period starts": date,
    "Relevant period ends": date,
    "Activity, project or decision supported": "A synthetic release assurance decision.",
    "Latest useful delivery date": date,
    "Why this date matters and impact if late": "It bounds the CI acceptance journey.",
    "Success criteria": "Customer receives and accepts the reviewed product.",
    "Constraints or caveats": "No known constraints.",
    "Supporting information available": "No supporting material is required.",
    "Handling instructions": "Standard synthetic-data handling applies.",
  };
  for (const [label, value] of Object.entries(values)) {
    await page.getByLabel(label).fill(value);
  }
  await page.getByLabel("Preferred product type").selectOption({ label: "Written report" });
  await page.getByRole("button", { name: "Submit request" }).click();
  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  const requestId = new URL(page.url()).pathname.split("/").at(-1);
  expect(requestId).toMatch(/^[0-9a-f-]{36}$/u);
  return requestId!;
}

function futureDate(days: number) {
  const date = new Date();
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}
