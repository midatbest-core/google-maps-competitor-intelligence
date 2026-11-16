import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        console_messages = []
        page.on("console", lambda msg: console_messages.append(f"[{msg.type}] {msg.text}"))
        
        failed_requests = []
        page.on("requestfailed", lambda req: failed_requests.append(f"{req.method} {req.url} - {req.failure}"))

        print("Navigating to https://roster-iq-delta.vercel.app ...")
        response = await page.goto("https://roster-iq-delta.vercel.app", wait_until="networkidle", timeout=30000)
        print(f"HTTP Status: {response.status if response else 'None'}")
        print(f"Title: {await page.title()}")

        await page.screenshot(path="qa_audit/screenshots/live_vercel_rosteriq.png", full_page=True)
        print("Screenshot saved to qa_audit/screenshots/live_vercel_rosteriq.png")

        print("\nConsole messages:")
        for msg in console_messages:
            print("  ", msg)

        print("\nFailed requests:")
        for req in failed_requests:
            print("  ", req)

        content = await page.content()
        print(f"\nPage content length: {len(content)}")
        
        # Check for visible text elements
        body_text = await page.inner_text("body")
        print("\nBody text preview:")
        print(body_text[:1000])

        await browser.close()

asyncio.run(main())
