import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import NotificationCard from "@/components/NotificationCard";

describe("NotificationCard", () => {
  it("affiche le nom du patient et le message", () => {
    render(
      <NotificationCard
        patientName="Marie Dupont"
        score={75}
        level={2}
        message="Score de risque élevé"
        time="10:30"
        read={false}
      />,
    );
    expect(screen.getByText(/Marie Dupont/)).toBeInTheDocument();
    expect(screen.getByText(/Score de risque élevé/)).toBeInTheDocument();
  });
});
