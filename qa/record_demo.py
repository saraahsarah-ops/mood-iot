"""
Graba videos demo del dashboard Mood-IoT y la app mobile.
"""

import asyncio
import shutil
from pathlib import Path
from playwright.async_api import async_playwright

BASE_DIR = Path(__file__).parent
OUT = BASE_DIR / "evidencias"
OUT.mkdir(exist_ok=True)

DASHBOARD_URL = "http://localhost:3000"
EMAIL_DR = "dr.martin@mood-iot.fr"
import os
from dotenv import load_dotenv

load_dotenv()
PASSWORD = os.getenv("TEST_USER_PASSWORD", "MoodIoT2026!")


async def record_dashboard():
    print("=" * 60)
    print("Recording Dashboard Demo...")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            record_video_dir=str(OUT),
            record_video_size={"width": 1366, "height": 768},
        )
        page = await context.new_page()

        # Login
        print("  [1] Login...")
        await page.goto(f"{DASHBOARD_URL}/login")
        await page.wait_for_timeout(2000)
        await page.fill('input[type="email"]', EMAIL_DR)
        await page.wait_for_timeout(500)
        await page.fill('input[type="password"]', PASSWORD)
        await page.wait_for_timeout(500)
        await page.click('button[type="submit"]')
        await page.wait_for_timeout(3000)

        # Dashboard hero screenshot
        print("  [2] Dashboard hero screenshot...")
        await page.screenshot(
            path=str(OUT / "screenshot_dashboard_hero.png"),
            full_page=False,
        )
        await page.wait_for_timeout(2500)

        # Scroll
        print("  [3] Scrolling dashboard...")
        await page.mouse.wheel(0, 250)
        await page.wait_for_timeout(1200)
        await page.mouse.wheel(0, 250)
        await page.wait_for_timeout(1200)
        await page.mouse.wheel(0, -500)
        await page.wait_for_timeout(1000)

        # Fiche patiente
        print("  [4] Fiche patiente...")
        await page.click('a[href="/patient"]')
        await page.wait_for_timeout(2500)
        await page.select_option("select", "Marie D.")
        await page.wait_for_timeout(2000)
        await page.select_option("select", "Sophie L.")
        await page.wait_for_timeout(2000)

        # Notifications
        print("  [5] Notifications...")
        await page.click('a[href="/notifications"]')
        await page.wait_for_timeout(2500)

        btn = page.locator("button", has_text="Marquer lu").first
        if await btn.count() > 0:
            await btn.click()
            await page.wait_for_timeout(1500)

        # Messagerie
        print("  [6] Messagerie...")
        await page.click('a[href="/messagerie"]')
        await page.wait_for_timeout(2500)

        quick_btn = page.locator("button", has_text="Encouragement")
        if await quick_btn.count() > 0:
            await quick_btn.click()
            await page.wait_for_timeout(2000)

        # Back to dashboard
        print("  [7] Back to dashboard...")
        await page.click('a[href="/"]')
        await page.wait_for_timeout(2500)

        print("  [8] Closing...")
        await page.wait_for_timeout(1000)
        video_path = await page.video.path()
        await context.close()
        await browser.close()

        final_path = OUT / "demo_dashboard.webm"
        shutil.move(str(video_path), str(final_path))
        print(f"\n  Video: {final_path}")
        print(f"  Screenshot: {OUT / 'screenshot_dashboard_hero.png'}")


async def record_mobile():
    print("\n" + "=" * 60)
    print("Recording Mobile App Demo...")
    print("=" * 60)

    preview = Path(r"G:\Mi unidad\Cursos Master ADE\FIL ROUGE\Diagramas Drawio\mood-iot\mobile-hub\SanteConnect\preview.html")
    if not preview.exists():
        print("  preview.html not found, skipping")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1200, "height": 800},
            record_video_dir=str(OUT),
            record_video_size={"width": 1200, "height": 800},
        )
        page = await context.new_page()

        url = "file:///" + str(preview).replace("\\", "/")
        print("  [1] Opening preview...")
        await page.goto(url)
        await page.wait_for_timeout(2500)

        # Login (fields are pre-filled with sophie.dupont@email.fr)
        print("  [2] Login as Sophie...")
        await page.fill("#emailInput", "sophie.dupont@email.fr")
        await page.wait_for_timeout(500)
        await page.fill("#passInput", "MoodIoT2026!")
        await page.wait_for_timeout(500)
        await page.click("#loginBtn")

        # Wait for login to complete and auto-sync to finish
        print("  [3] Waiting for login + auto-sync...")
        await page.wait_for_timeout(3000)

        # Wait until sync badge appears (green or red)
        print("  [4] Waiting for sync result...")
        try:
            await page.wait_for_selector(".sync-success, .sync-error", timeout=15000)
        except Exception:
            pass
        await page.wait_for_timeout(3000)

        # Click sync again manually
        print("  [5] Manual re-sync...")
        try:
            sync_btn = page.locator("#syncBtn")
            if await sync_btn.is_visible():
                await sync_btn.click()
                await page.wait_for_timeout(5000)
        except Exception:
            pass

        # Show the final state for a moment
        print("  [6] Showing final state...")
        await page.wait_for_timeout(3000)

        # Logout
        print("  [7] Logout...")
        try:
            await page.click("button.btn-logout")
            await page.wait_for_timeout(2500)
        except Exception:
            pass

        print("  [8] Closing...")
        await page.wait_for_timeout(1000)
        video_path = await page.video.path()
        await context.close()
        await browser.close()

        final_path = OUT / "demo_mobile.webm"
        shutil.move(str(video_path), str(final_path))
        print(f"\n  Video: {final_path}")


async def main():
    await record_dashboard()
    await record_mobile()
    print("\n" + "=" * 60)
    print("ALL DEMOS RECORDED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
