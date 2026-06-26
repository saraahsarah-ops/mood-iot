"""
Test E2E du dashboard médecin Mood-IoT (système DÉPLOYÉ — https://dashboard.mood-iot.fr).

Exécute les cas de test visuels/fonctionnels du dashboard, capture des
preuves (screenshots) dans le dossier QA Evidencias et imprime un rapport
PASS/FAIL + un fichier resultats.json.

Les identifiants viennent de variables d'environnement (jamais en dur) :
    MOODIOT_USER  (def. dr.martin@example.test)
    MOODIOT_PASS  (OBLIGATOIRE — le mot de passe du compte médecin de test)

Prérequis (une seule fois) :
    pip install playwright
    playwright install chromium

Lancement (PowerShell) :
    $env:MOODIOT_PASS = "Martin2026!"
    python qa/e2e_dashboard.py

Lancement (bash) :
    MOODIOT_PASS='Martin2026!' python qa/e2e_dashboard.py

Option : ajouter --headed pour voir le navigateur.
"""

import base64
import json
import os
import re
import sys
from pathlib import Path

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

# --- Configuration --------------------------------------------------------

BASE_URL = "https://dashboard.mood-iot.fr"
USER = os.environ.get("MOODIOT_USER", "dr.martin@example.test")
PASS = os.environ.get("MOODIOT_PASS")

# Dossier des preuves (Google Drive synchronisé)
EVID_DIR = Path(
    r"G:/Mi unidad/MS ADE/Cursos Master ADE/FIL ROUGE/Diagramas Drawio"
    r"/QA Evidencias/evidencias/2026-06-24_desplegado"
)

# Patients attendus dans le dashboard (simulateur)
EXPECTED_PATIENTS = ["Hugo", "Marie", "Léa", "Emma", "Paul"]

HEADED = "--headed" in sys.argv

results = []


def record(tc, nom, ok, detail, evidence=""):
    """Enregistre le résultat d'un cas de test."""
    statut = "Réussi" if ok else "Échoué"
    results.append(
        {
            "tc": tc,
            "nom": nom,
            "statut": statut,
            "detail": detail,
            "evidence": evidence,
        }
    )
    icone = "OK " if ok else "XX "
    print(f"  {icone}{tc}  {nom}  ->  {statut}")
    if detail:
        print(f"       {detail}")


def shot(page, filename):
    """Capture d'écran sauvegardée dans le dossier des preuves."""
    path = EVID_DIR / filename
    page.screenshot(path=str(path), full_page=True)
    return filename


def dismiss_cookies(page):
    """Ferme le bandeau de consentement cookies s'il est présent (il
    intercepte sinon les clics sur les cartes/boutons en bas de page)."""
    try:
        btn = page.get_by_role("button", name="Accepter")
        if btn.count() > 0 and btn.first.is_visible():
            btn.first.click(timeout=3000)
            page.wait_for_timeout(500)
    except Exception:
        pass


