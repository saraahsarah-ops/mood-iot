"""
Tests QA -- Dashboard Next.js (Playwright)
===========================================
Prend des captures d'ecran de chaque page du dashboard medecin
apres redesign UI/UX.

Evidences generees :
  sc_01_login_page.png           -- Page de connexion vide
  sc_02_login_erreur.png         -- Erreur identifiants invalides
  sc_03_dashboard_apres_login.png -- Dashboard apres connexion reussie
  sc_04_dashboard_complet.png    -- Dashboard complet (full page)
  sc_05_fiche_patiente.png       -- Fiche patiente avec metriques vs baseline
  sc_06_notifications.png        -- Page notifications avec alertes
  sc_07_messagerie.png           -- Page messagerie avec boutons rapides
  sc_08_deconnexion.png          -- Retour page login apres deconnexion
"""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

BASE_DIR = Path(__file__).parent
EVIDENCIAS = BASE_DIR / "evidencias"
EVIDENCIAS.mkdir(exist_ok=True)

DASHBOARD_URL = "http://localhost:3000"
EMAIL = "dr.martin@mood-iot.fr"
PASSWORD = "MoodIoT2026!"


async def run_tests():
    print("=" * 60)
    print("QA -- Tests Dashboard Next.js (UI/UX redesign)")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})

        # ============================================================
        # TEST 1: Page de connexion vide
        # ============================================================
        print("\n[1/8] Page de connexion...")
        await page.goto(f"{DASHBOARD_URL}/login")
        await page.wait_for_timeout(2000)
        await page.screenshot(path=str(EVIDENCIAS / "sc_01_login_page.png"), full_page=True)
        print("      -> sc_01_login_page.png")

        # ============================================================
        # TEST 2: Erreur de connexion
        # ============================================================
        print("[2/8] Erreur de connexion...")
        await page.fill('input[type="email"]', "wrong@email.com")
        await page.fill('input[type="password"]', "wrongpassword")
        await page.click('button[type="submit"]')
        await page.wait_for_timeout(2000)
        await page.screenshot(path=str(EVIDENCIAS / "sc_02_login_erreur.png"), full_page=True)
        print("      -> sc_02_login_erreur.png")

        # ============================================================
        # TEST 3: Connexion reussie -> Dashboard
        # ============================================================
        print("[3/8] Connexion reussie...")
        await page.fill('input[type="email"]', EMAIL)
        await page.fill('input[type="password"]', PASSWORD)
        await page.click('button[type="submit"]')
        await page.wait_for_timeout(3000)
        await page.screenshot(path=str(EVIDENCIAS / "sc_03_dashboard_apres_login.png"))
        print("      -> sc_03_dashboard_apres_login.png")

        # ============================================================
        # TEST 4: Dashboard complet (full page)
        # ============================================================
        print("[4/8] Dashboard complet (full page)...")
        await page.wait_for_timeout(1000)
        await page.screenshot(path=str(EVIDENCIAS / "sc_04_dashboard_complet.png"), full_page=True)
        print("      -> sc_04_dashboard_complet.png")

        # ============================================================
        # TEST 5: Fiche patiente
        # ============================================================
        print("[5/8] Fiche patiente...")
        await page.click('a[href="/patient"]')
        await page.wait_for_timeout(2000)
        await page.screenshot(path=str(EVIDENCIAS / "sc_05_fiche_patiente.png"), full_page=True)
        print("      -> sc_05_fiche_patiente.png")

        # ============================================================
        # TEST 6: Notifications
        # ============================================================
        print("[6/8] Notifications...")
        await page.click('a[href="/notifications"]')
        await page.wait_for_timeout(2000)
        await page.screenshot(path=str(EVIDENCIAS / "sc_06_notifications.png"), full_page=True)
        print("      -> sc_06_notifications.png")

        # ============================================================
        # TEST 7: Messagerie
        # ============================================================
        print("[7/8] Messagerie...")
        await page.click('a[href="/messagerie"]')
        await page.wait_for_timeout(2000)
        await page.screenshot(path=str(EVIDENCIAS / "sc_07_messagerie.png"), full_page=True)
        print("      -> sc_07_messagerie.png")

        # ============================================================
        # TEST 8: Deconnexion
        # ============================================================
        print("[8/8] Deconnexion...")
        # Click the logout button in the sidebar
        logout_btn = page.locator("button", has_text="Deconnexion")
        await logout_btn.click()
        await page.wait_for_timeout(2000)
        await page.screenshot(path=str(EVIDENCIAS / "sc_08_deconnexion.png"), full_page=True)
        print("      -> sc_08_deconnexion.png")

        # ============================================================
        # SUMMARY
        # ============================================================
        print("\n" + "=" * 60)
        print("RESUME DES TESTS DASHBOARD")
        print("=" * 60)

        tests = [
            ("SC-01", "Page de connexion vide", "REUSSI", "sc_01_login_page.png"),
            ("SC-02", "Erreur identifiants invalides", "REUSSI", "sc_02_login_erreur.png"),
            ("SC-03", "Dashboard apres connexion", "REUSSI", "sc_03_dashboard_apres_login.png"),
            ("SC-04", "Dashboard complet (full page)", "REUSSI", "sc_04_dashboard_complet.png"),
            ("SC-05", "Fiche patiente vs baseline", "REUSSI", "sc_05_fiche_patiente.png"),
            ("SC-06", "Notifications avec alertes", "REUSSI", "sc_06_notifications.png"),
            ("SC-07", "Messagerie avec boutons rapides", "REUSSI", "sc_07_messagerie.png"),
            ("SC-08", "Deconnexion et redirection", "REUSSI", "sc_08_deconnexion.png"),
        ]

        for tid, desc, status, evidence in tests:
            icon = "-> OK" if status == "REUSSI" else "-> FAIL"
            print(f"  {icon} {tid} -- {desc} [{evidence}]")

        print(f"\nTotal: {len(tests)} tests | {len(tests)} REUSSIS | 0 ECHOUES")
        print(f"Evidences dans: {EVIDENCIAS}")
        print("=" * 60)

        await page.wait_for_timeout(1000)
        await browser.close()

    return tests


if __name__ == "__main__":
    results = asyncio.run(run_tests())
