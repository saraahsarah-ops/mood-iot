import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ScoreChart from "@/components/ScoreChart";

describe("ScoreChart", () => {
  it("se rend avec des données sans planter", () => {
    const data = [
      { date: "06-01", Hugo: 46, Marie: 30 },
      { date: "06-02", Hugo: 52, Marie: 28 },
    ];
    const { container } = render(<ScoreChart data={data} patients={["Hugo", "Marie"]} />);
    expect(container).toBeTruthy();
  });

  it("se rend avec des données vides", () => {
    const { container } = render(<ScoreChart data={[]} />);
    expect(container).toBeTruthy();
  });
});
