"use client";

/**
 * Wrapper backward-compatible vers NextAuth.js.
 *
 * Avant la migration Keycloak, l'auth était gérée par un store Zustand.
 * Pour ne pas casser les dizaines de fichiers qui appellent
 * `useAuthStore((s) => s.user)` ou `useAuthStore().token`, on garde la
 * même API mais on délègue à `useSession()` de NextAuth.
 */

import { signIn, signOut, useSession } from "next-auth/react";
import { useMemo } from "react";

export interface AuthUser {
  id: string;
  email: string;
  role: string;
  first_name?: string;
  last_name?: string;
}

export interface AuthHookValue {
  token: string | null;
  user: AuthUser | null;
  isAuthenticated: boolean;
  error: string | null;
  loading: boolean;
  login: (kc_idp_hint?: string) => Promise<void>;
  logout: () => Promise<void>;
  /** No-op : NextAuth restaure automatiquement la session. Conservé pour compat. */
  restore: () => void;
}

/**
 * Hook backward-compatible. Trois formes d'appel acceptees :
 *
 *   const { token, user } = useAuthStore();
 *   const user = useAuthStore((s) => s.user);
 *   const token = useAuthStore((s) => s.token);
 */
export function useAuthStore(): AuthHookValue;
export function useAuthStore<T>(selector: (s: AuthHookValue) => T): T;
export function useAuthStore<T>(
  selector?: (s: AuthHookValue) => T,
): T | AuthHookValue {
  const { data: session, status } = useSession();

  const value = useMemo<AuthHookValue>(() => {
    const isAuthenticated =
      status === "authenticated" && !!session?.accessToken;
    const token = session?.accessToken ?? null;
    const sessionUser = session?.user;

    const user: AuthUser | null = sessionUser
      ? {
          id: (sessionUser.id as string | undefined) ?? "",
          email: sessionUser.email ?? "",
          role: (sessionUser.role as string | undefined) ?? "",
          first_name: sessionUser.name?.split(" ")[0],
          last_name: sessionUser.name?.split(" ").slice(1).join(" "),
        }
      : null;

    return {
      token,
      user,
      isAuthenticated,
      error:
        session?.error === "RefreshAccessTokenError"
          ? "Session expirée — veuillez vous reconnecter"
          : null,
      loading: status === "loading",
      login: async (kc_idp_hint?: string) => {
        const extra = kc_idp_hint ? { kc_idp_hint } : undefined;
        await signIn("keycloak", { redirectTo: "/" }, extra);
      },
      logout: async () => {
        await signOut({ redirectTo: "/login" });
      },
      restore: () => {
        /* NextAuth s'en charge automatiquement via SessionProvider. */
      },
    };
  }, [session, status]);

  if (selector) return selector(value);
  return value;
}
