import { defineConfig, devices } from "@playwright/test";

const inCi = Boolean(process.env.CI);

export default defineConfig({
  expect: { timeout: 15_000 },
  forbidOnly: inCi,
  fullyParallel: false,
  outputDir: "test-results",
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  reporter: inCi
    ? [["line"], ["html", { open: "never", outputFolder: "playwright-report" }]]
    : "list",
  retries: inCi ? 1 : 0,
  testDir: "./e2e",
  timeout: 12 * 60_000,
  use: {
    actionTimeout: 15_000,
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:5173",
    navigationTimeout: 30_000,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "off",
  },
  workers: 1,
});
