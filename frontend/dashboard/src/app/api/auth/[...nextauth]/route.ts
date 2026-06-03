/**
 * Route handler NextAuth.js (Auth.js v5).
 *
 * Expose les endpoints :
 *   - GET/POST /api/auth/signin
 *   - GET/POST /api/auth/signout
 *   - GET/POST /api/auth/callback/keycloak
 *   - GET     /api/auth/session
 *   - GET     /api/auth/csrf
 *   - GET     /api/auth/providers
 */

import { handlers } from "@/auth";

export const { GET, POST } = handlers;
