/**
 * Auth store — wrapper Zustand autour de la session Keycloak.
 *
 * Persiste le triplet (accessToken, refreshToken, idToken) + l'expiration
 * dans expo-secure-store. Le user interne (profil métier issu de /auth/me)
 * est rafraîchi à chaque démarrage et après un login.
 */

import { create } from "zustand";
import * as SecureStore from "expo-secure-store";
import * as kc from "@/services/auth";
import { fetchMe } from "@/services/api";

export interface AppUser {
  id: string;
  keycloak_id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: "patient" | "psychiatre" | "admin";
  registration_status: string;
}

interface PersistedTokens {
  accessToken: string;
  refreshToken: string;
  idToken?: string;
  expiresAt: number;
}

const TOKENS_KEY = "auth_tokens";
const USER_KEY = "auth_user";

interface AuthState {
  tokens: PersistedTokens | null;
  user: AppUser | null;
  loading: boolean;
  /** True pendant que `signIn` est en cours (ouverture du browser système). */
  signingIn: boolean;
  /** Erreur la plus récente (en français, affichable à l'utilisateur). */
  error: string | null;

  /** Restaure tokens + user au démarrage de l'app. */
  restore: () => Promise<void>;

  /** Lance le flow Keycloak (Google / Apple / email). */
  signIn: () => Promise<void>;

  /** Retourne un access token valide, rafraîchit silencieusement si besoin. */
  getValidAccessToken: () => Promise<string | null>;

  /** Force le rafraîchissement du profil utilisateur (/auth/me). */
  refreshUser: () => Promise<void>;

  /** Déconnexion complète (Keycloak + storage local). */
  signOut: () => Promise<void>;
}

async function loadTokens(): Promise<PersistedTokens | null> {
  const raw = await SecureStore.getItemAsync(TOKENS_KEY);
  return raw ? (JSON.parse(raw) as PersistedTokens) : null;
}

async function saveTokens(tokens: PersistedTokens): Promise<void> {
  await SecureStore.setItemAsync(TOKENS_KEY, JSON.stringify(tokens));
}

async function clearTokens(): Promise<void> {
  await SecureStore.deleteItemAsync(TOKENS_KEY);
  await SecureStore.deleteItemAsync(USER_KEY);
}

export const useAuthStore = create<AuthState>((set, get) => ({
  tokens: null,
  user: null,
  loading: true,
  signingIn: false,
  error: null,

  restore: async () => {
    try {
      const tokens = await loadTokens();
      const userJson = await SecureStore.getItemAsync(USER_KEY);
      if (tokens) {
        set({
          tokens,
          user: userJson ? (JSON.parse(userJson) as AppUser) : null,
          loading: false,
        });
        // Rafraîchit le profil en arrière-plan
        void get().refreshUser();
      } else {
        set({ loading: false });
      }
    } catch {
      set({ loading: false });
    }
  },

  signIn: async () => {
    set({ signingIn: true, error: null });
    try {
      const result = await kc.signInWithKeycloak();
      if (!result) {
        // Annulation utilisateur — pas une erreur
        set({ signingIn: false });
        return;
      }
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
      const message =
        err instanceof Error ? err.message : "Connexion impossible";
      set({ signingIn: false, error: message });
      throw err;
    }
  },

  getValidAccessToken: async () => {
    const current = get().tokens;
    if (!current) return null;
    if (Date.now() < current.expiresAt) {
      return current.accessToken;
    }
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
      // Refresh expiré / révoqué → on force le signout local
      await clearTokens();
      set({ tokens: null, user: null });
      return null;
    }
  },

  refreshUser: async () => {
    const accessToken = await get().getValidAccessToken();
    if (!accessToken) return;
    try {
      const me = await fetchMe(accessToken);
      await SecureStore.setItemAsync(USER_KEY, JSON.stringify(me));
      set({ user: me });
    } catch (err: unknown) {
      // Profil introuvable → l'utilisateur doit compléter son profil
      // (le flow welcome.tsx s'en chargera côté UI)
      if (err instanceof Error && err.message.includes("404")) {
        set({ user: null });
      }
    }
  },

  signOut: async () => {
    const current = get().tokens;
    if (current?.refreshToken) {
      await kc.signOut(current.refreshToken);
    }
    await clearTokens();
    set({ tokens: null, user: null, error: null });
  },
}));
