"use client";
import { create } from "zustand";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8010/api/v1";

interface AuthUser {
  id: string;
  email: string;
  role: string;
  first_name?: string;
  last_name?: string;
}

interface AuthStore {
  token: string | null;
  refreshToken: string | null;
  user: AuthUser | null;
  isAuthenticated: boolean;
  error: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<boolean>;
  logout: () => void;
  restore: () => void;
}

export const useAuthStore = create<AuthStore>((set, get) => ({
  token: null,
  refreshToken: null,
  user: null,
  isAuthenticated: false,
  error: null,
  loading: false,

  login: async (email: string, password: string) => {
    set({ loading: true, error: null });
    try {
      const res = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        let msg = `Erreur serveur (${res.status})`;
        try {
          const body = await res.json();
          if (body.detail) msg = body.detail;
        } catch { /* ignore */ }
        if (res.status === 401 && !msg.includes("attente") && !msg.includes("rejet")) {
          msg = "Identifiants invalides";
        }
        set({ loading: false, error: msg });
        return false;
      }

      const data = await res.json();
      const user: AuthUser = data.user || {
        id: data.user_id || "",
        email: email,
        role: data.role || "",
      };

      localStorage.setItem("mood_token", data.access_token);
      localStorage.setItem("mood_refresh", data.refresh_token || "");
      localStorage.setItem("mood_user", JSON.stringify(user));

      set({
        token: data.access_token,
        refreshToken: data.refresh_token,
        user,
        isAuthenticated: true,
        loading: false,
        error: null,
      });
      return true;
    } catch {
      set({ loading: false, error: "Impossible de contacter le serveur" });
      return false;
    }
  },

  logout: () => {
    localStorage.removeItem("mood_token");
    localStorage.removeItem("mood_refresh");
    localStorage.removeItem("mood_user");
    set({
      token: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
      error: null,
    });
  },

  restore: () => {
    if (typeof window === "undefined") return;
    const token = localStorage.getItem("mood_token");
    const userJson = localStorage.getItem("mood_user");
    if (token && userJson) {
      try {
        const user = JSON.parse(userJson);
        set({ token, user, isAuthenticated: true });
      } catch {
        // invalid stored data
      }
    }
  },
}));
