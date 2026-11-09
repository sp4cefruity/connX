import { defineConfig } from "vitest/config";

// Pure-logic tests only (no DOM, no React): frontend/lib/**/*.test.ts.
export default defineConfig({
  test: {
    include: ["lib/**/*.test.ts"],
    environment: "node",
  },
});
