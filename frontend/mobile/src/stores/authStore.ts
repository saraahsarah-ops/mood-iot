import { create } from "zustand";
import * as SecureStore from "expo-secure-store";
import * as api from "@/services/api";

interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
}

interface AuthState {
  token: string | null;
  user: User | null;
  loading: boolean;

  /** Restaure le token depuis SecureStore au demarrage */
  restore: () => Promise<void>;

  /** Login email/password */
  login: (email: string, password: string) => Promise<void>;

  /** Deconnexion */
  logout: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  user: null,
  loading: true,

  restore: async () => {
    try {
      const token = await SecureStore.getItemAsync("auth_token");
      const userJson = await SecureStore.getItemAsync("auth_user");
      if (token && userJson) {
        set({ token, user: JSON.parse(userJson), loading: false });
      } else {
        set({ loading: false });
      }
    } catch {
      set({ loading: false });
    }
  },

  login: async (email, password) => {
    const res = await api.login(email, password);
    await SecureStore.setItemAsync("auth_token", res.access_token);
    await SecureStore.setItemAsync("auth_user", JSON.stringify(res.user));
    set({ token: res.access_token, user: res.user });
  },

  logout: async () => {
    await SecureStore.deleteItemAsync("auth_token");
    await SecureStore.deleteItemAsync("auth_user");
    set({ token: null, user: null });
  },
}));
