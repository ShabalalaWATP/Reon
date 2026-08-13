import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const apiProxy = process.env.ISTARI_API_PROXY ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  build: {
    manifest: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": apiProxy,
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    testTimeout: 15_000,
    maxWorkers: 8,
    coverage: {
      provider: "v8",
      reporter: ["text", "json-summary", "html"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.test.{ts,tsx}", "src/main.tsx", "src/test/**", "src/vite-env.d.ts"],
      thresholds: {
        lines: 95,
        branches: 95,
        functions: 95,
        statements: 95,
      },
    },
  },
});
