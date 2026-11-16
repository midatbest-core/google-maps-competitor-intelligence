import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        console_logs = []
        network_logs = []

        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        
        def on_response(res):
            if "onrender.com/api" in res.url or "comp-intel-api" in res.url:
                cors = res.headers.get("access-control-allow-origin")
                network_logs.append(f"{res.request.method} {res.url} -> {res.status} (CORS: {cors})")
        page.on("response", on_response)

        page.on("requestfailed", lambda req: network_logs.append(f"FAILED: {req.method} {req.url} -> {req.failure}"))

        print("Navigating to https://google-maps-competitor-intelligence.onrender.com/login ...")
        await page.goto("https://google-maps-competitor-intelligence.onrender.com/login", wait_until="domcontentloaded", timeout=30000)
        
        # Fill login form
        print("Filling login form...")
        await page.fill('input[type="email"]', 'adisshinde05@gmail.com')
        await page.fill('input[type="password"]', '12345678')
        await page.click('button[type="submit"]')

        # Wait for navigation or token
        await asyncio.sleep(4)
        print("Current URL after login:", page.url)

        # Take screenshot of dashboard
        await page.screenshot(path="qa_audit/screenshots/live_dashboard_render.png")

        # Now navigate to Discovery
        print("Navigating to Discovery page...")
        await page.goto("https://google-maps-competitor-intelligence.onrender.com/projects/235a2d92-9c65-4fe9-af13-a38275ba89bd/discovery", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)
        await page.screenshot(path="qa_audit/screenshots/live_discovery_render.png")

        # Now navigate to Scraping
        print("Navigating to Scraping page...")
        await page.goto("https://google-maps-competitor-intelligence.onrender.com/projects/235a2d92-9c65-4fe9-af13-a38275ba89bd/scraping", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)
        await page.screenshot(path="qa_audit/screenshots/live_scraping_render.png")

        print("\n--- CONSOLE LOGS ---")
        for log in console_logs:
            print("  ", log)

        print("\n--- NETWORK LOGS ---")
        for net in network_logs:
            print("  ", net)

        await browser.close()

asyncio.run(main())
