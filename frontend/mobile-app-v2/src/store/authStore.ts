/**
 * Auth store — Zustand + react-native-keychain (RN CLI pur, sans Expo).
 */

import { create } from 'zustand';
import * as Keychain from 'react-native-keychain';
import * as kc from '../services/auth';

export interface AppUser {
  id: string;           // user id de /auth/me → utilisé comme sender_id dans les messages
  patient_id?: string;  // id de /patients/me → utilisé pour /patients/{id}/metrics
  keycloak_id?: string;
  email: string;
  first_name: string;
  last_name: string;
  date_of_birth?: string;
  gender?: string;
  phone?: string | null;
  psychiatre_id?: string;
  role?: 'patient' | 'psychiatre' | 'admin';
  registration_status?: string;
  created_at?: string;
  updated_at?: string;
}

interface PersistedTokens {
  accessToken: string;
  refreshToken: string;
  idToken?: string;
  expiresAt: number;
}

const KEYCHAIN_SERVICE_TOKENS = 'mood_iot_tokens';
const KEYCHAIN_SERVICE_USER   = 'mood_iot_user';

const API = 'https://api.mood-iot.fr/api/v1';

// ────────────────────────────────────────────────────────────────────────────
// Keychain helpers
// ────────────────────────────────────────────────────────────────────────────

async function loadTokens(): Promise<PersistedTokens | null> {
  const creds = await Keychain.getGenericPassword({ service: KEYCHAIN_SERVICE_TOKENS });
  if (!creds) return null;
  try { return JSON.parse(creds.password) as PersistedTokens; } catch { return null; }
}

async function saveTokens(tokens: PersistedTokens): Promise<void> {
  await Keychain.setGenericPassword('tokens', JSON.stringify(tokens), {
    service: KEYCHAIN_SERVICE_TOKENS,
    accessible: Keychain.ACCESSIBLE.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
  });
}

async function loadUser(): Promise<AppUser | null> {
  const creds = await Keychain.getGenericPassword({ service: KEYCHAIN_SERVICE_USER });
  if (!creds) return null;
  try { return JSON.parse(creds.password) as AppUser; } catch { return null; }
}

async function saveUser(user: AppUser): Promise<void> {
  await Keychain.setGenericPassword('user', JSON.stringify(user), {
    service: KEYCHAIN_SERVICE_USER,
  });
}

async function clearAll(): Promise<void> {
  await Keychain.resetGenericPassword({ service: KEYCHAIN_SERVICE_TOKENS });
  await Keychain.resetGenericPassword({ service: KEYCHAIN_SERVICE_USER });
}

// ────────────────────────────────────────────────────────────────────────────
// Store
// ────────────────────────────────────────────────────────────────────────────

interface AuthState {
  tokens: PersistedTokens | null;
  user: AppUser | null;
  loading: boolean;
  signingIn: boolean;
  error: string | null;

  restore: () => Promise<void>;
  signInWithEmailPassword: (email: string, password: string) => Promise<void>;
  signIn: () => Promise<void>;
  getValidAccessToken: () => Promise<string | null>;
  refreshUser: () => Promise<void>;
  signOut: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  tokens: null,
  user: null,
  loading: true,
  signingIn: false,
  error: null,

  restore: async () => {
    try {
      const [tokens, user] = await Promise.all([loadTokens(), loadUser()]);
      set({ tokens, user, loading: false });
      if (tokens) void get().refreshUser();
    } catch {
      set({ loading: false });
    }
  },

  signInWithEmailPassword: async (email, password) => {
    set({ signingIn: true, error: null });
    try {
      const result = await kc.signInWithPassword(email.trim(), password);
      const tokens: PersistedTokens = {
        accessToken: result.accessToken,
        refreshToken: result.refreshToken,
        idToken: result.idToken,
        expiresAt: result.expiresAt,
      };
      await saveTokens(tokens);
      set({ tokens });
      await get().refreshUser();
      set({ signingIn: false });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Connexion impossible';
      set({ signingIn: false, error: message });
      throw err;
    }
  },

  signIn: async () => {
    set({ signingIn: true, error: null });
    try {
      const result = await kc.signInWithKeycloak();
      if (!result) { set({ signingIn: false }); return; }
      const tokens: PersistedTokens = {
        accessToken: result.accessToken,
        refreshToken: result.refreshToken,
        idToken: result.idToken,
        expiresAt: result.expiresAt,
      };
      await saveTokens(tokens);
      set({ tokens });
      await get().refreshUser();
      set({ signingIn: false });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Connexion impossible';
      set({ signingIn: false, error: message });
      throw err;
    }
  },

  getValidAccessToken: async () => {
    const current = get().tokens;
    if (!current) return null;
    if (Date.now() < current.expiresAt) return current.accessToken;
    try {
      const refreshed = await kc.refreshTokens(current.refreshToken);
      const next: PersistedTokens = {
        accessToken: refreshed.accessToken,
        refreshToken: refreshed.refreshToken,
        idToken: refreshed.idToken,
        expiresAt: refreshed.expiresAt,
      };
      await saveTokens(next);
      set({ tokens: next });
      return next.accessToken;
    } catch {
      await clearAll();
      set({ tokens: null, user: null });
      return null;
    }
  },

  refreshUser: async () => {
    const token = await get().getValidAccessToken();
    if (!token) return;
    try {
      // Appels parallèles :
      // - /auth/me    → id (sender_id dans les messages du tchat)
      // - /patients/me → patient_id (pour /patients/{id}/metrics)
      const [authResp, patientResp] = await Promise.all([
        fetch(`${API}/auth/me`,     { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API}/patients/me`, { headers: { Authorization: `Bearer ${token}` } }),
      ]);

      if (!authResp.ok) {
        if (authResp.status === 404 || authResp.status === 401) set({ user: null });
        return;
      }

      const authMe = await authResp.json();

      let patient_id: string | undefined;
      if (patientResp.ok) {
        const patientMe = await patientResp.json();
        patient_id = patientMe.patient_id ?? patientMe.id;
      }

      const user: AppUser = { ...authMe, patient_id };
      await saveUser(user);
      set({ user });
    } catch { /* réseau indisponible — on garde le cache */ }
  },

  signOut: async () => {
    const current = get().tokens;
    if (current?.refreshToken) await kc.signOut(current.refreshToken);
    await clearAll();
    set({ tokens: null, user: null, error: null });
  },
}));