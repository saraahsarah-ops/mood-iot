import { describe, expect, it } from "vitest";

import { getRiskColor, getRiskEmoji, getRiskLabel } from "@/lib/types";

describe("getRiskColor", () => {
  it("score < 40 -> success", () => {
    expect(getRiskColor(0)).toBe("success");
    expect(getRiskColor(39.9)).toBe("success");
  });
  it("40 <= score < 70 -> warning", () => {
    expect(getRiskColor(40)).toBe("warning");
    expect(getRiskColor(69.9)).toBe("warning");
  });
  it("score >= 70 -> danger", () => {
    expect(getRiskColor(70)).toBe("danger");
    expect(getRiskColor(100)).toBe("danger");
  });
});

describe("getRiskLabel", () => {
  it("retourne le bon libellé par tranche", () => {
    expect(getRiskLabel(20)).toBe("Stable");
    expect(getRiskLabel(50)).toBe("À surveiller");
    expect(getRiskLabel(85)).toBe("Critique");
  });
});

describe("getRiskEmoji", () => {
  it("retourne le bon emoji par tranche", () => {
    expect(getRiskEmoji(20)).toBe("🟢");
    expect(getRiskEmoji(50)).toBe("🟡");
    expect(getRiskEmoji(85)).toBe("🔴");
  });
});
