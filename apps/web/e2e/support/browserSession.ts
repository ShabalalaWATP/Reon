import { expect, type Page } from "@playwright/test";

export class BrowserIssueMonitor {
  private readonly issues: string[] = [];

  attach(page: Page) {
    page.on("console", (message) => {
      const networkError = message.text().startsWith("Failed to load resource:");
      if (message.type() === "error" && !networkError) {
        this.issues.push(`console: ${message.text()}`);
      }
    });
    page.on("pageerror", (error) => {
      this.issues.push(`page: ${error.message}`);
    });
    page.on("requestfailed", (request) => {
      const reason = request.failure()?.errorText ?? "unknown network failure";
      if (reason !== "net::ERR_ABORTED") {
        this.issues.push(`request: ${request.method()} ${request.url()} (${reason})`);
      }
    });
    page.on("response", (response) => {
      const expectedAnonymousProbe =
        response.status() === 401 && new URL(response.url()).pathname === "/api/v1/auth/me";
      if (response.status() >= 400 && !expectedAnonymousProbe) {
        this.issues.push(
          `response: ${response.request().method()} ${response.url()} (${response.status()})`,
        );
      }
    });
  }

  assertClean() {
    expect(this.issues, this.issues.join("\n")).toEqual([]);
  }
}

export async function signIn(page: Page, username: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Account ID").fill(username);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in to ISTARI" }).click();
  await expect(page.getByRole("button", { name: /^Open account menu for /u })).toBeVisible();
}

async function signOut(page: Page) {
  await page.getByRole("button", { name: /^Open account menu for /u }).click();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
}

export async function switchIdentity(page: Page, username: string, password: string) {
  await signOut(page);
  await signIn(page, username, password);
}

export async function switchContext(page: Page, context: "Customer" | "Staff") {
  await page.getByRole("button", { name: /^Open account menu for /u }).click();
  await page.getByRole("button", { name: `Switch to ${context} context` }).click();
  if (context === "Customer") {
    await expect(page.getByRole("heading", { name: "My requests" })).toBeVisible();
    return;
  }
  await expect(page).toHaveURL(/\/overview$/u);
  await expect(page.getByText("Staff context", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Home", exact: true })).toHaveAttribute(
    "aria-current",
    "page",
  );
}

export async function selectOptionMatching(page: Page, fieldLabel: string, optionLabel: RegExp) {
  const select = page.getByLabel(fieldLabel);
  const option = select.locator("option").filter({ hasText: optionLabel }).first();
  await expect(option).toBeAttached();
  const value = await option.getAttribute("value");
  expect(value).not.toBeNull();
  await select.selectOption(value!);
}
