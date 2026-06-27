import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  getPatientHistory: vi.fn(async () => ({
    messages: [{ sender_id: "p1", content: "Bonjour docteur", sent_at: "2026-06-01T10:00:00" }],
  })),
  sendDirectMessage: vi.fn(async () => ({})),
}));

import Messagerie from "@/components/Messagerie";

describe("Messagerie", () => {
  it("charge et affiche les messages du patient", async () => {
    render(<Messagerie patientId="p1" />);
    expect(await screen.findByText("Bonjour docteur")).toBeInTheDocument();
  });
});
