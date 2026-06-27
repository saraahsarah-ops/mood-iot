import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  // promesse jamais résolue -> on reste sur l'état "Chargement".
  getPatientHistory: vi.fn(() => new Promise(() => {})),
  generateAIAnalysis: vi.fn(async () => ({ analysis: "ok" })),
}));

import ClinicalHistory from "@/components/ClinicalHistory";

describe("ClinicalHistory", () => {
  it("affiche l'état de chargement initial", () => {
    render(<ClinicalHistory patientId="p1" />);
    expect(screen.getByText(/Chargement/)).toBeInTheDocument();
  });
});
