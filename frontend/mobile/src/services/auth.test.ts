// makeRedirectUri s'exécute à l'import de auth.ts (REDIRECT_URI) et nécessite
// la config de scheme Expo, absente en test -> on stube expo-auth-session.
jest.mock("expo-auth-session", () => ({
  makeRedirectUri: jest.fn(() => "mood-iot://callback"),
  exchangeCodeAsync: jest.fn(),
  refreshAsync: jest.fn(),
}));

import { isExpired } from "./auth";

describe("isExpired", () => {
  it("retourne true si tokens absents", () => {
    expect(isExpired(null)).toBe(true);
  });
  it("retourne true si le token est expiré", () => {
    expect(isExpired({ expiresAt: Date.now() - 1000 } as any)).toBe(true);
  });
  it("retourne false si le token est encore valide", () => {
    expect(isExpired({ expiresAt: Date.now() + 60_000 } as any)).toBe(false);
  });
});
