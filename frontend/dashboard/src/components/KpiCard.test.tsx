import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import KpiCard from "@/components/KpiCard";

describe("KpiCard", () => {
  it("affiche le label, la valeur et l'emoji", () => {
    render(<KpiCard label="Alertes critiques" value={3} emoji="🔴" color="danger" />);
    expect(screen.getByText("Alertes critiques")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("🔴")).toBeInTheDocument();
  });

  it("affiche la tendance quand elle est fournie", () => {
    render(
      <KpiCard
        label="Score moyen"
        value={29}
        emoji="📊"
        color="primary"
        trend={{ value: 5, label: "vs hier" }}
      />,
    );
    expect(screen.getByText(/5% vs hier/)).toBeInTheDocument();
  });
});
