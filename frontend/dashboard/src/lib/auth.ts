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

/**
 * Extrait l'`iss` (URL de l'émetteur Keycloak) du payload de l'id_token.
 * Évite d'avoir à exposer l'issuer via une variable NEXT_PUBLIC_* : il est
 * déjà présent dans l'id_token. Retourne null si le token est illisible.
 */
function issuerFromIdToken(idToken: string): string | null {
  try {
    const part = idToken.split(".")[1];
    const padded = part.replace(/-/g, "+").replace(/_/g, "/");
    const pad = "=".repeat((4 - (padded.length % 4)) % 4);
    const payload = JSON.parse(atob(padded + pad)) as { iss?: unknown };
    return typeof payload.iss === "string" ? payload.iss : null;
  } catch {
    return null;
  }
}

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
        // Logout fédéré (RP-initiated logout) : on ferme d'abord la session
        // NextAuth, puis on redirige vers le `end_session_endpoint` de Keycloak
        // pour fermer aussi la session SSO. Sans ça, la cookie SSO Keycloak
        // survit au logout et la connexion suivante ré-authentifie en silence.
        const idToken = session?.idToken;
        await signOut({ redirect: false });
        const issuer = idToken ? issuerFromIdToken(idToken) : null;
        if (issuer && idToken) {
          const url = new URL(`${issuer}/protocol/openid-connect/logout`);
          url.searchParams.set("id_token_hint", idToken);
          url.searchParams.set(
            "post_logout_redirect_uri",
            `${window.location.origin}/login`,
          );
          window.location.href = url.toString();
        } else {
          // Repli : pas d'id_token disponible → logout local uniquement.
          window.location.href = "/login";
        }
      },
      restore: () => {
        /* NextAuth s'en charge automatiquement via SessionProvider. */
      },
    };
  }, [session, status]);

  if (selector) return selector(value);
  return value;
}
