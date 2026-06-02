/**
 * Mood-IoT : service d'authentification Keycloak (OIDC PKCE).
 *
 * Keycloak est la source de vérité de l'identité. Ce module expose le hook
 * `useKeycloakAuth` et les helpers `refreshTokens` / `signOut` que
 * l'authStore utilise pour stocker les tokens dans expo-secure-store.
 */

import * as AuthSession from "expo-auth-session";
import * as WebBrowser from "expo-web-browser";

// Permet à WebBrowser de capturer le retour de la redirection sur iOS
WebBrowser.maybeCompleteAuthSession();

// ────────────────────────────────────────────────────────────────────────────
// Configuration
// ────────────────────────────────────────────────────────────────────────────

const DISCOVERY_URL =
  process.env.EXPO_PUBLIC_KEYCLOAK_DISCOVERY ??
  "http://10.0.2.2:8080/realms/moodiot/.well-known/openid-configuration";

const CLIENT_ID =
  process.env.EXPO_PUBLIC_KEYCLOAK_CLIENT_ID ?? "mobile-app";

const ISSUER = (() => {
  try {
    return DISCOVERY_URL.replace(/\/\.well-known\/openid-configuration\/?$/, "");
  } catch {
    return DISCOVERY_URL;
  }
})();

const TOKEN_ENDPOINT = `${ISSUER}/protocol/openid-connect/token`;
const END_SESSION_ENDPOINT = `${ISSUER}/protocol/openid-connect/logout`;

// Redirect URI dérivée du scheme `mood-iot` déclaré dans app.json
export const REDIRECT_URI = AuthSession.makeRedirectUri({
  scheme: "mood-iot",
  path: "callback",
});

const SCOPES = ["openid", "profile", "email", "offline_access"];

// ────────────────────────────────────────────────────────────────────────────
// Types
// ────────────────────────────────────────────────────────────────────────────

export interface KeycloakTokens {
  accessToken: string;
  refreshToken: string;
  idToken?: string;
  /** Epoch ms à laquelle accessToken expire. */
  expiresAt: number;
}

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  id_token?: string;
  expires_in: number;
  token_type: string;
}

// ────────────────────────────────────────────────────────────────────────────
// Discovery (lazy, mis en cache module-level)
// ────────────────────────────────────────────────────────────────────────────

let _discoveryCache: AuthSession.DiscoveryDocument | null = null;

async function getDiscovery(): Promise<AuthSession.DiscoveryDocument> {
  if (_discoveryCache) return _discoveryCache;
  const discovery = await AuthSession.fetchDiscoveryAsync(ISSUER);
  _discoveryCache = discovery;
  return discovery;
}

// ────────────────────────────────────────────────────────────────────────────
// API publique
// ────────────────────────────────────────────────────────────────────────────

/**
 * Lance le flow OIDC PKCE en ouvrant le navigateur système vers Keycloak.
 * Retourne les tokens à la réussite, ou null si l'utilisateur annule.
 */
export async function signInWithKeycloak(): Promise<KeycloakTokens | null> {
  const discovery = await getDiscovery();

  const request = new AuthSession.AuthRequest({
    clientId: CLIENT_ID,
    scopes: SCOPES,
    redirectUri: REDIRECT_URI,
    usePKCE: true,
    responseType: AuthSession.ResponseType.Code,
    extraParams: {
      // Force l'UI Keycloak en français
      ui_locales: "fr",
    },
  });

  const result = await request.promptAsync(discovery);

  if (result.type !== "success") {
    return null;
  }

  const code = result.params.code;
  if (!code) {
    throw new Error("Pas de code d'autorisation reçu de Keycloak");
  }

  const tokenResult = await AuthSession.exchangeCodeAsync(
    {
      clientId: CLIENT_ID,
      code,
      redirectUri: REDIRECT_URI,
      extraParams: request.codeVerifier
        ? { code_verifier: request.codeVerifier }
        : undefined,
    },
    discovery
  );

  return toKeycloakTokens({
    access_token: tokenResult.accessToken,
    refresh_token: tokenResult.refreshToken ?? "",
    id_token: tokenResult.idToken,
    expires_in: tokenResult.expiresIn ?? 300,
    token_type: tokenResult.tokenType ?? "Bearer",
  });
}

/**
 * Rafraîchit l'access token via grant_type=refresh_token.
 * Levée si le refresh token est expiré/révoqué — l'appelant doit relancer
 * `signInWithKeycloak` pour récupérer.
 */
export async function refreshTokens(
  refreshToken: string
): Promise<KeycloakTokens> {
  const resp = await fetch(TOKEN_ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "refresh_token",
      client_id: CLIENT_ID,
      refresh_token: refreshToken,
    }).toString(),
  });

  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`Refresh token Keycloak rejeté (${resp.status}) : ${body}`);
  }

  const data: TokenResponse = await resp.json();
  return toKeycloakTokens(data);
}

/**
 * Révoque la session Keycloak et invalide le refresh token côté serveur.
 */
export async function signOut(refreshToken: string): Promise<void> {
  try {
    await fetch(END_SESSION_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        client_id: CLIENT_ID,
        refresh_token: refreshToken,
      }).toString(),
    });
  } catch {
    // Échec côté serveur non bloquant — on clear le local quoi qu'il arrive
  }
}

// ────────────────────────────────────────────────────────────────────────────
// Helpers
// ────────────────────────────────────────────────────────────────────────────

function toKeycloakTokens(t: TokenResponse): KeycloakTokens {
  return {
    accessToken: t.access_token,
    refreshToken: t.refresh_token,
    idToken: t.id_token,
    // 30s de marge pour éviter les requêtes émises juste avant expiration
    expiresAt: Date.now() + (t.expires_in - 30) * 1000,
  };
}

export function isExpired(tokens: KeycloakTokens | null): boolean {
  if (!tokens) return true;
  return Date.now() >= tokens.expiresAt;
}