def main():
    if not PASS:
        print(
            "ERREUR : la variable MOODIOT_PASS n'est pas définie.\n"
            "  PowerShell : $env:MOODIOT_PASS = '...'\n"
            "  bash       : MOODIOT_PASS='...' python qa/e2e_dashboard.py"
        )
        sys.exit(1)

    EVID_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n=== Test E2E dashboard Mood-IoT (DÉPLOYÉ) ===")
    print(f"Cible    : {BASE_URL}")
    print(f"Médecin  : {USER}")
    print(f"Preuves  : {EVID_DIR}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not HEADED)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="fr-FR",
        )
        page = context.new_page()

        # --- Instrumentation diagnostique (flow OIDC) --------------------
        console_msgs = []
        auth_chain = []
        page.on("console", lambda m: console_msgs.append(f"{m.type}: {m.text[:200]}"))

        def _on_response(resp):
            u = resp.url
            if "/api/auth/" in u or "openid-connect" in u or "/login" in u:
                loc = ""
                try:
                    loc = resp.headers.get("location", "")
                except Exception:
                    pass
                auth_chain.append(
                    f"{resp.status} {resp.request.method} {u[:140]}"
                    + (f"  ->  Location: {loc[:140]}" if loc else "")
                )

        page.on("response", _on_response)

        def diag(page):
            print("\n--- DIAGNOSTIC OIDC ---")
            print(f"URL finale (complète): {page.url}")
            print("\nChaîne de requêtes auth (status method url -> redirect):")
            for line in auth_chain[-25:]:
                print(f"  {line}")
            cookies = context.cookies()
            names = [c["name"] for c in cookies]
            session_cookies = [n for n in names if "session" in n.lower() or "auth" in n.lower()]
            print(f"\nCookies posés ({len(names)}): {names}")
            print(f"Cookies de session/auth: {session_cookies or 'AUCUN (-> session NextAuth jamais créée)'}")

            # Décisif : que renvoie /api/auth/session avec ces cookies ?
            # {} => session vide (JWT illisible, bug config/taille) ; user => bug redirect.
            try:
                r = context.request.get(f"{BASE_URL}/api/auth/session")
                body = r.text()
                print(f"\n/api/auth/session -> HTTP {r.status}")
                print(f"Body (300c): {body[:300]}")
                # taille totale des chunks de session-token
                tok = sum(len(c.get("value", "")) for c in cookies if "session-token" in c["name"])
                print(f"Taille totale session-token (tous chunks): {tok} octets"
                      + ("  [>4096 = JWT volumineux, chunké]" if tok > 4096 else ""))
            except Exception as ex:
                print(f"\n/api/auth/session -> erreur fetch: {ex}")
            errs = [m for m in console_msgs if m.startswith("error") or "error" in m.lower()]
            if errs:
                print(f"\nErreurs console ({len(errs)}):")
                for e in errs[-12:]:
                    print(f"  {e}")
            print("--- FIN DIAGNOSTIC ---\n")

        # --- 1. Page de login (TC-UC3-13) --------------------------------
        print("[1] Page de login")
        page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        body = page.inner_text("body")
        login_ok = "Mood-IoT" in body and "connecter" in body.lower()
        ev = shot(page, "TC-UC3-13_page_login.png")
        record(
            "TC-UC3-13",
            "Page de login dashboard (branding Mood-IoT)",
            login_ok,
            "Branding Mood-IoT + bouton Se connecter visibles" if login_ok else f"Contenu inattendu: {body[:120]}",
            ev,
        )

        # --- 2. Thème Keycloak (TC-UC3-15) -------------------------------
        # Le bouton "Se connecter" appelle signIn("keycloak") (NextAuth) qui
        # fait un redirect différé : il faut attendre l'hydratation React puis
        # que l'URL passe sur auth.mood-iot.fr (pas un simple networkidle).
        print("[2] Redirection Keycloak + thème")
        try:
            page.wait_for_timeout(1800)  # laisser React s'hydrater
            page.get_by_role("button", name="Se connecter").click(timeout=10000)
            # attendre le formulaire Keycloak (champ username) plutôt que l'évent
            # 'load' (un thème Keycloak peut avoir des ressources lentes).
            page.wait_for_selector("#username", state="visible", timeout=30000)
            kbody = page.inner_text("body")
            theme_ok = "Mood-IoT" in kbody or "mood-iot" in page.content().lower()
            ev = shot(page, "TC-UC3-15_theme_keycloak.png")
            record(
                "TC-UC3-15",
                "Thème Keycloak personnalisé Mood-IoT",
                theme_ok,
                f"URL={page.url}",
                ev,
            )
        except PWTimeout as e:
            record("TC-UC3-15", "Thème Keycloak personnalisé", False, f"Redirect Keycloak non détecté: {e}")
            shot(page, "TC-UC3-15_echec.png")
            browser.close()
            _dump()
            return

        # --- 3. Login (identifiants depuis l'environnement) --------------
        print("[3] Authentification")
        try:
            page.wait_for_selector("#username", state="visible", timeout=15000)
            page.fill("#username", USER)
            page.fill("#password", PASS)
            page.click("#kc-login, input[type=submit], button[type=submit]")
            page.wait_for_timeout(3500)  # laisser le POST + redirect se faire

            # MFA/OTP éventuel : Keycloak peut demander un code TOTP
            if "auth.mood-iot.fr" in page.url:
                kbody = page.inner_text("body").lower()
                if any(t in kbody for t in ["otp", "code", "authentifica", "vérification", "totp"]):
                    shot(page, "TC-UC3-AUTH_mfa.png")
                    record(
                        "TC-UC3-AUTH",
                        "Connexion médecin via Keycloak (OIDC)",
                        False,
                        "Keycloak demande un code MFA/TOTP — non automatisable (à saisir manuellement)",
                        "TC-UC3-AUTH_mfa.png",
                    )
                    browser.close()
                    _dump()
                    return
                # sinon, erreur d'identifiants probable
                err = page.locator(".alert-error, #input-error, .pf-c-alert").count()
                shot(page, "TC-UC3-AUTH_echec.png")
                record(
                    "TC-UC3-AUTH",
                    "Connexion médecin via Keycloak (OIDC)",
                    False,
                    f"Toujours sur Keycloak après submit (erreur identifiants ? alertes={err}) URL={page.url}",
                    "TC-UC3-AUTH_echec.png",
                )
                browser.close()
                _dump()
                return

            page.wait_for_url(f"{BASE_URL}/**", timeout=20000)
            # NE PAS attendre 'networkidle' : le dashboard ouvre un WebSocket
            # (notifications temps réel) → le réseau n'est jamais "idle".
            page.wait_for_load_state("domcontentloaded", timeout=15000)
            page.wait_for_timeout(4000)  # laisser charger les données (KPIs/patients)
            logged_in = BASE_URL in page.url and "/login" not in page.url
            record(
                "TC-UC3-AUTH",
                "Connexion médecin via Keycloak (OIDC)",
                logged_in,
                f"URL après login={page.url}",
            )
            if not logged_in:
                shot(page, "TC-UC3-AUTH_echec.png")
                diag(page)
                browser.close()
                _dump()
                return
        except PWTimeout as e:
            record("TC-UC3-AUTH", "Connexion médecin", False, f"Timeout/échec login: {e}")
            shot(page, "TC-UC3-AUTH_echec.png")
            browser.close()
            _dump()
            return

        # --- 4. Vue générale : KPIs + liste patients ---------------------
        print("[4] Vue générale (KPIs + patients)")
        page.wait_for_timeout(1500)
        dismiss_cookies(page)  # sinon le bandeau intercepte les clics
        dash_body = page.inner_text("body")
        found = [pat for pat in EXPECTED_PATIENTS if pat in dash_body]
        patients_ok = len(found) >= 4
        ev = shot(page, "TC-UC9-01_vue_generale.png")
        record(
            "TC-UC9-01",
            "Vue générale : liste des patients chargée",
            patients_ok,
            f"Patients trouvés: {found} ({len(found)}/{len(EXPECTED_PATIENTS)})",
            ev,
        )

        # KPIs (cartes de synthèse) — on cherche des libellés probables
        kpi_terms = ["patient", "alerte", "score", "moyen"]
        kpi_hits = [t for t in kpi_terms if t in dash_body.lower()]
        record(
            "TC-UC9-02",
            "Vue générale : cartes KPI affichées",
            len(kpi_hits) >= 2,
            f"Termes KPI détectés: {kpi_hits}",
            ev,
        )

        # --- 5. Fiche patient : BPM arrondi + métriques + courbe 30j -----
        print("[5] Fiche patient")
        try:
            # La CARTE patient affiche "Prénom I." (ex. "Hugo P.") alors que la
            # LÉGENDE du graphe affiche juste "Hugo". On cible donc la carte via
            # le motif "Prénom <Initiale>." pour ne pas cliquer la légende.
            target = found[0] if found else EXPECTED_PATIENTS[0]
            card = page.get_by_text(
                re.compile(rf"\b{re.escape(target)}\s+[A-ZÀ-Ÿ]\.")
            ).first
            card.click(timeout=10000)
            page.wait_for_url("**/patient**", timeout=15000)
            page.wait_for_load_state("domcontentloaded", timeout=15000)
            page.wait_for_timeout(4000)
            dismiss_cookies(page)
            fiche_body = page.inner_text("body")
            ev = shot(page, "TC-UC9-03_fiche_patient.png")
            on_fiche = "/patient" in page.url
            if not on_fiche:
                record("TC-UC9-03", "Navigation vers la fiche patient", False,
                        f"N'a pas navigué vers /patient (URL={page.url})", ev)

            # BPM doit être un entier (pas 65.6630...)
            bpm_matches = re.findall(r"(\d+(?:\.\d+)?)\s*bpm", fiche_body, re.IGNORECASE)
            bpm_floats = [m for m in bpm_matches if "." in m]
            bpm_ok = len(bpm_matches) > 0 and len(bpm_floats) == 0
            record(
                "TC-UC9-04",
                "Fiche patient : BPM arrondi (entier)",
                bpm_ok,
                f"Valeurs bpm détectées: {bpm_matches or 'aucune'}"
                + (f" — DÉCIMALES TROUVÉES: {bpm_floats}" if bpm_floats else ""),
                ev,
            )

            # Métriques présentes (pas/sommeil/écran)
            metric_terms = ["pas", "sommeil", "écran", "fréquence", "cardiaque"]
            metric_hits = [t for t in metric_terms if t in fiche_body.lower()]
            record(
                "TC-UC9-05",
                "Fiche patient : métriques bien-être affichées",
                len(metric_hits) >= 2,
                f"Métriques détectées: {metric_hits}",
                ev,
            )

            # Bouton "Teleconsultation" du header de la fiche (écrit SANS accent
            # dans l'UI -> recherche accent-insensible via le stem "consultation",
            # rôle=button pour ne pas matcher le lien de nav latéral).
            tc_btn = page.get_by_role(
                "button", name=re.compile("consultation", re.I)
            ).count()
            record(
                "TC-UC9-06",
                "Fiche patient : bouton Téléconsultation (ouvre le modal)",
                tc_btn > 0,
                f"Boutons 'consultation' dans la fiche: {tc_btn}",
                ev,
            )

            # Courbe d'évolution (SVG / canvas du graphe)
            chart = page.locator("svg, canvas").count()
            chart_ok = chart > 0 and ("évolution" in fiche_body.lower() or "score" in fiche_body.lower())
            record(
                "TC-UC9-07",
                "Fiche patient : courbe d'évolution des scores",
                chart_ok,
                f"Éléments graphiques (svg/canvas): {chart}",
                ev,
            )
        except PWTimeout as e:
            record("TC-UC9-03", "Fiche patient", False, f"Timeout: {e}")

        # --- 6. Téléconsultation : dropdown patients ---------------------
        # Le dropdown n'existe que DANS le modal ouvert par "+ Nouvelle session"
        # (pas sur la page par défaut). Il faut donc ouvrir le modal d'abord.
        print("[6] Page téléconsultation")
        try:
            page.goto(f"{BASE_URL}/teleconsult", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            dismiss_cookies(page)
            page.get_by_role("button", name=re.compile("Nouvelle session", re.I)).first.click(timeout=10000)
            page.wait_for_selector("select", state="visible", timeout=10000)
            page.wait_for_timeout(1500)
            tbody = page.inner_text("body")
            ev = shot(page, "TC-UC5-01_teleconsult_dropdown.png")
            # 1er <select> = liste des patients ; ses <option> (hors placeholder)
            opt_count = page.locator("select").first.locator("option").count()
            tfound = [pat for pat in EXPECTED_PATIENTS if pat in tbody]
            tc_ok = opt_count > 1  # > 1 car la 1re option est "Sélectionner..."
            record(
                "TC-UC5-01",
                "Téléconsultation : dropdown patients peuplé (bug 422 corrigé)",
                tc_ok,
                f"options={opt_count} (dont placeholder), patients dans le modal={tfound}",
                ev,
            )
        except PWTimeout as e:
            record("TC-UC5-01", "Téléconsultation dropdown", False, f"Timeout: {e}")

        # --- 7. Onglets de la fiche : Historique Clinique & IA + Messagerie
        print("[7] Onglets fiche (Historique IA + Messagerie)")
        try:
            page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            dismiss_cookies(page)
            target = found[0] if found else EXPECTED_PATIENTS[0]
            page.get_by_text(
                re.compile(rf"\b{re.escape(target)}\s+[A-ZÀ-Ÿ]\.")
            ).first.click(timeout=10000)
            page.wait_for_url("**/patient**", timeout=15000)
            page.wait_for_timeout(3000)
            dismiss_cookies(page)

            # Onglet Historique Clinique & IA
            page.get_by_role("button", name=re.compile("Historique", re.I)).first.click(timeout=8000)
            page.wait_for_timeout(3000)
            hist_body = page.inner_text("body")
            ev = shot(page, "TC-UC9-11_onglet_historique_IA.png")
            hist_ok = "historique" in hist_body.lower()
            record("TC-UC9-11", "Fiche : onglet Historique Clinique & IA",
                    hist_ok, f"Onglet rendu (longueur texte={len(hist_body)})", ev)

            # Explications IA / facteurs / déviations (UC6-05 + UC6-03)
            ia_terms = ["facteur", "déviation", "deviation", "score", "ia",
                        "shap", "risque", "rechute", "z-score", "baseline"]
            ia_hits = [t for t in ia_terms if t in hist_body.lower()]
            record("TC-UC6-05", "Explications du score (facteurs/déviations) visibles",
                    len(ia_hits) >= 2, f"Termes IA/explication détectés: {ia_hits}", ev)

            # Onglet Messagerie
            page.get_by_role("button", name=re.compile("Messagerie", re.I)).first.click(timeout=8000)
            page.wait_for_timeout(2500)
            msg_body = page.inner_text("body")
            ev = shot(page, "TC-UC9-12_onglet_messagerie.png")
            has_input = page.locator("textarea, input[type=text]").count() > 0
            record("TC-UC9-12", "Fiche : onglet Messagerie (zone de saisie)",
                    has_input, f"Champs de saisie détectés: {has_input}", ev)
        except PWTimeout as e:
            record("TC-UC9-11", "Onglets fiche", False, f"Timeout: {e}")

        # --- 8. Sécurité de session : cookie HttpOnly + rôles JWT --------
        print("[8] Sécurité session (cookie HttpOnly + rôles JWT)")
        try:
            cookies = context.cookies()
            sess = [c for c in cookies if "session-token" in c["name"]]
            httponly_ok = len(sess) > 0 and all(c.get("httpOnly") for c in sess)
            record("TC-UC3-12", "Session NextAuth en cookie HttpOnly",
                    httponly_ok,
                    f"{len(sess)} cookie(s) session-token, httpOnly={[c.get('httpOnly') for c in sess]}",
                    "")

            # rôles JWT : décoder l'access token renvoyé par /api/auth/session
            r = context.request.get(f"{BASE_URL}/api/auth/session")
            data = r.json()
            tok = data.get("accessToken", "")
            role_claims = []
            if tok and tok.count(".") >= 2:
                part = tok.split(".")[1]
                part += "=" * (-len(part) % 4)
                payload = json.loads(base64.urlsafe_b64decode(part))
                realm_roles = payload.get("realm_access", {}).get("roles", [])
                role_claims = realm_roles
            role_ok = "psychiatre" in [str(x).lower() for x in role_claims] or \
                      str(data.get("user", {}).get("role", "")).lower() == "psychiatre"
            record("TC-UC13-04", "Rôles JWT mappés (psychiatre)",
                    role_ok,
                    f"role session={data.get('user', {}).get('role')}, realm_roles={role_claims}",
                    "")
        except Exception as e:
            record("TC-UC3-12", "Sécurité session", False, f"Erreur: {e}")

        # --- 9. Déconnexion fédérée (EN DERNIER, ferme la session) -------
        print("[9] Déconnexion fédérée")
        try:
            page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2500)
            dismiss_cookies(page)
            page.get_by_role("button", name=re.compile("connexion|Déconnexion|Deconnexion", re.I)).first.click(timeout=8000)
            page.wait_for_timeout(4000)
            ev = shot(page, "TC-UC3-11_logout.png")
            on_login = "/login" in page.url or "auth.mood-iot.fr" in page.url
            # vérifier que la session est bien fermée : revenir sur / doit
            # rediriger vers /login (plus de cookie de session valide).
            page.goto(BASE_URL, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(2500)
            logged_out = "/login" in page.url or "auth.mood-iot.fr" in page.url
            record("TC-UC3-11", "Déconnexion fédérée (ferme la session)",
                    on_login and logged_out,
                    f"Après logout URL={page.url} ; retour sur / -> redirigé login={logged_out}",
                    ev)
        except PWTimeout as e:
            record("TC-UC3-11", "Déconnexion fédérée", False, f"Timeout: {e}")

        browser.close()
        _dump()


def _dump():
    out = EVID_DIR / "resultats_e2e.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    reussis = sum(1 for r in results if r["statut"] == "Réussi")
    print(f"\n=== Résumé : {reussis}/{len(results)} Réussi ===")
    print(f"Résultats JSON : {out}")
    print(f"Captures       : {EVID_DIR}\n")


if __name__ == "__main__":
    main()
