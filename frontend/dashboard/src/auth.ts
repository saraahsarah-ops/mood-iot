/**
 * Configuration NextAuth.js (Auth.js v5) pour le dashboard médecin.
 *
 * Le dashboard délègue l'authentification à Keycloak (réalm `moodiot`,
 * client `dashboard-medecin`). NextAuth gère :
 *  - Flow OIDC Authorization Code + PKCE
 *  - Refresh automatique de l'access_token quand il expire
 *  - Session signée (cookie HttpOnly Secure SameSite=Lax)
 *
 * Les pages restent client-side (Next.js App Router "use client"). Le
 * token d'accès est exposé via `useSession()` pour les appels backend.
 */

import NextAuth, { type DefaultSession } from "next-auth";
import Keycloak from "next-auth/providers/keycloak";

// Étendre la session avec les champs Keycloak qui nous intéressent.
// En NextAuth v5 le module 'next-auth/jwt' n'est plus exporté séparément :
// les champs custom du JWT vivent désormais dans la même augmentation que
// la Session.
declare module "next-auth" {
  interface Session {
    accessToken?: string;
    // id_token Keycloak — utilisé comme id_token_hint pour le logout fédéré
    // (RP-initiated logout) afin de fermer aussi la session SSO Keycloak.
    idToken?: string;
    error?: "RefreshAccessTokenError";
    user: {
      id?: string;
      role?: string;
    } & DefaultSession["user"];
  }
  // Augment le JWT interne aussi
  interface JWT {
    accessToken?: string;
    refreshToken?: string;
    idToken?: string;
    accessTokenExpires?: number;
    roles?: string[];
    error?: "RefreshAccessTokenError";
  }
}

// Type local pour le JWT enrichi (NextAuth v5)
interface KeycloakJwt {
  accessToken?: string;
  refreshToken?: string;
  idToken?: string;
  accessTokenExpires?: number;
  roles?: string[];
  error?: "RefreshAccessTokenError";
  [k: string]: unknown;
}

/** Pick the application role from the realm roles array. */
function pickRole(roles: string[] | undefined): string | undefined {
  if (!roles) return undefined;
  for (const r of ["admin", "psychiatre", "patient"]) {
    if (roles.includes(r)) return r;
  }
  return undefined;
}

/** Decode the JWT payload without verifying — used to extract realm_access.roles. */
function decodePayload(token: string): Record<string, unknown> {
  const part = token.split(".")[1];
  const padded = part.replace(/-/g, "+").replace(/_/g, "/");
  const pad = "=".repeat((4 - (padded.length % 4)) % 4);
  if (typeof atob !== "undefined") {
    return JSON.parse(atob(padded + pad));
  }
  return JSON.parse(Buffer.from(padded + pad, "base64").toString());
}

async function refreshAccessToken(
  token: KeycloakJwt,
): Promise<{
  accessToken?: string;
  refreshToken?: string;
  accessTokenExpires?: number;
  error?: "RefreshAccessTokenError";
}> {
  try {
    const issuer = process.env.AUTH_KEYCLOAK_ISSUER;
    if (!issuer) throw new Error("AUTH_KEYCLOAK_ISSUER manquant");
    const resp = await fetch(`${issuer}/protocol/openid-connect/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        grant_type: "refresh_token",
        client_id: process.env.AUTH_KEYCLOAK_ID ?? "dashboard-medecin",
        client_secret: process.env.AUTH_KEYCLOAK_SECRET ?? "",
        refresh_token: token.refreshToken ?? "",
      }),
    });
    if (!resp.ok) throw new Error(`Keycloak refresh ${resp.status}`);
    const data = (await resp.json()) as {
      access_token: string;
      refresh_token?: string;
      expires_in: number;
    };
    return {
      accessToken: data.access_token,
      refreshToken: data.refresh_token ?? token.refreshToken,
      accessTokenExpires: Date.now() + (data.expires_in - 30) * 1000,
    };
  } catch {
    return { error: "RefreshAccessTokenError" };
  }
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Keycloak({
      clientId: process.env.AUTH_KEYCLOAK_ID ?? "dashboard-medecin",
      clientSecret: process.env.AUTH_KEYCLOAK_SECRET ?? "",
      issuer: process.env.AUTH_KEYCLOAK_ISSUER,
      // `prompt=login` force Keycloak à TOUJOURS afficher le formulaire de
      // connexion (email/mot de passe), même si une session SSO est encore
      // active côté Keycloak. Sans ça, après un premier login, cliquer
      // « Se connecter » ré-authentifie en silence et redirige direct vers le
      // dashboard. La page de login Keycloak porte aussi le lien
      // « Créer un compte » (registrationAllowed=true) pour l'inscription.
      authorization: { params: { prompt: "login" } },
    }),
  ],
  // Session strategy 'jwt' = NextAuth stocke l'access_token Keycloak dans le
  // cookie session signe (JWE par defaut). Le backend ne le voit jamais en clair.
  session: { strategy: "jwt" },
  callbacks: {
    async jwt({ token, account }) {
      const kc = token as KeycloakJwt;
      // Premier login : on copie l'access/refresh token Keycloak dans le JWT.
      if (account?.access_token) {
        const payload = decodePayload(account.access_token);
        const roles =
          (payload.realm_access as { roles?: string[] } | undefined)?.roles ??
          [];
        return {
          ...token,
          accessToken: account.access_token,
          refreshToken: account.refresh_token,
          idToken: account.id_token,
          accessTokenExpires: (account.expires_at ?? 0) * 1000,
          roles,
        } as KeycloakJwt;
      }
      // Si encore valide -> on garde tel quel.
      const exp = kc.accessTokenExpires;
      if (typeof exp === "number" && Date.now() < exp) {
        return token;
      }
      // Sinon -> tentative de refresh.
      const refreshed = await refreshAccessToken(kc);
      return { ...token, ...refreshed } as KeycloakJwt;
    },
    async session({ session, token }) {
      const kc = token as KeycloakJwt;
      session.accessToken = kc.accessToken;
      session.idToken = kc.idToken;
      session.error = kc.error;
      session.user.role = pickRole(kc.roles);
      return session;
    },
  },
  pages: {
    signIn: "/login",
    error: "/login",
  },
});
