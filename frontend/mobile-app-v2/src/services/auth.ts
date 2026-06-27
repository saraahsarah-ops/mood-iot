/**
 * Service d'authentification Keycloak (OIDC PKCE) — RN CLI pur.
 * Utilise react-native-app-auth pour le flow browser et fetch pour ROPC.
 */

import { authorize, refresh, revoke } from 'react-native-app-auth';

// ────────────────────────────────────────────────────────────────────────────
// Configuration — à externaliser dans un .env via react-native-config
// ────────────────────────────────────────────────────────────────────────────

const KEYCLOAK_BASE    = 'https://auth.mood-iot.fr/realms/moodiot';
const CLIENT_ID        = 'mobile-app';
const TOKEN_ENDPOINT   = `${KEYCLOAK_BASE}/protocol/openid-connect/token`;
const REDIRECT_URI     = 'mood-iot://callback';

/**
 * Scope minimal (aligné sur le curl).
 * Ajoute 'offline_access' ici si tu veux un refresh token de longue durée,
 * mais le client Keycloak doit avoir "Direct Access Grants" + offline_access activé.
 */
const SCOPES = ['openid', 'profile', 'email', 'offline_access'];
const SCOPE_STRING = SCOPES.join(' ');

const APP_AUTH_CONFIG = {
  issuer: KEYCLOAK_BASE,
  clientId: CLIENT_ID,
  redirectUrl: REDIRECT_URI,
  scopes: SCOPES,
  additionalParameters: { ui_locales: 'fr' },
};

// ────────────────────────────────────────────────────────────────────────────
// Types
// ────────────────────────────────────────────────────────────────────────────

export interface KeycloakTokens {
  accessToken: string;
  refreshToken: string;
  idToken?: string;
  expiresAt: number; // epoch ms
}

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  id_token?: string;
  expires_in: number;
}

// ────────────────────────────────────────────────────────────────────────────
// API publique
// ────────────────────────────────────────────────────────────────────────────

/**
 * Flow PKCE — ouvre le navigateur système vers Keycloak (Google, MFA…).
 */
export async function signInWithKeycloak(): Promise<KeycloakTokens | null> {
  try {
    const result = await authorize(APP_AUTH_CONFIG);
    return {
      accessToken: result.accessToken,
      refreshToken: result.refreshToken,
      idToken: result.idToken,
      expiresAt: new Date(result.accessTokenExpirationDate).getTime(),
    };
  } catch (err: unknown) {
    if (err instanceof Error && err.message.includes('cancel')) return null;
    throw err;
  }
}

/**
 * Login email + password direct (Resource Owner Password Grant).
 *
 * Équivalent exact du curl :
 *   curl -X POST https://auth.mood-iot.fr/realms/moodiot/protocol/openid-connect/token \
 *     -d "grant_type=password" \
 *     -d "client_id=mobile-app" \
 *     -d "username=<email>" \
 *     -d "password=<password>" \
 *     -d "scope=openid profile email offline_access"
 */
export async function signInWithPassword(
  email: string,
  password: string,
): Promise<KeycloakTokens> {
  const resp = await fetch(TOKEN_ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type:  'password',
      client_id:   CLIENT_ID,
      username:    email,
      password,
      scope:       SCOPE_STRING,
    }).toString(),
  });

  if (!resp.ok) {
    let detail = '';
    try {
      const body = await resp.json();
      detail = body.error_description ?? body.error ?? '';
    } catch { /* ignore */ }

    if (resp.status === 401 || detail.includes('Invalid user credentials')) {
      throw new Error('Email ou mot de passe incorrect.');
    }
    if (detail.includes('Account is not fully set up')) {
      throw new Error("Votre compte n'est pas finalisé. Vérifiez votre email.");
    }
    if (detail.includes('disabled')) {
      throw new Error('Votre compte est désactivé. Contactez le support.');
    }
    throw new Error(`Connexion impossible (HTTP ${resp.status})`);
  }

  const data: TokenResponse = await resp.json();
  return toTokens(data);
}

/**
 * Rafraîchit l'access token silencieusement.
 */
export async function refreshTokens(refreshToken: string): Promise<KeycloakTokens> {
  try {
    const result = await refresh(APP_AUTH_CONFIG, { refreshToken });
    return {
      accessToken: result.accessToken,
      refreshToken: result.refreshToken,
      idToken: result.idToken,
      expiresAt: new Date(result.accessTokenExpirationDate).getTime(),
    };
  } catch {
    // Fallback fetch direct si react-native-app-auth échoue
    const resp = await fetch(TOKEN_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        grant_type:    'refresh_token',
        client_id:     CLIENT_ID,
        refresh_token: refreshToken,
      }).toString(),
    });
    if (!resp.ok) throw new Error('Session expirée, veuillez vous reconnecter.');
    const data: TokenResponse = await resp.json();
    return toTokens(data);
  }
}

/**
 * Révoque la session côté Keycloak.
 */
export async function signOut(refreshToken: string): Promise<void> {
  try {
    await revoke(APP_AUTH_CONFIG, { tokenToRevoke: refreshToken, sendClientId: true });
  } catch {
    // Non bloquant — le store local sera nettoyé quoi qu'il arrive
  }
}

export function isExpired(tokens: KeycloakTokens | null): boolean {
  if (!tokens) return true;
  return Date.now() >= tokens.expiresAt;
}

// ────────────────────────────────────────────────────────────────────────────
// Helpers
// ────────────────────────────────────────────────────────────────────────────

function toTokens(t: TokenResponse): KeycloakTokens {
  return {
    accessToken:  t.access_token,
    refreshToken: t.refresh_token,
    idToken:      t.id_token,
    expiresAt:    Date.now() + (t.expires_in - 30) * 1000,
  };
}