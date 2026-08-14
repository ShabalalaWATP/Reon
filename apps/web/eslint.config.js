import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

import { frontendComplexityDebt } from "./scripts/complexity-baseline.js";

export default tseslint.config(
  { ignores: ["dist", "coverage"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: { ecmaVersion: 2022 },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      // New code starts at the target. Legacy orchestration modules are listed
      // in an exact, executable baseline which must shrink as they are split.
      complexity: ["error", { max: 12, variant: "modified" }],
      "max-depth": ["error", 4],
      // Keep the established Hooks correctness rules explicit. Version 7's
      // recommended preset also enables React Compiler rules, but this app
      // does not use the compiler and should not inherit that unrelated policy.
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
    },
  },
  {
    files: ["**/*.test.{ts,tsx}", "e2e/**/*.{ts,tsx}", "src/test/**/*.{ts,tsx}"],
    rules: { complexity: "off" },
  },
  ...Object.entries(frontendComplexityDebt).map(([file, maximum]) => ({
    files: [file],
    rules: { complexity: ["error", maximum] },
  })),
);
