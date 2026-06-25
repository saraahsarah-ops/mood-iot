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

import json
import os
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
            # cliquer le premier patient trouvé
            target = found[0] if found else EXPECTED_PATIENTS[0]
            page.click(f"text={target}", timeout=10000)
            page.wait_for_load_state("domcontentloaded", timeout=15000)
            page.wait_for_timeout(4000)
            fiche_body = page.inner_text("body")
            ev = shot(page, "TC-UC9-03_fiche_patient.png")

            # BPM doit être un entier (pas 65.6630...)
            import re
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

            # Bouton planifier téléconsultation
            tc_btn = page.locator("text=/téléconsultation/i").count()
            record(
                "TC-UC9-06",
                "Fiche patient : bouton Planifier téléconsultation",
                tc_btn > 0,
                f"Occurrences 'téléconsultation' dans la fiche: {tc_btn}",
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
        print("[6] Page téléconsultation")
        try:
            page.goto(f"{BASE_URL}/teleconsult", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(4000)
            tbody = page.inner_text("body")
            ev = shot(page, "TC-UC5-01_teleconsult_dropdown.png")
            # le dropdown doit lister des patients (pas vide -> bug 422 corrigé)
            opt_count = page.locator("select option, [role=option]").count()
            tfound = [pat for pat in EXPECTED_PATIENTS if pat in tbody]
            tc_ok = opt_count > 1 or len(tfound) >= 3
            record(
                "TC-UC5-01",
                "Téléconsultation : dropdown patients peuplé (bug 422 corrigé)",
                tc_ok,
                f"options={opt_count}, patients dans la page={tfound}",
                ev,
            )
        except PWTimeout as e:
            record("TC-UC5-01", "Téléconsultation dropdown", False, f"Timeout: {e}")

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
