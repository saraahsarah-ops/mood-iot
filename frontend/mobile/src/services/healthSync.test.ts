import { toPayload } from "./healthSync";

describe("toPayload", () => {
  it("mappe DayMetrics vers le payload backend", () => {
    const day = {
      date: "2026-06-01",
      heartRateAvg: 70,
      hrv: 42,
      sleepMinutes: 430,
      steps: 6500,
      screenTimeMin: 300,
    } as any;
    const p = toPayload(day);
    expect(p.date).toBe("2026-06-01");
    expect(p.heart_rate_avg).toBe(70);
    expect(p.sleep_duration_min).toBe(430);
    expect(p.step_count).toBe(6500);
    expect(["ios_healthkit", "android_health_connect"]).toContain(p.source_platform);
  });
});
