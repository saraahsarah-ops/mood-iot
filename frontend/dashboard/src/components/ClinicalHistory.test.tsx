import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { getPatientHistory, getPatientCoaching, generateAIAnalysis } = vi.hoisted(
  () => ({
    getPatientHistory: vi.fn(),
    getPatientCoaching: vi.fn(),
    generateAIAnalysis: vi.fn(),
  }),
);

vi.mock("@/lib/api", () => ({
  getPatientHistory,
  getPatientCoaching,
  generateAIAnalysis,
}));

import ClinicalHistory from "@/components/ClinicalHistory";

describe("ClinicalHistory", () => {
  it("affiche l'état de chargement initial", () => {
    // getPatientHistory ne résout jamais -> on reste sur "Chargement".
    getPatientHistory.mockReturnValue(new Promise(() => {}));
    getPatientCoaching.mockResolvedValue({ notifications: [] });
    render(<ClinicalHistory patientId="p1" />);
    expect(screen.getByText(/Chargement/)).toBeInTheDocument();
  });

  it("affiche les recommandations de coaching IA envoyées au patient", async () => {
    getPatientHistory.mockResolvedValue({
      teleconsults: [],
      notes: [],
      messages: [],
    });
    getPatientCoaching.mockResolvedValue({
      notifications: [
        {
          id: "c1",
          title: "Coaching",
          body: "Pensez à dormir 8h par nuit",
          created_at: "2026-06-28T10:00:00",
          status: "sent",
        },
      ],
      total: 1,
      unread: 0,
    });
    render(<ClinicalHistory patientId="p1" />);
    expect(
      await screen.findByText("Pensez à dormir 8h par nuit"),
    ).toBeInTheDocument();
  });
});
