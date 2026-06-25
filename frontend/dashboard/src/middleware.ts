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
 * IMPORTANT — chunking des cookies : quand le JWT dépasse ~4 Ko (ce qui est
 * notre cas, car on stocke l'id_token pour le logout fédéré), NextAuth scinde
 * le cookie en `<nom>.0`, `<nom>.1`, … et il n'existe alors AUCUN cookie au
 * nom exact `__Secure-authjs.session-token`. Un simple `cookies.has(nom)`
 * renvoie donc false et le middleware rejette une session pourtant valide
 * (-> boucle de redirection vers /login). On détecte donc aussi les chunks.
 *
 * Les routes publiques doivent refléter celles du RouteGate :
 *   exact  : /login, /register/doctor
 *   prefix : /privacy, /about, /api/auth
 * NB : /register/doctor/complete n'est PAS public (exige une session).
 */

const PUBLIC_EXACT = new Set(["/login", "/register/doctor"]);
const PUBLIC_PREFIX = ["/privacy", "/about", "/api/auth"];

// Noms de base du cookie de session NextAuth v5 (préfixe __Secure- en HTTPS).
const SESSION_COOKIE_BASES = [
  "authjs.session-token",
  "__Secure-authjs.session-token",
];

function isPublic(pathname: string): boolean {
  if (PUBLIC_EXACT.has(pathname)) return true;
  return PUBLIC_PREFIX.some(
    (p) => pathname === p || pathname.startsWith(p + "/"),
  );
}

/**
 * Vrai si un cookie de session est présent, qu'il soit entier
 * (`__Secure-authjs.session-token`) ou scindé en chunks
 * (`__Secure-authjs.session-token.0`, `.1`, …).
 */
function hasSessionCookie(req: NextRequest): boolean {
  return req.cookies
    .getAll()
    .some((c) =>
      SESSION_COOKIE_BASES.some(
        (base) => c.name === base || c.name.startsWith(base + "."),
      ),
    );
}

export function middleware(req: NextRequest): NextResponse {
  const { pathname } = req.nextUrl;
  if (isPublic(pathname)) return NextResponse.next();

  if (!hasSessionCookie(req)) {
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
