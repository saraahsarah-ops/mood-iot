import path from "path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Configuration Vitest pour le dashboard (React 18 + Next 14).
// Environnement jsdom pour tester les composants ; alias "@" -> src.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      // Couverture mesurée sur le code unit-testable (composants + lib) ;
      // les pages app/ (data fetching) relèvent des tests E2E (Playwright).
      include: ["src/components/**", "src/lib/**"],
      exclude: ["**/*.test.{ts,tsx}"],
      reporter: ["text", "text-summary"],
      // Gate « ratchet » : on interdit de redescendre. À relever à chaque lot.
      thresholds: { statements: 80, lines: 80 },
    },
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
});
