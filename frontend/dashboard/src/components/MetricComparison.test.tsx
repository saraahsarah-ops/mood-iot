import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import MetricComparison from "@/components/MetricComparison";

describe("MetricComparison", () => {
  it("affiche le label, la valeur courante et la baseline", () => {
    render(
      <MetricComparison emoji="❤️" label="BPM" current={76} baseline={69} unit="bpm" />,
    );
    expect(screen.getByText("BPM")).toBeInTheDocument();
    expect(screen.getByText("76")).toBeInTheDocument();
    expect(screen.getByText(/ref 69/)).toBeInTheDocument();
  });
});
