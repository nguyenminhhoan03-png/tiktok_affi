import sys
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.append(str(Path(__file__).parent.parent))

from src.cookie_manager import CookieManager

def main():
    cookies_path = "./cookies/cookies.json"
    product_url = "https://vt.tiktok.com/ZS9jj3rYGhudo-VGxmu/"
    
    with sync_playwright() as p:
        manager = CookieManager(cookies_path)
        browser, context = manager.load_context_with_cookies(p, headless=False)
        page = context.new_page()
        print("Visiting product url...")
        try:
            page.goto(product_url, wait_until="domcontentloaded", timeout=25000)
        except Exception as e:
            print(f"Warning/Error visiting: {e}")
        page.wait_for_timeout(5000)
        
        title = page.title()
        print(f"Page Title: {title}")
        print(f"Page URL: {page.url}")
        
        js_dump = """
        () => {
            const imgs = Array.from(document.querySelectorAll("img"));
            return imgs.map((img, idx) => {
                const rect = img.getBoundingClientRect();
                return {
                    idx: idx,
                    src: img.src,
                    class: img.className,
                    id: img.id,
                    alt: img.alt,
                    width: img.width,
                    height: img.height,
                    naturalWidth: img.naturalWidth,
                    naturalHeight: img.naturalHeight,
                    rect: {
                        top: rect.top,
                        left: rect.left,
                        bottom: rect.bottom,
                        right: rect.right,
                        width: rect.width,
                        height: rect.height
                    },
                    parentClass: img.parentElement ? img.parentElement.className : '',
                    grandParentClass: (img.parentElement && img.parentElement.parentElement) ? img.parentElement.parentElement.className : ''
                };
            });
        }
        """
        data = page.evaluate(js_dump)
        import json
        os.makedirs("scratch", exist_ok=True)
        with open("scratch/images_dump.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("Done dumping images to scratch/images_dump.json")
        browser.close()

if __name__ == "__main__":
    main()
