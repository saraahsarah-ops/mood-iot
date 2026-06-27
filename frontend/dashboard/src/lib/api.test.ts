import { beforeEach, describe, expect, it, vi } from "vitest";

// getSession (next-auth) est appelé par le fetcher pour récupérer le token.
vi.mock("next-auth/react", () => ({
  getSession: vi.fn(async () => ({ accessToken: "tok-test" })),
}));

import {
  acknowledgeNotification,
  createTeleconsultSession,
  deleteNotification,
  getLatestScore,
  getPatients,
  getScoreHistory,
  getTeleconsultSessions,
} from "@/lib/api";

function mockFetchOk(data: unknown) {
  const fn = vi.fn(async () => ({
    ok: true,
    status: 200,
    statusText: "OK",
    json: async () => data,
  }));
  global.fetch = fn as any;
  return fn;
}

function lastUrl(fn: any): string {
  return fn.mock.calls[0][0] as string;
}
function lastOpts(fn: any): any {
  return fn.mock.calls[0][1] ?? {};
}

beforeEach(() => vi.clearAllMocks());

describe("api client (fetcher)", () => {
  it("getPatients -> GET /patients avec token", async () => {
    const f = mockFetchOk({ patients: [{ id: "1" }], total: 1 });
    const r = await getPatients(1, 50);
    expect(r.total).toBe(1);
    expect(lastUrl(f)).toContain("/patients");
    expect(lastOpts(f).headers.Authorization).toBe("Bearer tok-test");
  });

  it("getLatestScore -> /scoring/latest/{id}", async () => {
    const f = mockFetchOk({ score: 50 });
    await getLatestScore("p1");
    expect(lastUrl(f)).toContain("/scoring/latest/p1");
  });

  it("getScoreHistory inclut le limit", async () => {
    const f = mockFetchOk({ scores: [] });
    await getScoreHistory("p1", 30);
    expect(lastUrl(f)).toContain("/scoring/history/p1?limit=30");
  });

  it("getTeleconsultSessions -> /teleconsult/sessions", async () => {
    const f = mockFetchOk({ sessions: [], total: 0 });
    await getTeleconsultSessions();
    expect(lastUrl(f)).toContain("/teleconsult/sessions");
  });

  it("acknowledgeNotification -> PUT", async () => {
    const f = mockFetchOk({});
    await acknowledgeNotification("n1");
    expect(lastUrl(f)).toContain("/notifications/n1/acknowledge");
    expect(lastOpts(f).method).toBe("PUT");
  });

  it("deleteNotification -> DELETE", async () => {
    const f = mockFetchOk({});
    await deleteNotification("n1");
    expect(lastOpts(f).method).toBe("DELETE");
  });

  it("createTeleconsultSession -> POST", async () => {
    const f = mockFetchOk({ id: "s1" });
    await createTeleconsultSession({
      patient_id: "p1",
      psychiatre_id: "d1",
      scheduled_at: "2026-07-01T15:00:00",
      duration_minutes: 30,
    } as any);
    expect(lastOpts(f).method).toBe("POST");
  });

  it("propage l'erreur si la réponse n'est pas ok", async () => {
    global.fetch = vi.fn(async () => ({
      ok: false,
      status: 500,
      statusText: "err",
      json: async () => ({ detail: "boom" }),
    })) as any;
    await expect(getPatients()).rejects.toThrow("boom");
  });
});
