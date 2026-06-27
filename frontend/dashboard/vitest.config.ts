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
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
});
