import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next-auth/react", () => ({
  getSession: vi.fn(async () => ({ accessToken: "tok-test" })),
}));

import * as api from "@/lib/api";

function mockFetchOk(data: unknown = {}) {
  const fn = vi.fn(async () => ({
    ok: true,
    status: 200,
    statusText: "OK",
    json: async () => data,
  }));
  global.fetch = fn as any;
  return fn;
}
const url = (f: any) => f.mock.calls[0][0] as string;
const opts = (f: any) => f.mock.calls[0][1] ?? {};

beforeEach(() => vi.clearAllMocks());

describe("api client — chemins clés", () => {
  it("getPatients: GET + token", async () => {
    const f = mockFetchOk({ patients: [{ id: "1" }], total: 1 });
    const r = await api.getPatients(1, 50);
    expect(r.total).toBe(1);
    expect(url(f)).toContain("/patients");
    expect(opts(f).headers.Authorization).toBe("Bearer tok-test");
  });
  it("getScoreHistory: limit dans l'URL", async () => {
    const f = mockFetchOk({ scores: [] });
    await api.getScoreHistory("p1", 30);
    expect(url(f)).toContain("/scoring/history/p1?limit=30");
  });
  it("acknowledgeNotification: PUT", async () => {
    const f = mockFetchOk();
    await api.acknowledgeNotification("n1");
    expect(opts(f).method).toBe("PUT");
  });
  it("deletePatient: DELETE", async () => {
    const f = mockFetchOk();
    await api.deletePatient("p1");
    expect(opts(f).method).toBe("DELETE");
  });
  it("createTeleconsultSession: POST", async () => {
    const f = mockFetchOk({ id: "s1" });
    await api.createTeleconsultSession({
      patient_id: "p1", psychiatre_id: "d1",
      scheduled_at: "2026-07-01T15:00:00", duration_minutes: 30,
    } as any);
    expect(opts(f).method).toBe("POST");
  });
  it("propage l'erreur si !ok", async () => {
    global.fetch = vi.fn(async () => ({
      ok: false, status: 500, statusText: "err",
      json: async () => ({ detail: "boom" }),
    })) as any;
    await expect(api.getPatients()).rejects.toThrow("boom");
  });
  it("connectAlertWS construit un WebSocket", () => {
    const WS = vi.fn(function (this: any) { this.onmessage = null; });
    (global as any).WebSocket = WS;
    api.connectAlertWS("u1", () => {});
    expect(WS).toHaveBeenCalledOnce();
    expect(WS.mock.calls[0][0]).toContain("/notifications/ws/u1");
  });
});

describe("api client — toutes les fonctions appellent le fetcher", () => {
  const cas: Array<[string, () => Promise<unknown>]> = [
    ["getMyProfile", () => api.getMyProfile()],
    ["getPatient", () => api.getPatient("p1")],
    ["getPatientMetrics", () => api.getPatientMetrics("p1")],
    ["getLatestScore", () => api.getLatestScore("p1")],
    ["computeScore", () => api.computeScore("p1")],
    ["explainScore", () => api.explainScore("s1")],
    ["getAllNotifications", () => api.getAllNotifications()],
    ["getNotifications", () => api.getNotifications("p1")],
    ["deleteNotification", () => api.deleteNotification("n1")],
    ["getTeleconsultSessions", () => api.getTeleconsultSessions()],
    ["getTeleconsultSession", () => api.getTeleconsultSession("s1")],
    ["joinTeleconsultSession", () => api.joinTeleconsultSession("s1")],
    ["endTeleconsultSession", () => api.endTeleconsultSession("s1", {} as any)],
    ["deleteTeleconsultSession", () => api.deleteTeleconsultSession("s1")],
    ["getSessionNotes", () => api.getSessionNotes("s1")],
    ["addSessionNote", () => api.addSessionNote("s1", { content: "n" } as any)],
    ["registerDoctorProfile", () => api.registerDoctorProfile({} as any)],
    ["registerDoctor", () => api.registerDoctor({} as any)],
    ["getDoctorProfile", () => api.getDoctorProfile()],
    ["updateDoctorProfile", () => api.updateDoctorProfile({} as any)],
    ["getPendingDoctors", () => api.getPendingDoctors()],
    ["approveDoctor", () => api.approveDoctor("u1")],
    ["rejectDoctor", () => api.rejectDoctor("u1", "motif")],
    ["getInstitutionMembers", () => api.getInstitutionMembers()],
    ["addInstitutionMember", () => api.addInstitutionMember({} as any)],
    ["removeInstitutionMember", () => api.removeInstitutionMember("u1")],
    ["createPatient", () => api.createPatient({} as any)],
    ["updatePatient", () => api.updatePatient("p1", {} as any)],
    ["getPatientHistory", () => api.getPatientHistory("p1")],
    ["sendDirectMessage", () => api.sendDirectMessage("p1", "hola")],
    ["generateAIAnalysis", () => api.generateAIAnalysis("p1")],
  ];
  for (const [name, fn] of cas) {
    it(`${name} appelle fetch`, async () => {
      const f = mockFetchOk({});
      await fn();
      expect(f).toHaveBeenCalledOnce();
    });
  }
});
