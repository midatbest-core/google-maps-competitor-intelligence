import asyncio
import sys
from app.scraper.google_maps.adapter import GoogleMapsAdapter

async def main():
    if len(sys.argv) < 2:
        print("Usage: python smoke_scrape.py <google_maps_url>")
        sys.exit(1)
        
    url = sys.argv[1]
    print(f"Starting smoke test scrape for: {url}")
    
    adapter = GoogleMapsAdapter()
    try:
        result = await adapter.scrape(url)
        print("\n--- Scrape Result ---")
        print(f"Status: {result.status}")
        print(f"Error Message: {result.error_message}")
        print(f"Posts Extracted: {len(result.posts)}")
        
        for i, post in enumerate(result.posts, 1):
            print(f"\n[Post {i}]")
            print(f"Content: {post.content[:100]}...")
            print(f"Date: {post.post_date}")
            print(f"Media URL: {post.media_url}")
            print(f"CTA Text: {post.cta_text}")
            print(f"CTA URL: {post.cta_url}")
    except Exception as e:
        print(f"Error during scrape: {e}")
    finally:
        print("\nCleaning up resources...")
        await adapter.close()
        
if __name__ == "__main__":
    asyncio.run(main())
