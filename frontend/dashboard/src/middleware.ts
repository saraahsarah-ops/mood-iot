import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Garde d'authentification côté serveur (edge).
 *
 * Le `RouteGate` client (src/app/layout.tsx) redirige déjà vers /login, mais
 * uniquement après hydratation → bref flash de contenu pour un visiteur non
 * authentifié. Ce middleware applique la garde AVANT le rendu : pas de flash,
 * et la protection ne dépend plus du JS client.
 *
 * On vérifie seulement la PRÉSENCE du cookie de session NextAuth (edge-safe,
 * pas d'import de la config auth). La validité réelle du token reste vérifiée
 * par l'app et par le backend à chaque appel API.
 *
 * Les routes publiques doivent refléter celles du RouteGate :
 *   exact  : /login, /register/doctor
 *   prefix : /privacy, /about, /api/auth
 * NB : /register/doctor/complete n'est PAS public (exige une session).
 */

const PUBLIC_EXACT = new Set(["/login", "/register/doctor"]);
const PUBLIC_PREFIX = ["/privacy", "/about", "/api/auth"];

function isPublic(pathname: string): boolean {
  if (PUBLIC_EXACT.has(pathname)) return true;
  return PUBLIC_PREFIX.some(
    (p) => pathname === p || pathname.startsWith(p + "/"),
  );
}

export function middleware(req: NextRequest): NextResponse {
  const { pathname } = req.nextUrl;
  if (isPublic(pathname)) return NextResponse.next();

  // Cookie de session NextAuth v5 — préfixe __Secure- en HTTPS (prod).
  const hasSession =
    req.cookies.has("authjs.session-token") ||
    req.cookies.has("__Secure-authjs.session-token");

  if (!hasSession) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  // Exclut les assets statiques du middleware.
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|icon-|apple-touch-icon|manifest).*)",
  ],
};
