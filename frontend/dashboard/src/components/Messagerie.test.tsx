import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  getPatientHistory: vi.fn(async () => ({
    messages: [
      // Message du patient (sender = user du patient) -> à gauche
      { sender_id: "patient-user", content: "Bonjour docteur", sent_at: "2026-06-01T10:00:00" },
      // Message du médecin connecté (sender = son id interne) -> à droite
      { sender_id: "doc1", content: "Bonjour, comment allez-vous", sent_at: "2026-06-01T10:05:00" },
    ],
  })),
  sendDirectMessage: vi.fn(async () => ({})),
  getMyProfile: vi.fn(async () => ({ id: "doc1" })),
}));

import Messagerie from "@/components/Messagerie";

describe("Messagerie", () => {
  it("charge et affiche les messages du patient", async () => {
    render(<Messagerie patientId="p1" />);
    expect(await screen.findByText("Bonjour docteur")).toBeInTheDocument();
  });

  it("aligne ses messages à droite et ceux du patient à gauche", async () => {
    render(<Messagerie patientId="p1" />);
    const monMessage = await screen.findByText("Bonjour, comment allez-vous");
    const messagePatient = await screen.findByText("Bonjour docteur");

    // Le médecin connecté (doc1) : bulle primaire (droite).
    await waitFor(() =>
      expect(monMessage.closest("div")?.className).toContain("bg-primary-500"),
    );
    // Le patient : bulle grise (gauche) — NON primaire.
    expect(messagePatient.closest("div")?.className).toContain("bg-gray-100");
  });
});
