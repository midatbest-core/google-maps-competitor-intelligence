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
            if "onrender.com" in res.url:
                cors = res.headers.get("access-control-allow-origin")
                network_logs.append(f"{res.request.method} {res.url} -> {res.status} (CORS: {cors})")
        page.on("response", on_response)

        page.on("requestfailed", lambda req: network_logs.append(f"FAILED: {req.method} {req.url} -> {req.failure}"))

        # Login
        await page.goto("https://google-maps-competitor-intelligence.onrender.com/login", wait_until="domcontentloaded")
        await page.fill('input[type="email"]', 'adisshinde05@gmail.com')
        await page.fill('input[type="password"]', '12345678')
        await page.click('button[type="submit"]')
        await asyncio.sleep(3)

        # 1. Competitors page
        print("Testing Competitors page...")
        await page.goto("https://google-maps-competitor-intelligence.onrender.com/projects/235a2d92-9c65-4fe9-af13-a38275ba89bd/competitors", wait_until="domcontentloaded")
        await asyncio.sleep(16) # wait for the slow 15s eager load!

        # 2. Scraping page
        print("Testing Scraping page & triggering scrape...")
        await page.goto("https://google-maps-competitor-intelligence.onrender.com/projects/235a2d92-9c65-4fe9-af13-a38275ba89bd/scraping", wait_until="domcontentloaded")
        await asyncio.sleep(5)
        
        # Click start scrape button if found
        scrape_btn = await page.query_selector("button:has-text('Start Scraping'), button:has-text('Scrape All')")
        if scrape_btn:
            print("Found scrape button, clicking...")
            await scrape_btn.click()
            await asyncio.sleep(5)
        else:
            print("No scrape button found")

        print("\n--- ALL CONSOLE LOGS ---")
        for log in console_logs:
            print("  ", log)

        print("\n--- ALL NETWORK LOGS ---")
        for net in network_logs:
            print("  ", net)

        await browser.close()

asyncio.run(main())
