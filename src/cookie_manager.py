import time
import random
from playwright.sync_api import Page, Browser, Playwright, sync_playwright
from loguru import logger

from src.utils import load_cookies, save_cookies


class CookieManager:
    """Quản lý session/cookies cho TikTok"""

    TIKTOK_DOMAIN = "https://www.tiktok.com"

    def __init__(self, cookies_path: str):
        self.cookies_path = cookies_path

    def export_cookies_interactively(self) -> None:
        """
        Mở trình duyệt để user đăng nhập thủ công,
        sau đó tự động lưu cookies lại.
        """
        logger.info("🌐 Mở trình duyệt để bạn đăng nhập TikTok...")
        logger.info("👉 Hãy đăng nhập vào TikTok, sau đó nhấn Enter trong terminal này.")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, channel="chrome", slow_mo=50)
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()
            page.goto(self.TIKTOK_DOMAIN)

            input("\n✅ Sau khi đã đăng nhập xong, nhấn Enter để lưu cookies...")

            cookies = context.cookies()
            save_cookies(cookies, self.cookies_path)
            browser.close()

        logger.info("🎉 Export cookies thành công!")

    def load_context_with_cookies(self, playwright: Playwright, headless: bool = False):
        """
        Tạo browser context đã có session cookies (không cần login lại).
        """
        browser = playwright.chromium.launch(
            headless=headless,
            channel="chrome",
            slow_mo=50,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )

        cookies = load_cookies(self.cookies_path)
        from src.utils import clean_cookies_for_playwright
        cleaned_cookies = clean_cookies_for_playwright(cookies)
        context.add_cookies(cleaned_cookies)
        logger.info(f"🍪 Đã load {len(cleaned_cookies)} cookies vào session")

        return browser, context
