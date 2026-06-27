import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import PatientCard from "@/components/PatientCard";

describe("PatientCard", () => {
  it("affiche le nom et le coaching", () => {
    render(<PatientCard name="Hugo Petit" score={46} coaching="Sommeil perturbé" />);
    expect(screen.getByText("Hugo Petit")).toBeInTheDocument();
    expect(screen.getByText(/Sommeil perturbé/)).toBeInTheDocument();
  });
});
