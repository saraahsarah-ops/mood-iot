import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SkeletonCard, SkeletonChart, SkeletonPulse } from "@/components/SkeletonCard";

describe("Skeletons", () => {
  it("se rendent sans planter", () => {
    expect(render(<SkeletonPulse />).container.firstChild).toBeTruthy();
    expect(render(<SkeletonCard />).container.firstChild).toBeTruthy();
    expect(render(<SkeletonChart />).container.firstChild).toBeTruthy();
  });
});
