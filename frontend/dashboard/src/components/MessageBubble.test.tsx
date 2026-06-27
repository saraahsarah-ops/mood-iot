import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import MessageBubble from "@/components/MessageBubble";

describe("MessageBubble", () => {
  it("affiche le texte du message", () => {
    render(<MessageBubble role="medecin" texte="Bonjour, comment allez-vous ?" heure="10:30" />);
    expect(screen.getByText("Bonjour, comment allez-vous ?")).toBeInTheDocument();
  });
});
